"""CLI helpers for validating addon tag metadata."""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config.tags import ADDON_TAGS, MAX_ADDON_TAGS, VALID_ADDON_TAGS, normalize_tags
from .utils.logging import get_logger, setup_logging

logger = get_logger("tag_review")
COMMENT_MARKER = "<!-- zotero-addon-tag-review -->"


@dataclass
class AddonConfigEntry:
    """Addon config file loaded from the addons directory."""

    path: Path
    repo: str
    data: dict[str, Any]
    tags: list[str]

    @classmethod
    def load(cls, path: Path) -> AddonConfigEntry:
        """Load an addon config file."""
        text = path.read_text(encoding="utf-8").strip()
        return cls.from_text(path, text)

    @classmethod
    def from_text(cls, path: Path, text: str) -> AddonConfigEntry:
        """Load an addon config file from raw text."""
        text = text.strip()
        data: dict[str, Any]
        if not text:
            data = {}
        else:
            parsed = json.loads(text)
            if not isinstance(parsed, dict):
                raise ValueError("Addon config must be a JSON object")
            data = parsed

        repo = path.name.replace("@", "/", 1)
        tags = data.get("tags", [])
        if tags is None:
            tags = []
        if not isinstance(tags, list):
            raise ValueError("'tags' must be a JSON array when present")

        return cls(path=path, repo=repo, data=data, tags=list(tags))


@dataclass
class FileReviewResult:
    """Validation outcome for one addon config file."""

    path: Path
    repo: str
    status: str
    current_tags: list[str]
    messages: list[str]

    @property
    def ok(self) -> bool:
        return self.status == "ok"


@dataclass
class TagSuggestion:
    """AI tag recommendation for one addon."""

    path: Path
    repo: str
    suggested_tags: list[str]
    confidence: str
    reason: str
    error: str = ""


class AddonTagReviewer:
    """Validate addon tags locally."""

    def review_file(self, path: Path) -> FileReviewResult:
        """Review a single addon config file."""
        try:
            entry = AddonConfigEntry.load(path)
        except Exception as exc:
            return FileReviewResult(
                path=path,
                repo=path.name.replace("@", "/", 1),
                status="failed",
                current_tags=[],
                messages=[str(exc)],
            )
        return self.review_entry(entry)

    def review_text(self, path: Path, text: str) -> FileReviewResult:
        """Review a single addon config file from raw text."""
        try:
            entry = AddonConfigEntry.from_text(path, text)
        except Exception as exc:
            return FileReviewResult(
                path=path,
                repo=path.name.replace("@", "/", 1),
                status="failed",
                current_tags=[],
                messages=[str(exc)],
            )
        return self.review_entry(entry)

    def review_entry(self, entry: AddonConfigEntry) -> FileReviewResult:
        """Review a parsed addon config entry."""
        messages = self._validate(entry)

        if messages:
            return FileReviewResult(
                path=entry.path,
                repo=entry.repo,
                status="failed",
                current_tags=entry.tags,
                messages=messages,
            )

        return FileReviewResult(
            path=entry.path,
            repo=entry.repo,
            status="ok",
            current_tags=normalize_tags(entry.tags),
            messages=[],
        )

    def _validate(self, entry: AddonConfigEntry) -> list[str]:
        """Validate file structure and tag taxonomy."""
        messages: list[str] = []

        unknown_keys = sorted(set(entry.data) - {"tags", "recommended"})
        if unknown_keys:
            messages.append(
                f"Unsupported addon config keys: {', '.join(unknown_keys)}"
            )

        if "recommended" in entry.data and not isinstance(
            entry.data["recommended"], bool
        ):
            messages.append("'recommended' must be a boolean when present")

        if not entry.tags:
            return messages

        non_string_tags = [tag for tag in entry.tags if not isinstance(tag, str)]
        if non_string_tags:
            messages.append("All tags must be strings")
            return messages

        if len(entry.tags) != len(set(entry.tags)):
            messages.append("Duplicate tags are not allowed")

        invalid_tags = [tag for tag in entry.tags if tag not in VALID_ADDON_TAGS]
        if invalid_tags:
            messages.append(
                "Unknown tags: "
                f"{', '.join(invalid_tags)}. Allowed tags: "
                f"{', '.join(VALID_ADDON_TAGS)}"
            )

        if len(entry.tags) > MAX_ADDON_TAGS:
            messages.append(f"At most {MAX_ADDON_TAGS} tags are allowed per addon")

        normalized = normalize_tags(entry.tags)
        if entry.tags != normalized:
            messages.append(f"Tags should use canonical order: {normalized}")

        return messages


class GitHubPullRequestClient:
    """Small GitHub REST client used by PR tag review."""

    def __init__(
        self,
        repository: str,
        token: str,
        api_url: str = "https://api.github.com",
    ) -> None:
        self.repository = repository
        self.api_url = api_url.rstrip("/")
        import requests

        self.session = requests.Session()
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _api(self, path: str, **kwargs: Any) -> Any:
        response = self.session.get(
            f"{self.api_url}{path}",
            headers=self.headers,
            timeout=30,
            **kwargs,
        )
        response.raise_for_status()
        return response

    def _api_json(self, path: str, **kwargs: Any) -> Any:
        return self._api(path, **kwargs).json()

    def list_changed_addon_files(self, pr_number: int) -> list[dict[str, Any]]:
        """List added/modified addon files in a pull request."""
        files: list[dict[str, Any]] = []
        page = 1
        while True:
            data = self._api_json(
                f"/repos/{self.repository}/pulls/{pr_number}/files",
                params={"per_page": 100, "page": page},
            )
            if not data:
                break
            for item in data:
                filename = item.get("filename", "")
                status = item.get("status")
                path = Path(filename)
                if (
                    len(path.parts) == 2
                    and path.parts[0] == "addons"
                    and "@" in path.name
                    and status != "removed"
                ):
                    files.append(item)
            page += 1
        return files

    def fetch_pr_file_text(self, file_info: dict[str, Any]) -> str:
        """Fetch a changed file's PR-head content through its raw URL."""
        raw_url = file_info.get("raw_url")
        if not raw_url:
            return ""
        response = self.session.get(raw_url, timeout=30)
        response.raise_for_status()
        return response.text

    def fetch_readme(self, repo: str, limit: int) -> str:
        """Fetch the target addon's default-branch README."""
        headers = dict(self.headers)
        headers["Accept"] = "application/vnd.github.raw"
        response = self.session.get(
            f"{self.api_url}/repos/{repo}/readme",
            headers=headers,
            timeout=30,
        )
        if response.status_code == 404:
            return ""
        response.raise_for_status()
        return response.text[:limit]

    def upsert_pr_comment(self, pr_number: int, body: str) -> None:
        """Create or update the bot comment for this review."""
        comments = self._api_json(
            f"/repos/{self.repository}/issues/{pr_number}/comments",
            params={"per_page": 100},
        )
        existing_id: int | None = None
        for comment in comments:
            if COMMENT_MARKER in comment.get("body", ""):
                existing_id = comment.get("id")
                break

        if existing_id:
            response = self.session.patch(
                f"{self.api_url}/repos/{self.repository}/issues/comments/{existing_id}",
                headers=self.headers,
                json={"body": body},
                timeout=30,
            )
        else:
            response = self.session.post(
                f"{self.api_url}/repos/{self.repository}/issues/{pr_number}/comments",
                headers=self.headers,
                json={"body": body},
                timeout=30,
            )
        response.raise_for_status()


class OpenAICompatibleTagSuggester:
    """Recommend addon tags through an OpenAI-compatible chat API."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        readme_limit: int,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.readme_limit = readme_limit
        import requests

        self.session = requests.Session()

    @property
    def endpoint(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    def suggest(
        self,
        repo: str,
        path: Path,
        current_tags: list[str],
        readme: str,
    ) -> TagSuggestion:
        """Ask the model for tag suggestions."""
        if not readme.strip():
            return TagSuggestion(
                path=path,
                repo=repo,
                suggested_tags=[],
                confidence="low",
                reason="Target repository README was not found.",
                error="missing README",
            )

        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You classify Zotero add-ons. Return only strict JSON "
                        "with keys: tags, confidence, reason. The tags array must "
                        f"contain at most {MAX_ADDON_TAGS} values and every value "
                        "must be selected from the allowed tag list."
                    ),
                },
                {
                    "role": "user",
                    "content": self._build_prompt(repo, current_tags, readme),
                },
            ],
        }
        response = self.session.post(
            self.endpoint,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        parsed = _parse_json_object(content)
        tags = parsed.get("tags", [])
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise ValueError("Model response field 'tags' must be a string array")
        if not tags:
            raise ValueError("Model response must include at least one tag")
        if len(tags) != len(set(tags)):
            raise ValueError("Model response contains duplicate tags")
        if len(tags) > MAX_ADDON_TAGS:
            raise ValueError(f"Model returned more than {MAX_ADDON_TAGS} tags")

        invalid = [tag for tag in tags if tag not in VALID_ADDON_TAGS]
        if invalid:
            raise ValueError(f"Model returned unknown tags: {', '.join(invalid)}")

        normalized_tags = normalize_tags(tags)
        reason = parsed.get("reason", "")
        confidence = parsed.get("confidence", "medium")
        return TagSuggestion(
            path=path,
            repo=repo,
            suggested_tags=normalized_tags,
            confidence=str(confidence),
            reason=str(reason)[:500],
        )

    def _build_prompt(self, repo: str, current_tags: list[str], readme: str) -> str:
        tag_catalog = "\n".join(
            f"- {tag}: {description}" for tag, description in ADDON_TAGS.items()
        )
        return (
            f"Repository: {repo}\n"
            f"Current tags in PR: {current_tags or []}\n\n"
            "Allowed tags:\n"
            f"{tag_catalog}\n\n"
            "Classify the add-on using the README below. Prefer the primary "
            "user-facing function over implementation details. If two tags are "
            "useful, include two; "
            "otherwise include one.\n\n"
            "README:\n"
            f"{readme[: self.readme_limit]}"
        )


def _parse_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object, tolerating markdown fences around model output."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("Model response did not contain a JSON object")
    parsed = json.loads(stripped[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Model response JSON must be an object")
    return parsed


def _table_cell(text: str) -> str:
    """Escape simple markdown table cell content."""
    return text.replace("\n", " ").replace("|", "\\|")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for tag review."""
    parser = argparse.ArgumentParser(
        description="Validate addon tags for addon config files."
    )
    parser.add_argument(
        "--files",
        nargs="+",
        help="Addon config files to review",
    )
    parser.add_argument(
        "--summary-file",
        default="",
        help="Optional markdown file to append the review summary to",
    )
    parser.add_argument("--pr-number", type=int, help="Pull request number to review")
    parser.add_argument(
        "--repository",
        default=os.getenv("GITHUB_REPOSITORY", ""),
        help="GitHub repository in owner/name form",
    )
    parser.add_argument(
        "--github-token",
        default=os.getenv("GITHUB_TOKEN", ""),
        help="GitHub token for PR file, README, and comment access",
    )
    parser.add_argument(
        "--github-api-url",
        default=os.getenv("GITHUB_API_URL", "https://api.github.com"),
        help="GitHub API base URL",
    )
    parser.add_argument(
        "--ai-review",
        action="store_true",
        help=(
            "Fetch target README files and ask the configured model for tag "
            "suggestions"
        ),
    )
    parser.add_argument(
        "--model-base-url",
        default=os.getenv("AI_REVIEW_BASE_URL", ""),
        help="OpenAI-compatible API base URL, for example https://api.openai.com/v1",
    )
    parser.add_argument(
        "--model-api-key",
        default=os.getenv("AI_REVIEW_API_KEY", ""),
        help="OpenAI-compatible API key",
    )
    parser.add_argument(
        "--model-name",
        default=os.getenv("AI_REVIEW_MODEL", ""),
        help="Model name for AI tag review",
    )
    parser.add_argument(
        "--readme-limit",
        type=int,
        default=12000,
        help="Maximum README characters sent to the model",
    )
    parser.add_argument(
        "--post-comment",
        action="store_true",
        help="Create or update a PR comment with the review summary",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level",
    )
    return parser.parse_args()


def render_summary(
    results: list[FileReviewResult],
    suggestions: list[TagSuggestion] | None = None,
) -> str:
    """Render a GitHub-friendly markdown summary."""
    if not results:
        return "## Addon tag review\n\nNo addon files were provided for review.\n"

    lines = ["## Addon tag review", ""]
    lines.append("| File | Status | Tags |")
    lines.append("| --- | --- | --- |")
    for result in results:
        tags = ", ".join(result.current_tags) or "-"
        lines.append(f"| `{result.path}` | {result.status} | {tags} |")
        for message in result.messages:
            lines.append(f"- `{result.path}`: {message}")
    lines.append("")
    lines.append("Allowed tags: " + ", ".join(f"`{tag}`" for tag in ADDON_TAGS))
    lines.append("")

    suggestions = suggestions or []
    if suggestions:
        result_by_path = {result.path: result for result in results}
        lines.append("### AI suggestions")
        lines.append("")
        lines.append(
            "| File | Current tags | Suggested tags | Match | Confidence | Notes |"
        )
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for suggestion in suggestions:
            result = result_by_path.get(suggestion.path)
            current_tags = result.current_tags if result else []
            current = ", ".join(current_tags) or "-"
            tags = ", ".join(suggestion.suggested_tags) or "-"
            match = "yes" if current_tags == suggestion.suggested_tags else "no"
            if suggestion.error:
                match = "-"
            note = suggestion.error or suggestion.reason or "-"
            lines.append(
                f"| `{suggestion.path}` | {current} | {tags} | {match} | "
                f"{_table_cell(suggestion.confidence)} | {_table_cell(note)} |"
            )
        lines.append("")

    return "\n".join(lines)


def _review_pull_request(
    args: argparse.Namespace,
) -> tuple[list[FileReviewResult], list[TagSuggestion]]:
    """Review addon files from a PR using GitHub APIs."""
    if not args.repository:
        raise ValueError("--repository is required with --pr-number")
    if not args.github_token:
        raise ValueError("--github-token or GITHUB_TOKEN is required with --pr-number")

    github = GitHubPullRequestClient(
        repository=args.repository,
        token=args.github_token,
        api_url=args.github_api_url,
    )
    files = github.list_changed_addon_files(args.pr_number)
    reviewer = AddonTagReviewer()
    results: list[FileReviewResult] = []
    suggestions: list[TagSuggestion] = []

    suggester: OpenAICompatibleTagSuggester | None = None
    if args.ai_review:
        if args.model_base_url and args.model_api_key and args.model_name:
            suggester = OpenAICompatibleTagSuggester(
                base_url=args.model_base_url,
                api_key=args.model_api_key,
                model=args.model_name,
                readme_limit=args.readme_limit,
            )
        else:
            logger.warning(
                "AI review requested but AI_REVIEW_BASE_URL, AI_REVIEW_API_KEY, "
                "or AI_REVIEW_MODEL is missing"
            )

    for file_info in files:
        path = Path(file_info["filename"])
        text = github.fetch_pr_file_text(file_info)
        result = reviewer.review_text(path, text)
        results.append(result)

        if args.ai_review:
            if not suggester:
                suggestions.append(
                    TagSuggestion(
                        path=path,
                        repo=result.repo,
                        suggested_tags=[],
                        confidence="low",
                        reason="AI review is not configured.",
                        error="missing model configuration",
                    )
                )
                continue
            try:
                readme = github.fetch_readme(result.repo, args.readme_limit)
                suggestions.append(
                    suggester.suggest(
                        repo=result.repo,
                        path=path,
                        current_tags=result.current_tags,
                        readme=readme,
                    )
                )
            except Exception as exc:
                suggestions.append(
                    TagSuggestion(
                        path=path,
                        repo=result.repo,
                        suggested_tags=[],
                        confidence="low",
                        reason="AI tag suggestion failed.",
                        error=str(exc),
                    )
                )

    return results, suggestions


def main() -> int:
    """CLI entry point used by GitHub Actions workflows."""
    args = parse_args()

    import logging

    setup_logging(level=getattr(logging, args.log_level))

    if args.pr_number:
        results, suggestions = _review_pull_request(args)
    else:
        file_paths = [Path(path) for path in args.files or [] if path]
        if not file_paths:
            logger.info("No addon files to review")
            if args.summary_file:
                Path(args.summary_file).write_text(render_summary([]), encoding="utf-8")
            return 0

        reviewer = AddonTagReviewer()
        results = []
        suggestions = []
        for path in file_paths:
            if not path.exists():
                logger.info(f"Skipping deleted or missing addon file: {path}")
                continue
            logger.info(f"Reviewing addon tags: {path}")
            results.append(reviewer.review_file(path))

    if not results:
        logger.info("No addon files to review")
        if args.summary_file:
            Path(args.summary_file).write_text(render_summary([]), encoding="utf-8")
        return 0

    summary = render_summary(results, suggestions)
    print(summary)
    if args.summary_file:
        Path(args.summary_file).write_text(summary, encoding="utf-8")
    if args.post_comment and args.pr_number:
        github = GitHubPullRequestClient(
            repository=args.repository,
            token=args.github_token,
            api_url=args.github_api_url,
        )
        github.upsert_pr_comment(args.pr_number, f"{COMMENT_MARKER}\n{summary}")

    failures = [result for result in results if not result.ok]
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""CLI helpers for validating addon tag metadata."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config.tags import ADDON_TAGS, MAX_ADDON_TAGS, VALID_ADDON_TAGS, normalize_tags
from .utils.logging import get_logger, setup_logging

logger = get_logger("tag_review")


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


class AddonTagReviewer:
    """Validate addon tags locally."""

    def review_file(self, path: Path) -> FileReviewResult:
        """Review a single addon config file."""
        try:
            entry = AddonConfigEntry.load(path)
            messages = self._validate(entry)
        except Exception as exc:
            return FileReviewResult(
                path=path,
                repo=path.name.replace("@", "/", 1),
                status="failed",
                current_tags=[],
                messages=[str(exc)],
            )

        if messages:
            return FileReviewResult(
                path=path,
                repo=entry.repo,
                status="failed",
                current_tags=entry.tags,
                messages=messages,
            )

        return FileReviewResult(
            path=path,
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
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level",
    )
    return parser.parse_args()


def render_summary(results: list[FileReviewResult]) -> str:
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
    return "\n".join(lines)


def main() -> int:
    """CLI entry point used by GitHub Actions workflows."""
    args = parse_args()

    import logging

    setup_logging(level=getattr(logging, args.log_level))

    file_paths = [Path(path) for path in args.files or [] if path]
    if not file_paths:
        logger.info("No addon files to review")
        if args.summary_file:
            Path(args.summary_file).write_text(render_summary([]), encoding="utf-8")
        return 0

    reviewer = AddonTagReviewer()
    results: list[FileReviewResult] = []
    for path in file_paths:
        if not path.exists():
            logger.info(f"Skipping deleted or missing addon file: {path}")
            continue
        logger.info(f"Reviewing addon tags: {path}")
        results.append(reviewer.review_file(path))

    summary = render_summary(results)
    print(summary)
    if args.summary_file:
        Path(args.summary_file).write_text(summary, encoding="utf-8")

    failures = [result for result in results if not result.ok]
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

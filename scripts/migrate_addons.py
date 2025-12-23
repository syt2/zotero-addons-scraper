#!/usr/bin/env python3
"""
Migrate addons/*.json from old format to simplified format.

Old format:
{
  "repo": "owner/name",
  "releases": [
    {"targetZoteroVersion": "7", "tagName": "latest"},
    {"targetZoteroVersion": "6", "tagName": "v1.0.0"}
  ]
}

New format:
{
  "repo": "owner/name"
}

The release information is now managed by release_cache.json instead.

Usage:
    python scripts/migrate_addons.py --input addons --output addons_new
    python scripts/migrate_addons.py --input addons --in-place
"""

import argparse
import json
import shutil
from pathlib import Path


def migrate_addon_file(input_path: Path, output_path: Path) -> bool:
    """Migrate a single addon config file.

    Args:
        input_path: Path to input file.
        output_path: Path to output file.

    Returns:
        True if migration was successful.
    """
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Extract only the repo field
        repo = data.get("repo")
        if not repo:
            print(f"  Warning: {input_path.name} has no 'repo' field, skipping")
            return False

        new_data = {"repo": repo}

        # Write output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(new_data, f, ensure_ascii=False, indent=2)
            f.write("\n")

        return True
    except Exception as e:
        print(f"  Error processing {input_path.name}: {e}")
        return False


def migrate_all(input_dir: Path, output_dir: Path, in_place: bool = False) -> dict:
    """Migrate all addon config files.

    Args:
        input_dir: Input directory containing addon configs.
        output_dir: Output directory for migrated configs.
        in_place: If True, overwrite original files.

    Returns:
        Statistics dict.
    """
    stats = {"total": 0, "migrated": 0, "skipped": 0, "errors": 0}

    if not input_dir.exists():
        print(f"Error: Input directory not found: {input_dir}")
        return stats

    json_files = list(input_dir.glob("*.json"))
    stats["total"] = len(json_files)

    print(f"Found {len(json_files)} addon config files")

    for json_file in sorted(json_files):
        if in_place:
            output_path = json_file
        else:
            output_path = output_dir / json_file.name

        print(f"Processing {json_file.name}...")

        # Read and check if already migrated
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "releases" not in data:
            print(f"  Already in new format, skipping")
            stats["skipped"] += 1
            if not in_place:
                shutil.copy(json_file, output_path)
            continue

        if migrate_addon_file(json_file, output_path):
            stats["migrated"] += 1
            print(f"  Migrated successfully")
        else:
            stats["errors"] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Migrate addons/*.json to simplified format"
    )
    parser.add_argument(
        "--input",
        type=str,
        default="addons",
        help="Input directory (default: addons)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="addons_migrated",
        help="Output directory (default: addons_migrated)",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Modify files in place (overwrites original files)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )

    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)

    if args.dry_run:
        print("Dry run mode - no changes will be made")
        print(f"Input directory: {input_dir}")
        print(f"Output directory: {output_dir}")

        json_files = list(input_dir.glob("*.json"))
        print(f"\nWould process {len(json_files)} files:")

        for json_file in sorted(json_files):
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "releases" in data:
                releases = data.get("releases", [])
                print(f"  {json_file.name}: would remove {len(releases)} releases")
            else:
                print(f"  {json_file.name}: already migrated")
        return

    if args.in_place:
        confirm = input(
            f"This will modify files in {input_dir} in place. Continue? [y/N] "
        )
        if confirm.lower() != "y":
            print("Aborted")
            return

    stats = migrate_all(input_dir, output_dir, in_place=args.in_place)

    print(f"\nMigration complete:")
    print(f"  Total files: {stats['total']}")
    print(f"  Migrated: {stats['migrated']}")
    print(f"  Skipped (already new format): {stats['skipped']}")
    print(f"  Errors: {stats['errors']}")

    if not args.in_place:
        print(f"\nMigrated files are in: {output_dir}")
        print("To use them, run:")
        print(f"  rm -rf {input_dir} && mv {output_dir} {input_dir}")


if __name__ == "__main__":
    main()

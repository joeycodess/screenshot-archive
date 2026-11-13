"""Archive PNG and JPEG screenshots by UTC modification date."""
import argparse
import csv
import hashlib
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path


FIELDS = ("source", "destination", "status", "detail")


def fingerprint(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def archive_file(source, archive, dry_run, planned):
    with source.open("rb") as stream:
        header = stream.read(8)
    expected = b"\x89PNG\r\n\x1a\n" if source.suffix.lower() == ".png" else b"\xff\xd8\xff"
    if not header.startswith(expected):
        raise ValueError("file signature does not match the extension")

    stamp = datetime.fromtimestamp(source.stat().st_mtime, timezone.utc)
    digest = fingerprint(source)
    extension = ".png" if source.suffix.lower() == ".png" else ".jpg"
    folder = archive / f"{stamp:%Y}" / f"{stamp:%m}" / f"{stamp:%d}"
    target = folder / f"{stamp:%Y%m%dT%H%M%S}-{digest}{extension}"
    if not target.is_relative_to(archive) or folder.resolve() != folder:
        raise ValueError("archive date path must not contain symbolic links")

    def existing_status():
        if target.is_symlink() or not target.is_file() or fingerprint(target) != digest:
            raise ValueError("destination exists with different content or is not a regular file")
        return target, "already_archived"

    if target.exists() or target.is_symlink():
        return existing_status()
    if target in planned:
        return target, "duplicate_in_batch"
    if dry_run:
        planned.add(target)
        return target, "would_archive"

    folder.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=folder, prefix=".archive-") as staged:
        shutil.copyfile(source, staged.name)
        if fingerprint(Path(staged.name)) != digest:
            raise ValueError("source changed while it was being copied")
        try:
            os.link(staged.name, target)
        except FileExistsError:
            return existing_status()
    return target, "archived"


def run(source, archive, manifest, dry_run=False):
    source, archive = source.resolve(), archive.resolve()
    if not source.is_dir():
        raise ValueError("source must be an existing directory")
    if source.is_relative_to(archive) or archive.is_relative_to(source):
        raise ValueError("source and archive must be separate directory trees")
    if manifest.resolve().is_relative_to(source) or manifest.resolve().is_relative_to(archive):
        raise ValueError("manifest must be outside the source and archive trees")

    planned = set()
    rows = []
    with manifest.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(FIELDS)
        for path in sorted(source.iterdir()):
            if path.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                continue
            try:
                if path.is_symlink() or not path.is_file():
                    raise ValueError("input must be a regular file")
                target, status = archive_file(path, archive, dry_run, planned)
                row = (path.name, target.relative_to(archive).as_posix(), status, "")
            except (OSError, ValueError) as error:
                row = (path.name, "", "error", str(error))
            writer.writerow(row)
            stream.flush()
            rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--manifest", required=True, type=Path, help="new CSV path outside both directory trees")
    parser.add_argument("--dry-run", action="store_true", help="write a manifest without creating archive files")
    args = parser.parse_args()
    try:
        rows = run(args.source, args.archive, args.manifest, args.dry_run)
    except (OSError, ValueError) as error:
        parser.exit(2, f"archive: {error}\n")
    from collections import Counter
    counts = Counter(row[2] for row in rows)
    print(", ".join(f"{status}={count}" for status, count in sorted(counts.items())) or "No supported inputs")
    return int(bool(counts["error"]))


if __name__ == "__main__":
    raise SystemExit(main())

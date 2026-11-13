# Screenshot Archive

A dependency-free Python CLI that copies PNG and JPEG screenshots into a UTC date hierarchy, names them deterministically, and records the result for each input. This is a standalone work sample using synthetic data.

## Run the demo

Requires Python 3.11+ and a destination filesystem that supports hard links.

```sh
demo=$(mktemp -d)
python3 make_fixtures.py "$demo/inbox"
python3 screenshot_archive.py "$demo/inbox" "$demo/archive" --manifest "$demo/plan.csv" --dry-run
python3 screenshot_archive.py "$demo/inbox" "$demo/archive" --manifest "$demo/apply.csv"
python3 screenshot_archive.py "$demo/inbox" "$demo/archive" --manifest "$demo/repeat.csv"
cat "$demo/repeat.csv"
```

The three commands report `would_archive=12`, `archived=12`, and `already_archived=12`. A dry run creates only its CSV. Source files stay in place throughout.

## Behavior

- Input is the top level of one directory. Supported extensions are PNG, JPG and JPEG. The CLI checks the file signature. It does not decode or repair images.
- The UTC modification time determines the date and timestamp. It may differ from capture time. Each destination name also includes the full SHA-256 digest, so different files with the same timestamp receive different paths. The same timestamp and content produce the same path.
- Files are copied to a temporary file, checked against the source digest, then published with an exclusive hard link. An existing destination with different content is reported and left untouched. A rerun uses a new manifest and skips byte-identical destinations.
- The manifest records source filename, relative destination, status, and diagnostic detail. It must be a new path outside both directory trees. Exit status is 0 for a completed run without row errors, 1 for a completed run with row errors, or 2 for a setup or command error.

## Verification and benchmark

```sh
python3 -m unittest -v
python3 benchmark.py --count 1000 --repeats 3
```

The benchmark times the CLI process from launch through archive and CSV writes. It generates one synthetic dataset before timing, uses a fresh archive for each run, and verifies the copied bytes and unchanged archive on rerun after timing.

On Apple Silicon macOS, Python 3.13.2, the three runs took 1.720, 1.698, and 1.694 seconds. Median time was **1.698 seconds for 1,000 synthetic PNGs**, with **zero additional copies on rerun**. See [raw results](benchmark-results.txt). This is a local sample-data measurement without a manual baseline.

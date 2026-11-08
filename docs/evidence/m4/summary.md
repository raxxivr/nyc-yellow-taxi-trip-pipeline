# M4 Verification Summary

## Full pipeline

`python run_pipeline.py` completed successfully twice from the repository root.
The two logs are byte-for-byte identical.

- Raw rows: 3,876,044
- Clean rows: 3,784,607
- Rejected rows: 91,437
- Zero-distance rows flagged: 143,191
- Analytics rows: daily 30, top zones 10, tip-by-hour 24, payment type 6

All 9 quality checks passed on both runs.

## Fresh-clone verification

The committed repository was cloned into a temporary directory. A new virtual
environment was created, `requirements.txt` was installed, `.env` was supplied,
and `python run_pipeline.py` completed successfully with the same output as the
repository-root run.

The temporary clone was deleted after verification.

## Raw data and repository hygiene

- Raw files are only downloaded by `extract.py`; the load, transform, and
  analytics stages do not modify them.
- SHA-256 hashes of `data/raw/` were unchanged after a load run.
- No `.env`, `data/`, parquet, or CSV files are tracked by git.
- `clean` and `analytics` column names are snake_case.

## Evidence files

- `run-1.txt`, `run-2.txt` — full pipeline runs
- `fresh-clone-run.txt` — clean-clone run
- `quality-checks-run-1.txt`, `quality-checks-run-2.txt`
- `quality-checks-fresh-clone.txt`
- `raw-files-before.txt`, `raw-files-after.txt`
- `raw-immutability-load.txt`

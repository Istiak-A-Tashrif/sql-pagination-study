# Backend evidence and analysis

The accepted collection is recorded in raw/collections.jsonl. Only a completed, fully guarded collection enters analysis; attempted data are never silently substituted. The frozen manifest is ../manifest.json, with code/protocol hashes in the collection environment record.

From the repository root:

```sh
python3 -m venv .venv
.venv/bin/pip install -r results/requirements.txt
.venv/bin/python backend-study/analyze.py
PANDOC=/path/to/pandoc TECTONIC=/path/to/tectonic .venv/bin/python backend-study/manuscript/build.py
```

These commands regenerate analysis/figures/documents without any benchmark. `BACKEND_PYTHON="$PWD/.venv/bin/python" backend-study/reproduce` performs a new guarded collection first. Install Pandoc and Tectonic or set their environment paths. The same pinned Python dependencies are shared with the existing browser project; no browser observations are used.

Raw schemas:

- environment-COLLECTION.json: host/Docker/client versions, source/dump/manifest hashes and starting Git commit.
- batches.jsonl: exact UTC start/end, guard state, commands and status for every setup/check/plan/measurement stage.
- correctness-COLLECTION.txt: independently counted relations, all-product and page-window oracle results, PostgreSQL settings and actual index definitions.
- plans-COLLECTION.txt: ninety SQL texts and complete EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) trees; explanatory single executions, not primary timing samples.
- requests.jsonl: client endpoint, IDs, selected products/digest, phase and treatment.
- api.jsonl: separate server audit with Redis outcome, query duration, serialization and lookup/write phases.
- trials.jsonl: three-request trial grouping, treatment, repetition and timestamps.
- events.jsonl: warm-up/completion markers.
- collections.jsonl: fully accepted collection IDs.

Derived outputs: complete cell summaries, per-trial JSON/CSV, all-request PASS audit, paired descriptive contrasts, plan summaries, early/late drift diagnostics, manuscript values and raw SHA-256 digests. The twenty trial means per cell are the bootstrap units. Conditional query/Redis timings are not independent engine timers or production hit estimates.

The selected depth windows are the same product IDs for both methods, but keyset assumes its cursor is already known. Generated ID replication preserves source structure and does not establish realism. No mixed-hit, write, freshness, concurrency, frontend or model experiment is included.

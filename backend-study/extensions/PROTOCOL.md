# Follow-up sensitivity experiments: protocol

These four experiments qualify the primary backend study (../PROTOCOL.md). They do not change it. The cells, seed and trial order are fixed in `build_manifest.py` and `manifest.json` (seed 20261022), and the manifest hash is recorded in the accepted collection record. This document describes that design; the primary study's matrix, statistics and integrity rules apply unchanged (twenty three-request trials per cell, 10,000-resample percentile bootstrap over trial means, no outlier deletion, fail-closed process guard, only fully accepted collections analysed).

Isolated Compose project `unibackendx`, own database volume, ports 24002/24003/25434. Same PostgreSQL 17.2, Node 22.23.0 and primary settings (shared_buffers 512 MB, work_mem 16 MB, JIT off, no parallel workers), except where an experiment states otherwise. No Redis.

| Id | Question | Cells |
|---|---|---|
| E1_cursor | What does keyset cost when its cursor must be discovered? | 3 designs x {OFFSET, keyset known cursor, keyset after an index-ordered OFFSET discovery query} x depths 0/50/95% (27) |
| E2_skew | Does the ordering hold on an independently generated heavy-tailed dataset? | `skew100000`: 3 designs x 2 methods x 3 depths (18) |
| E3_default_jit_parallel | Do default JIT/parallel settings change the deepest-page result? | `api_default` process, session options `-c jit=on -c max_parallel_workers_per_gather=2`: 3 designs x 2 methods x 95% (6) |
| E4_no_index | How dependent are the page-first designs on the child product_id indexes? | `noidx100000` (copy of `s100000` without the two child product_id indexes): 3 designs x 2 methods x 0/95% (12) |

Total 63 cells, 1,260 trials, 3,780 measured requests, two warm-up requests per cell.

## Datasets

`s100000` is built exactly like the primary 100,000-product schema (the base dump cloned 20 times with disjoint ID ranges). `skew100000` is generated with `setseed(0.20261022)`: 100,000 products, 200,000 users, 400,000 orders, 1,000,000 order items and 600,000 reviews. A child's product is `1 + (floor(100000 * u^a) * p) mod 100000` with `a` = 3 and `p` = 7919 for order items and `a` = 2 and `p` = 104729 for reviews; the primes are coprime to 100,000, so heavy products are spread across IDs. Fan-out statistics are recorded in the correctness log. `noidx100000` copies `s100000` and drops only the two child `product_id` indexes.

## Correctness and integrity

Every design/method is compared with a scalar correlated-subquery oracle over every product for `s100000` and `skew100000`, and over the first, middle and deepest pages for `noidx100000` (identical data to `s100000`, so the `s100000` oracle is used). During analysis every returned page's row digest must be identical across designs, methods and cursor modes within a schema and window, and `s100000`/`noidx100000` windows must agree.

## Timing

API service time covers route entry through response serialization and includes the discovery query when one runs. Cursor time is also logged separately. Baseline cells are re-measured in this collection; they are not taken from the primary collection.

## Reproduction

`python3 backend-study/extensions/run.py` (compose build, start, correctness, plans, measurement), then `python3 backend-study/extensions/analyze.py`. Raw files land in `extensions/results/raw`, derived files in `extensions/results/derived`.

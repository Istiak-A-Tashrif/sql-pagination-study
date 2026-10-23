# Backend query-design study: frozen protocol

## Scope and research questions

Working title: Query Design and Pagination Costs in PostgreSQL-Backed APIs: An Experimental Study. This is a new backend-only empirical study, not a split of the existing browser measurements. No browser endpoint, rendering comparison, predictive model, staleness, real network, queueing or concurrency experiment is included. Redis is a bounded implementation sensitivity, not a new cache mechanism or predictive break-even analysis.

RQ1: How do three equivalent aggregate-query designs affect API/database duration as data volume grows? RQ2: How do pagination depth and OFFSET versus existing-cursor keyset continuation interact with query design? RQ3: Do results change with page size, and what work remains for verified Redis misses/hits?

## Designs and correctness

Global pre-aggregation computes order/review aggregates independently before joining products. Page-first grouped aggregation materializes the requested product page, then groups only its children. Page-first lateral aggregation materializes the page and uses indexed per-product aggregates. All count distinct order IDs, average ratings independently, return the same columns and order by unique product ID. Invalid fan-out SQL is excluded from performance comparisons.

Every variant/method is compared over every product against scalar correlated-subquery SQL, with an additional nine page windows per scale. Actual output objects, including names/categories/count/rating/stock, must match exactly. Counts are independently queried from the new database. EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) is recorded separately from primary timings.

The unchanged 5k-product synthetic dump is expanded deterministically into schemas with 5k, 25k and 100k products by cloning relation blocks with disjoint ID ranges. Categories/tags remain shared in shape, reviews/orders/order items scale proportionally. This preserves the source fan-out distribution rather than claiming realistic new diversity. The SQL loader VACUUM ANALYZEs every scaled relation. All source child-key indexes are present.

## Primary and sensitivity matrices

Primary: 3 scales x 3 designs x 2 pagination methods x 3 depths = 54 cells, page size 25. Depths skip 0%, 50% or 95% of product IDs. Page-size sensitivity: 10 and 100 rows at the largest scale = 36 additional cells. Twenty repetitions/cell, each averaging three sequential requests; repeated requests within one trial are not independent observations. A globally shuffled manifest (seed 20261021) fixes order before timing. Two untimed warm-up requests per primary/size cell precede the sweep.

Keyset receives the predecessor product ID as an already-available cursor, selecting exactly the same product IDs as OFFSET. Cursor discovery cost is excluded. This is a continuation-cost comparison, not evidence that keyset supports arbitrary page-number jumps for free. Unique, immutable ID ordering and read-only data make the selected windows comparable.

Redis sensitivity: only largest scale, 95% depth, page size 25; all 3 designs and 2 pagination methods; off, compulsory miss and guaranteed hit = 18 cells, each with 20 three-request trials. Misses have distinct request namespaces; hits have a logged compulsory fill followed by the measured requests. No mixed-hit/popularity prediction, expiry, update or capacity experiment is claimed.

## Environment and timing

Isolated Compose project unibackend, bridge network and loopback ports 24001/25433/26380. PostgreSQL 17.2, Redis 7.4.2 and Node 22.23.0 API image. PostgreSQL shared_buffers=512MB, work_mem=16MB, JIT disabled, zero parallel workers/query, track_io_timing enabled. One API pool connection and one sequential client; no load/concurrency claims. Processes remain warm and OS/DB caches are not flushed. This is a warmed-buffer experiment, not cold-disk performance. Container/host versions and settings are recorded from the run.

Client elapsed time spans fetch through JSON decoding. Service time spans handler entry through response JSON serialization, excluding out-of-band hash/audit writing and response send. Database duration brackets the awaited pg query and includes driver/pool/link overhead. Redis lookup/parse/serialization/write and response serialization are separate fields. Logging and hashing after the service timer can affect client elapsed time; all treatments use identical instrumentation.

## Statistics and integrity

The statistical unit is a three-request trial mean. Report means and seeded 10,000-resample percentile bootstrap 95% CIs over the 20 trial means. Report within-repetition paired descriptive contrasts, not significance from CI overlap. Preserve raw request events, API events, plans, environment, manifest/source hashes and stage logs. Only fully accepted guarded collections enter analysis; interrupted/error collections remain archived and excluded. Report run-order drift without deleting noisy observations.

Before each stage and every 250 ms during it, pgrep must find no main research driver; errors fail closed. A match terminates the stage and stops ONLY unibackend API/DB/Redis, preventing orphan queries. Every stage has pre/post guard timestamps. Caffeinate follows the controller PID. No research-server access, main-repo edits, cachebed actions or measurement reuse is permitted.

## Reproduction

From the SUJ repository root: `python3 backend-study/run.py`. It performs setup, full correctness checks, query plans and collection. Raw files land under backend-study/results/raw. Existing raw collections are preserved; only a fully completed new collection is marked accepted. Run the analysis/export script after collection. Do not run while the main research driver is active.

# Second SUJ paper — backend/query study

Working directory remains the existing caching-research-suj repository. This directory contains new code and newly collected evidence for a backend query-design paper. The existing browser paper at manuscript/ and delivery/ is unchanged. Read PROTOCOL.md and SOURCE_MAP.md first.

`python3 backend-study/run.py` from the repository root starts only the isolated unibackend project, verifies every product and page window, records query plans, collects the frozen randomized experiment, and stops its own services. It refuses to run if the main research driver is active. PostgreSQL/Redis volumes and raw attempts remain available for audit.

The first complete collection has passed its SQL, request/cache and export checks. Read HANDOVER.md for measured findings, exact reproduction commands and remaining author/editor review items. The draft and its separate editorial package are under manuscript/ and delivery/. Fast-cell variation and single-session limitations are stated explicitly; no acceptance or universal performance claim is made.

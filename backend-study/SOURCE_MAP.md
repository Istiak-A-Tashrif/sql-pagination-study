# Source boundaries

This is the new backend/query study, inside the existing SUJ repository. The existing browser manuscript, results and editorial package remain separate and unchanged. The predictive TWEB repository is read-only and supplies no experiment results to this study.

Read-only historical reference: the original application in ../caching-research-62717afc552df1eab3564d49986f5bae4ba1f276. Its faulty join and original timings are not performance baselines. The shared synthetic dump comes from app/generated_test_data_dump.sql. It is reused as infrastructure and deterministically expanded; all backend measurement logs are newly collected here.

Three equivalent correct SQL variants are written independently for this study: global pre-aggregation, page-first grouped aggregation, and page-first indexed lateral aggregation. All return identical named columns in product-ID order. The oracle independently computes scalar correlated aggregates over every product and compares complete results and selected pagination windows.

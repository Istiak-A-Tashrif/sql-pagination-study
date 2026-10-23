# Five independent raw-evidence checks

Computed directly from raw SQL/API/plan logs without importing analyze.py. The two service means match manuscript Table 1 after rounding. Product scan counts describe the representative plans; the cache check covers every measured hit.

```text
1. Largest independently counted product total: 100000
2 global offset service sum 17098.039422000074 requests 60 mean 284.96732370000126
3 page_lateral keyset service sum 26.445586000034382 requests 60 mean 0.4407597666672397
4. Product scan output in lateral deep-page plans:
offset [(95025, 1)]
keyset [(25, 1)]
5. Measured cache hits: 360 database queries: 0
```

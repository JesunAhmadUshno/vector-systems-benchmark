| Backend | Unfiltered recall@10 | Unfiltered p95 ms | Tight filter recall@10 | Tight shortfall | Post-churn recall drop | Hybrid nDCG@10 (dense to hybrid) |
|---|---|---|---|---|---|---|
| faiss | 0.967 | 0.47 | 0.413 | 0.267 | 0.009 | 0.374 to 0.421 |
| pgvector | 0.978 | 3.05 | 1.000 | 0.000 | 0.002 | 0.375 to 0.392 |
| qdrant | 1.000 | 299.53 | 1.000 | 0.000 | 0.000 | 0.387 to 0.456 |

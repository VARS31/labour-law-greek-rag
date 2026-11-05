# 2026-11-05_retrieval-bge-m3-rrf-limit4-dev

{"split": "dev", "system": "one-shot", "fusion": "rrf", "max_per_document": 4, "embedding": "bge-m3", "retrieval_only": true, "context_chunks": 8, "pool": 30}

| Category | Questions | Recall@8 | Recall@50 | MRR | Median time (s) |
|---|---:|---:|---:|---:|---:|
| all | 32 | 59% | 89% | 0.36 | 0.034 |
| single_source | 15 | 67% | 87% | 0.45 | 0.034 |
| sector_trap | 4 | 75% | 100% | 0.47 | 0.034 |
| vocabulary | 4 | 0% | 75% | 0.05 | 0.035 |
| follow_reference | 2 | 50% | 100% | 0.10 | 0.035 |
| must_refuse | 5 | - | - | - | 0.03 |
| exact_lookup | 2 | 100% | 100% | 0.29 | 0.032 |

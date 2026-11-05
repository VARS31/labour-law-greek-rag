# 2026-11-05_retrieval-bge-m3-rrf-limit2-dev

{"split": "dev", "system": "one-shot", "fusion": "rrf", "max_per_document": 2, "embedding": "bge-m3", "retrieval_only": true, "context_chunks": 8, "pool": 30}

| Category | Questions | Recall@8 | Recall@50 | MRR | Median time (s) |
|---|---:|---:|---:|---:|---:|
| all | 32 | 48% | 89% | 0.36 | 0.033 |
| single_source | 15 | 60% | 87% | 0.45 | 0.034 |
| sector_trap | 4 | 75% | 100% | 0.47 | 0.034 |
| vocabulary | 4 | 0% | 75% | 0.05 | 0.033 |
| follow_reference | 2 | 0% | 100% | 0.10 | 0.034 |
| must_refuse | 5 | - | - | - | 0.032 |
| exact_lookup | 2 | 50% | 100% | 0.29 | 0.034 |

# 2026-11-05_retrieval-bge-m3-semantic-limit4-dev

{"split": "dev", "system": "one-shot", "fusion": "semantic", "max_per_document": 4, "embedding": "bge-m3", "retrieval_only": true, "context_chunks": 8, "pool": 30}

| Category | Questions | Recall@8 | Recall@50 | MRR | Median time (s) |
|---|---:|---:|---:|---:|---:|
| all | 32 | 70% | 96% | 0.53 | 0.032 |
| single_source | 15 | 73% | 93% | 0.58 | 0.034 |
| sector_trap | 4 | 75% | 100% | 0.39 | 0.032 |
| vocabulary | 4 | 50% | 100% | 0.54 | 0.032 |
| follow_reference | 2 | 100% | 100% | 0.67 | 0.033 |
| must_refuse | 5 | - | - | - | 0.031 |
| exact_lookup | 2 | 50% | 100% | 0.29 | 0.031 |

# 2026-11-05_retrieval-qwen3-4b-rrf-limit4-dev

{"split": "dev", "system": "one-shot", "fusion": "rrf", "max_per_document": 4, "embedding": "qwen3-4b", "retrieval_only": true, "context_chunks": 8, "pool": 30}

| Category | Questions | Recall@8 | Recall@50 | MRR | Median time (s) |
|---|---:|---:|---:|---:|---:|
| all | 32 | 63% | 96% | 0.38 | 0.126 |
| single_source | 15 | 67% | 100% | 0.43 | 0.127 |
| sector_trap | 4 | 75% | 100% | 0.65 | 0.13 |
| vocabulary | 4 | 25% | 100% | 0.12 | 0.119 |
| follow_reference | 2 | 50% | 50% | 0.08 | 0.128 |
| must_refuse | 5 | - | - | - | 0.118 |
| exact_lookup | 2 | 100% | 100% | 0.29 | 0.121 |

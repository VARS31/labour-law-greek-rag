# 2026-11-04_retrieval-qwen3-4b-limit2-dev

{"split": "dev", "max_per_document": 2, "embedding": "qwen3-4b", "retrieval_only": true, "context_chunks": 8, "pool": 30}

| Category | Questions | Recall@8 | Recall@50 | MRR | Median time (s) |
|---|---:|---:|---:|---:|---:|
| all | 32 | 52% | 96% | 0.38 | 0.159 |
| single_source | 15 | 53% | 100% | 0.43 | 0.167 |
| sector_trap | 4 | 75% | 100% | 0.65 | 0.17 |
| vocabulary | 4 | 25% | 100% | 0.12 | 0.155 |
| follow_reference | 2 | 0% | 50% | 0.08 | 0.163 |
| must_refuse | 5 | - | - | - | 0.143 |
| exact_lookup | 2 | 100% | 100% | 0.29 | 0.145 |

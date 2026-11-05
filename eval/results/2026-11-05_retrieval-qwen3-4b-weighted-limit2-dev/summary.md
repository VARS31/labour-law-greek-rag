# 2026-11-05_retrieval-qwen3-4b-weighted-limit2-dev

{"split": "dev", "system": "one-shot", "fusion": "weighted", "max_per_document": 2, "embedding": "qwen3-4b", "retrieval_only": true, "context_chunks": 8, "pool": 30}

| Category | Questions | Recall@8 | Recall@50 | MRR | Median time (s) |
|---|---:|---:|---:|---:|---:|
| all | 32 | 70% | 100% | 0.48 | 0.124 |
| single_source | 15 | 80% | 100% | 0.57 | 0.125 |
| sector_trap | 4 | 75% | 100% | 0.66 | 0.13 |
| vocabulary | 4 | 25% | 100% | 0.17 | 0.123 |
| follow_reference | 2 | 50% | 100% | 0.18 | 0.127 |
| must_refuse | 5 | - | - | - | 0.115 |
| exact_lookup | 2 | 100% | 100% | 0.38 | 0.121 |

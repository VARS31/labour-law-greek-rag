# 2026-11-05_retrieval-qwen3-4b-rrf-limit2-dev

{"split": "dev", "system": "one-shot", "fusion": "rrf", "max_per_document": 2, "embedding": "qwen3-4b", "retrieval_only": true, "context_chunks": 8, "pool": 30}

| Category | Questions | Recall@8 | Recall@50 | MRR | Median time (s) |
|---|---:|---:|---:|---:|---:|
| all | 32 | 52% | 96% | 0.38 | 0.125 |
| single_source | 15 | 53% | 100% | 0.43 | 0.125 |
| sector_trap | 4 | 75% | 100% | 0.65 | 0.127 |
| vocabulary | 4 | 25% | 100% | 0.12 | 0.128 |
| follow_reference | 2 | 0% | 50% | 0.08 | 0.126 |
| must_refuse | 5 | - | - | - | 0.115 |
| exact_lookup | 2 | 100% | 100% | 0.29 | 0.122 |

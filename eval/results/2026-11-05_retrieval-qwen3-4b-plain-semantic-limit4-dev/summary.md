# 2026-11-05_retrieval-qwen3-4b-plain-semantic-limit4-dev

{"split": "dev", "system": "one-shot", "fusion": "semantic", "max_per_document": 4, "embedding": "qwen3-4b-plain", "retrieval_only": true, "context_chunks": 8, "pool": 30}

| Category | Questions | Recall@8 | Recall@50 | MRR | Median time (s) |
|---|---:|---:|---:|---:|---:|
| all | 32 | 85% | 96% | 0.63 | 0.121 |
| single_source | 15 | 93% | 100% | 0.86 | 0.122 |
| sector_trap | 4 | 100% | 100% | 0.40 | 0.124 |
| vocabulary | 4 | 75% | 100% | 0.45 | 0.117 |
| follow_reference | 2 | 50% | 100% | 0.16 | 0.124 |
| must_refuse | 5 | - | - | - | 0.111 |
| exact_lookup | 2 | 50% | 50% | 0.25 | 0.116 |

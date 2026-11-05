# 2026-11-05_retrieval-qwen3-4b-weighted-limit4-dev

{"split": "dev", "system": "one-shot", "fusion": "weighted", "max_per_document": 4, "embedding": "qwen3-4b", "retrieval_only": true, "context_chunks": 8, "pool": 30}

| Category | Questions | Recall@8 | Recall@50 | MRR | Median time (s) |
|---|---:|---:|---:|---:|---:|
| all | 32 | 74% | 100% | 0.48 | 0.126 |
| single_source | 15 | 87% | 100% | 0.57 | 0.129 |
| sector_trap | 4 | 75% | 100% | 0.66 | 0.125 |
| vocabulary | 4 | 25% | 100% | 0.17 | 0.122 |
| follow_reference | 2 | 50% | 100% | 0.18 | 0.126 |
| must_refuse | 5 | - | - | - | 0.116 |
| exact_lookup | 2 | 100% | 100% | 0.38 | 0.121 |

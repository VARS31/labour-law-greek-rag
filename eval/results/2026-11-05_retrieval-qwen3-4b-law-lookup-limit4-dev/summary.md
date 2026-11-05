# 2026-11-05_retrieval-qwen3-4b-law-lookup-limit4-dev

{"split": "dev", "system": "one-shot", "fusion": "law-lookup", "max_per_document": 4, "embedding": "qwen3-4b", "retrieval_only": true, "context_chunks": 8, "pool": 30}

| Category | Questions | Recall@8 | Recall@50 | MRR | Median time (s) |
|---|---:|---:|---:|---:|---:|
| all | 32 | 85% | 100% | 0.61 | 0.125 |
| single_source | 15 | 93% | 100% | 0.75 | 0.129 |
| sector_trap | 4 | 100% | 100% | 0.62 | 0.126 |
| vocabulary | 4 | 75% | 100% | 0.51 | 0.125 |
| follow_reference | 2 | 50% | 100% | 0.14 | 0.127 |
| must_refuse | 5 | - | - | - | 0.119 |
| exact_lookup | 2 | 50% | 100% | 0.27 | 0.121 |

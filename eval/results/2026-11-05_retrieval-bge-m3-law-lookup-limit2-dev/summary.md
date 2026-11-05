# 2026-11-05_retrieval-bge-m3-law-lookup-limit2-dev

{"split": "dev", "system": "one-shot", "fusion": "law-lookup", "max_per_document": 2, "embedding": "bge-m3", "retrieval_only": true, "context_chunks": 8, "pool": 30}

| Category | Questions | Recall@8 | Recall@50 | MRR | Median time (s) |
|---|---:|---:|---:|---:|---:|
| all | 32 | 63% | 96% | 0.53 | 0.035 |
| single_source | 15 | 67% | 93% | 0.58 | 0.034 |
| sector_trap | 4 | 50% | 100% | 0.39 | 0.032 |
| vocabulary | 4 | 50% | 100% | 0.54 | 0.043 |
| follow_reference | 2 | 100% | 100% | 0.67 | 0.039 |
| must_refuse | 5 | - | - | - | 0.033 |
| exact_lookup | 2 | 50% | 100% | 0.29 | 0.036 |

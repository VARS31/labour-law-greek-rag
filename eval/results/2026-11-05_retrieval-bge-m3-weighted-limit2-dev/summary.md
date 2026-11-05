# 2026-11-05_retrieval-bge-m3-weighted-limit2-dev

{"split": "dev", "system": "one-shot", "fusion": "weighted", "max_per_document": 2, "embedding": "bge-m3", "retrieval_only": true, "context_chunks": 8, "pool": 30}

| Category | Questions | Recall@8 | Recall@50 | MRR | Median time (s) |
|---|---:|---:|---:|---:|---:|
| all | 32 | 56% | 96% | 0.40 | 0.035 |
| single_source | 15 | 60% | 93% | 0.49 | 0.034 |
| sector_trap | 4 | 75% | 100% | 0.46 | 0.036 |
| vocabulary | 4 | 25% | 100% | 0.08 | 0.038 |
| follow_reference | 2 | 50% | 100% | 0.17 | 0.037 |
| must_refuse | 5 | - | - | - | 0.03 |
| exact_lookup | 2 | 50% | 100% | 0.42 | 0.032 |

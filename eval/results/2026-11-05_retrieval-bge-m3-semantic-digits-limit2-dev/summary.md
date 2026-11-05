# 2026-11-05_retrieval-bge-m3-semantic-digits-limit2-dev

{"split": "dev", "system": "one-shot", "fusion": "semantic", "number_rule": "digits", "max_per_document": 2, "embedding": "bge-m3", "retrieval_only": true, "context_chunks": 8, "pool": 30}

| Category | Questions | Recall@8 | Recall@50 | MRR | Median time (s) |
|---|---:|---:|---:|---:|---:|
| all | 32 | 67% | 96% | 0.53 | 0.033 |
| single_source | 15 | 73% | 93% | 0.58 | 0.033 |
| sector_trap | 4 | 50% | 100% | 0.39 | 0.034 |
| vocabulary | 4 | 50% | 100% | 0.54 | 0.037 |
| follow_reference | 2 | 100% | 100% | 0.67 | 0.034 |
| must_refuse | 5 | - | - | - | 0.03 |
| exact_lookup | 2 | 50% | 100% | 0.29 | 0.034 |

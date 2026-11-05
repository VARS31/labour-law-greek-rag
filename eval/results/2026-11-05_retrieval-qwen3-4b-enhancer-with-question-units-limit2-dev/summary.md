# 2026-11-05_retrieval-qwen3-4b-enhancer-with-question-units-limit2-dev

{"split": "dev", "system": "one-shot", "fusion": "semantic", "number_rule": "units", "enhancer": "with-question", "max_per_document": 2, "embedding": "qwen3-4b", "retrieval_only": true, "context_chunks": 8, "pool": 30}

| Category | Questions | Recall@8 | Recall@50 | MRR | Median time (s) |
|---|---:|---:|---:|---:|---:|
| all | 32 | 82% | 100% | 0.63 | 7.63 |
| single_source | 15 | 93% | 100% | 0.74 | 7.552 |
| sector_trap | 4 | 75% | 100% | 0.71 | 8.06 |
| vocabulary | 4 | 75% | 100% | 0.65 | 7.879 |
| follow_reference | 2 | 50% | 100% | 0.12 | 7.76 |
| must_refuse | 5 | - | - | - | 7.88 |
| exact_lookup | 2 | 50% | 100% | 0.08 | 8.668 |

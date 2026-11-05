# 2026-11-05_retrieval-qwen3-4b-enhancer-variants-units-limit2-dev

{"split": "dev", "system": "one-shot", "fusion": "semantic", "number_rule": "units", "enhancer": "variants", "max_per_document": 2, "embedding": "qwen3-4b", "retrieval_only": true, "context_chunks": 8, "pool": 30}

| Category | Questions | Recall@8 | Recall@50 | MRR | Median time (s) |
|---|---:|---:|---:|---:|---:|
| all | 32 | 78% | 93% | 0.57 | 7.516 |
| single_source | 15 | 87% | 93% | 0.68 | 7.422 |
| sector_trap | 4 | 100% | 100% | 0.75 | 7.942 |
| vocabulary | 4 | 50% | 100% | 0.46 | 7.766 |
| follow_reference | 2 | 50% | 100% | 0.12 | 7.641 |
| must_refuse | 5 | - | - | - | 7.733 |
| exact_lookup | 2 | 50% | 50% | 0.06 | 8.528 |

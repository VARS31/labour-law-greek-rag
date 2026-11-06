# 2026-11-06_oneshot-haiku-qwen3-4b-semantic-units-limit2-test

{"split": "test", "system": "oneshot-haiku", "fusion": "semantic", "number_rule": "units", "enhancer": null, "max_per_document": 2, "embedding": "qwen3-4b", "retrieval_only": false, "context_chunks": 8, "pool": 30, "model": "claude-haiku-5-5"}

| Category | Questions | Recall@8 | Recall@50 | MRR | Key facts | All facts | Gold law cited | Check passed | Correct refusals | Wrong refusals | Search problems | Reading problems | Median time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| all | 20 | 88% | 94% | 0.78 | 85% | 69% | 100% | 81% | 4 of 4 | 1 of 16 | 1 | 4 | 10.348 |
| single_source | 10 | 100% | 100% | 1.00 | 87% | 60% | 100% | 70% | 0 of 0 | 0 of 10 | 0 | 4 | 10.383 |
| sector_trap | 2 | 100% | 100% | 1.00 | 100% | 100% | 100% | 100% | 0 of 0 | 0 of 2 | 0 | 0 | 11.916 |
| vocabulary | 2 | 100% | 100% | 0.42 | 100% | 100% | 100% | 100% | 0 of 0 | 0 of 2 | 0 | 0 | 10.568 |
| follow_reference | 1 | 0% | 100% | 0.08 | - | - | - | - | 1 of 1 | 0 of 0 | 0 | 0 | 10.393 |
| must_refuse | 3 | - | - | - | - | - | - | - | 3 of 3 | 0 of 0 | 0 | 0 | 10.293 |
| exact_lookup | 2 | 50% | 50% | 0.17 | 50% | 50% | 100% | 100% | 0 of 0 | 1 of 2 | 1 | 0 | 7.947 |

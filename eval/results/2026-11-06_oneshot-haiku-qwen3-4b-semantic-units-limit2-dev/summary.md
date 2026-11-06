# 2026-11-06_oneshot-haiku-qwen3-4b-semantic-units-limit2-dev

{"split": "dev", "system": "oneshot-haiku", "fusion": "semantic", "number_rule": "units", "enhancer": null, "max_per_document": 2, "embedding": "qwen3-4b", "retrieval_only": false, "context_chunks": 8, "pool": 30, "model": "claude-haiku-5-5"}

| Category | Questions | Recall@8 | Recall@50 | MRR | Key facts | All facts | Gold law cited | Check passed | Correct refusals | Wrong refusals | Search problems | Reading problems | Median time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| all | 32 | 82% | 100% | 0.61 | 78% | 62% | 96% | 92% | 5 of 6 | 3 of 26 | 4 | 7 | 11.787 |
| single_source | 15 | 93% | 100% | 0.75 | 91% | 80% | 100% | 100% | 0 of 0 | 1 of 15 | 1 | 2 | 11.351 |
| sector_trap | 4 | 75% | 100% | 0.62 | 58% | 50% | 100% | 75% | 0 of 0 | 0 of 4 | 1 | 1 | 12.819 |
| vocabulary | 4 | 75% | 100% | 0.51 | 62% | 25% | 75% | 75% | 0 of 0 | 1 of 4 | 1 | 2 | 11.26 |
| follow_reference | 2 | 50% | 100% | 0.14 | 33% | 0% | 100% | 100% | 0 of 1 | 0 of 1 | 0 | 2 | 16.919 |
| must_refuse | 5 | - | - | - | - | - | - | - | 5 of 5 | 0 of 0 | 0 | 0 | 8.876 |
| exact_lookup | 2 | 50% | 100% | 0.27 | 67% | 50% | 100% | 100% | 0 of 0 | 1 of 2 | 1 | 0 | 12.949 |

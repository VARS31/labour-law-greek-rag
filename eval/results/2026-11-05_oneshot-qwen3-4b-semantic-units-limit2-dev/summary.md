# 2026-11-05_oneshot-qwen3-4b-semantic-units-limit2-dev

{"split": "dev", "system": "one-shot", "fusion": "semantic", "number_rule": "units", "enhancer": null, "max_per_document": 2, "embedding": "qwen3-4b", "retrieval_only": false, "context_chunks": 8, "pool": 30}

| Category | Questions | Recall@8 | Recall@50 | MRR | Key facts | All facts | Gold law cited | Check passed | Correct refusals | Wrong refusals | Search problems | Reading problems | Median time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| all | 32 | 82% | 100% | 0.61 | 68% | 46% | 96% | 42% | 4 of 6 | 0 of 26 | 3 | 13 | 62.738 |
| single_source | 15 | 93% | 100% | 0.75 | 81% | 67% | 100% | 53% | 0 of 0 | 0 of 15 | 1 | 4 | 60.312 |
| sector_trap | 4 | 75% | 100% | 0.62 | 54% | 25% | 100% | 0% | 0 of 0 | 0 of 4 | 1 | 2 | 74.78 |
| vocabulary | 4 | 75% | 100% | 0.51 | 25% | 0% | 75% | 50% | 0 of 0 | 0 of 4 | 1 | 3 | 66.36 |
| follow_reference | 2 | 50% | 100% | 0.14 | 67% | 0% | 100% | 100% | 0 of 1 | 0 of 1 | 0 | 2 | 81.314 |
| must_refuse | 5 | - | - | - | - | - | - | - | 4 of 5 | 0 of 0 | 0 | 1 | 40.994 |
| exact_lookup | 2 | 50% | 100% | 0.27 | 83% | 50% | 100% | 0% | 0 of 0 | 0 of 2 | 0 | 1 | 71.552 |

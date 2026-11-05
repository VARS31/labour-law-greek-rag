# 2026-11-05_oneshot-qwen3-4b-semantic-units-limit2-test

{"split": "test", "system": "oneshot-v2", "fusion": "semantic", "number_rule": "units", "enhancer": null, "max_per_document": 2, "embedding": "qwen3-4b", "retrieval_only": false, "context_chunks": 8, "pool": 30}

| Category | Questions | Recall@8 | Recall@50 | MRR | Key facts | All facts | Gold law cited | Check passed | Correct refusals | Wrong refusals | Search problems | Reading problems | Median time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| all | 20 | 88% | 94% | 0.78 | 69% | 38% | 94% | 62% | 1 of 4 | 1 of 16 | 1 | 12 | 48.719 |
| single_source | 10 | 100% | 100% | 1.00 | 72% | 40% | 100% | 40% | 0 of 0 | 0 of 10 | 0 | 6 | 46.457 |
| sector_trap | 2 | 100% | 100% | 1.00 | 58% | 0% | 100% | 100% | 0 of 0 | 0 of 2 | 0 | 2 | 53.895 |
| vocabulary | 2 | 100% | 100% | 0.42 | 83% | 50% | 100% | 100% | 0 of 0 | 0 of 2 | 0 | 1 | 46.69 |
| follow_reference | 1 | 0% | 100% | 0.08 | - | - | - | - | 0 of 1 | 0 of 0 | 0 | 1 | 35.887 |
| must_refuse | 3 | - | - | - | - | - | - | - | 1 of 3 | 0 of 0 | 0 | 2 | 62.79 |
| exact_lookup | 2 | 50% | 50% | 0.17 | 50% | 50% | 50% | 100% | 0 of 0 | 1 of 2 | 1 | 0 | 44.034 |

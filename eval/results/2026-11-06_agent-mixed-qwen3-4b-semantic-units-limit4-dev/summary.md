# 2026-11-06_agent-mixed-qwen3-4b-semantic-units-limit4-dev

{"split": "dev", "system": "agent-mixed", "fusion": "semantic", "number_rule": "units", "enhancer": null, "max_per_document": 4, "embedding": "qwen3-4b", "retrieval_only": false, "context_chunks": 8, "pool": 30, "model": "claude-haiku-5-5", "judge": "local"}

| Category | Questions | Recall@8 | Recall@50 | MRR | Key facts | All facts | Gold law cited | Check passed | Correct refusals | Wrong refusals | Search problems | Reading problems | Median time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| all | 32 | 89% | 100% | 0.61 | 82% | 65% | 92% | 92% | 5 of 6 | 2 of 26 | 2 | 8 | 75.693 |
| single_source | 15 | 100% | 100% | 0.75 | 86% | 67% | 100% | 100% | 0 of 0 | 0 of 15 | 0 | 5 | 67.039 |
| sector_trap | 4 | 100% | 100% | 0.62 | 100% | 100% | 100% | 75% | 0 of 0 | 0 of 4 | 0 | 0 | 99.186 |
| vocabulary | 4 | 75% | 100% | 0.51 | 62% | 25% | 75% | 75% | 0 of 0 | 1 of 4 | 1 | 2 | 92.204 |
| follow_reference | 2 | 50% | 100% | 0.14 | 100% | 100% | 100% | 100% | 0 of 1 | 0 of 1 | 0 | 1 | 196.366 |
| must_refuse | 5 | - | - | - | - | - | - | - | 5 of 5 | 0 of 0 | 0 | 0 | 87.39 |
| exact_lookup | 2 | 50% | 100% | 0.27 | 50% | 50% | 50% | 100% | 0 of 0 | 1 of 2 | 1 | 0 | 179.698 |

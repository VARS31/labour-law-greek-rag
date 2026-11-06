# 2026-11-06_agent-haiku-qwen3-4b-semantic-units-limit4-dev

{"split": "dev", "system": "agent-haiku", "fusion": "semantic", "number_rule": "units", "enhancer": null, "max_per_document": 4, "embedding": "qwen3-4b", "retrieval_only": false, "context_chunks": 8, "pool": 30, "model": "claude-haiku-5-5"}

| Category | Questions | Recall@8 | Recall@50 | MRR | Key facts | All facts | Gold law cited | Check passed | Correct refusals | Wrong refusals | Search problems | Reading problems | Median time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| all | 32 | 93% | 100% | 0.61 | 85% | 69% | 96% | 85% | 5 of 6 | 0 of 26 | 1 | 8 | 19.898 |
| single_source | 15 | 100% | 100% | 0.75 | 92% | 80% | 100% | 87% | 0 of 0 | 0 of 15 | 0 | 3 | 19.735 |
| sector_trap | 4 | 100% | 100% | 0.62 | 83% | 75% | 100% | 75% | 0 of 0 | 0 of 4 | 0 | 1 | 20.081 |
| vocabulary | 4 | 75% | 100% | 0.51 | 54% | 25% | 75% | 75% | 0 of 0 | 0 of 4 | 1 | 2 | 23.363 |
| follow_reference | 2 | 50% | 100% | 0.14 | 67% | 0% | 100% | 100% | 0 of 1 | 0 of 1 | 0 | 2 | 24.477 |
| must_refuse | 5 | - | - | - | - | - | - | - | 5 of 5 | 0 of 0 | 0 | 0 | 7.12 |
| exact_lookup | 2 | 100% | 100% | 0.27 | 100% | 100% | 100% | 100% | 0 of 0 | 0 of 2 | 0 | 0 | 27.289 |

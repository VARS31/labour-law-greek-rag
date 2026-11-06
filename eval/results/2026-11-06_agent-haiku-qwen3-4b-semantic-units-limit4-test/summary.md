# 2026-11-06_agent-haiku-qwen3-4b-semantic-units-limit4-test

{"split": "test", "system": "agent-haiku", "fusion": "semantic", "number_rule": "units", "enhancer": null, "max_per_document": 4, "embedding": "qwen3-4b", "retrieval_only": false, "context_chunks": 8, "pool": 30, "model": "claude-haiku-5-5"}

| Category | Questions | Recall@8 | Recall@50 | MRR | Key facts | All facts | Gold law cited | Check passed | Correct refusals | Wrong refusals | Search problems | Reading problems | Median time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| all | 20 | 94% | 100% | 0.79 | 88% | 69% | 100% | 100% | 4 of 4 | 0 of 16 | 0 | 5 | 21.14 |
| single_source | 10 | 100% | 100% | 1.00 | 80% | 50% | 100% | 100% | 0 of 0 | 0 of 10 | 0 | 5 | 20.37 |
| sector_trap | 2 | 100% | 100% | 1.00 | 100% | 100% | 100% | 100% | 0 of 0 | 0 of 2 | 0 | 0 | 23.281 |
| vocabulary | 2 | 100% | 100% | 0.42 | 100% | 100% | 100% | 100% | 0 of 0 | 0 of 2 | 0 | 0 | 20.073 |
| follow_reference | 1 | 0% | 100% | 0.08 | - | - | - | - | 1 of 1 | 0 of 0 | 0 | 0 | 40.18 |
| must_refuse | 3 | - | - | - | - | - | - | - | 3 of 3 | 0 of 0 | 0 | 0 | 30.72 |
| exact_lookup | 2 | 100% | 100% | 0.24 | 100% | 100% | 100% | 100% | 0 of 0 | 0 of 2 | 0 | 0 | 10.783 |

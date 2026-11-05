# 2026-11-05_agent-3c1-qwen3-4b-semantic-units-limit4-dev

{"split": "dev", "system": "agent", "fusion": "semantic", "number_rule": "units", "enhancer": null, "max_per_document": 4, "embedding": "qwen3-4b", "retrieval_only": false, "context_chunks": 8, "pool": 30}

| Category | Questions | Recall@8 | Recall@50 | MRR | Key facts | All facts | Gold law cited | Check passed | Correct refusals | Wrong refusals | Search problems | Reading problems | Median time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| all | 32 | 89% | 100% | 0.61 | 78% | 62% | 92% | 50% | 5 of 6 | 1 of 26 | 2 | 9 | 141.223 |
| single_source | 15 | 100% | 100% | 0.75 | 90% | 80% | 100% | 60% | 0 of 0 | 0 of 15 | 0 | 3 | 134.933 |
| sector_trap | 4 | 100% | 100% | 0.62 | 92% | 75% | 100% | 50% | 0 of 0 | 0 of 4 | 0 | 1 | 166.255 |
| vocabulary | 4 | 75% | 100% | 0.51 | 38% | 0% | 75% | 0% | 0 of 0 | 0 of 4 | 1 | 3 | 190.533 |
| follow_reference | 2 | 50% | 100% | 0.14 | 67% | 0% | 100% | 100% | 0 of 1 | 0 of 1 | 0 | 2 | 322.376 |
| must_refuse | 5 | - | - | - | - | - | - | - | 5 of 5 | 0 of 0 | 0 | 0 | 110.93 |
| exact_lookup | 2 | 50% | 100% | 0.27 | 50% | 50% | 50% | 50% | 0 of 0 | 1 of 2 | 1 | 0 | 209.987 |

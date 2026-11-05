# 2026-11-05_agent-qwen3-4b-semantic-units-limit4-dev

{"split": "dev", "system": "agent", "fusion": "semantic", "number_rule": "units", "enhancer": null, "max_per_document": 4, "embedding": "qwen3-4b", "retrieval_only": false, "context_chunks": 8, "pool": 30}

| Category | Questions | Recall@8 | Recall@50 | MRR | Key facts | All facts | Gold law cited | Check passed | Correct refusals | Wrong refusals | Search problems | Reading problems | Median time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| all | 32 | 82% | 100% | 0.61 | 76% | 62% | 88% | 58% | 5 of 6 | 2 of 26 | 4 | 7 | 166.988 |
| single_source | 15 | 93% | 100% | 0.75 | 87% | 80% | 93% | 67% | 0 of 0 | 1 of 15 | 1 | 2 | 168.386 |
| sector_trap | 4 | 100% | 100% | 0.62 | 92% | 75% | 100% | 50% | 0 of 0 | 0 of 4 | 0 | 1 | 163.578 |
| vocabulary | 4 | 50% | 100% | 0.51 | 38% | 0% | 75% | 25% | 0 of 0 | 0 of 4 | 2 | 2 | 196.079 |
| follow_reference | 2 | 50% | 100% | 0.14 | 67% | 0% | 100% | 100% | 0 of 1 | 0 of 1 | 0 | 2 | 280.254 |
| must_refuse | 5 | - | - | - | - | - | - | - | 5 of 5 | 0 of 0 | 0 | 0 | 62.26 |
| exact_lookup | 2 | 50% | 100% | 0.27 | 50% | 50% | 50% | 50% | 0 of 0 | 1 of 2 | 1 | 0 | 120.408 |

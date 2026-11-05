# 2026-11-05_agent-3c1-qwen3-4b-semantic-units-limit4-test

{"split": "test", "system": "agent", "fusion": "semantic", "number_rule": "units", "enhancer": null, "max_per_document": 4, "embedding": "qwen3-4b", "retrieval_only": false, "context_chunks": 8, "pool": 30}

| Category | Questions | Recall@8 | Recall@50 | MRR | Key facts | All facts | Gold law cited | Check passed | Correct refusals | Wrong refusals | Search problems | Reading problems | Median time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| all | 20 | 82% | 100% | 0.79 | 66% | 31% | 88% | 62% | 3 of 4 | 2 of 16 | 2 | 10 | 118.131 |
| single_source | 10 | 90% | 100% | 1.00 | 62% | 20% | 90% | 60% | 0 of 0 | 1 of 10 | 1 | 7 | 127.775 |
| sector_trap | 2 | 100% | 100% | 1.00 | 71% | 0% | 100% | 0% | 0 of 0 | 0 of 2 | 0 | 2 | 115.783 |
| vocabulary | 2 | 50% | 100% | 0.42 | 50% | 50% | 50% | 100% | 0 of 0 | 1 of 2 | 1 | 0 | 198.115 |
| follow_reference | 1 | 0% | 100% | 0.08 | - | - | - | - | 0 of 1 | 0 of 0 | 0 | 1 | 89.545 |
| must_refuse | 3 | - | - | - | - | - | - | - | 3 of 3 | 0 of 0 | 0 | 0 | 291.67 |
| exact_lookup | 2 | 100% | 100% | 0.24 | 100% | 100% | 100% | 100% | 0 of 0 | 0 of 2 | 0 | 0 | 78.54 |

# 2026-11-04_oneshot-limit2-test

{"split": "test", "max_per_document": 2, "embedding": "bge-m3", "retrieval_only": false, "context_chunks": 8, "pool": 30}

| Category | Questions | Recall@8 | Recall@50 | MRR | Key facts | All facts | Gold law cited | Check passed | Correct refusals | Wrong refusals | Search problems | Reading problems | Median time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| all | 20 | 71% | 100% | 0.49 | 60% | 44% | 94% | 44% | 2 of 4 | 1 of 16 | 5 | 6 | 54.207 |
| single_source | 10 | 80% | 100% | 0.50 | 70% | 50% | 100% | 50% | 0 of 0 | 1 of 10 | 2 | 3 | 56.778 |
| sector_trap | 2 | 50% | 100% | 0.53 | 33% | 0% | 100% | 0% | 0 of 0 | 0 of 2 | 1 | 1 | 55.541 |
| vocabulary | 2 | 50% | 100% | 0.08 | 50% | 50% | 50% | 0% | 0 of 0 | 0 of 2 | 1 | 0 | 48.332 |
| follow_reference | 1 | 100% | 100% | 1.00 | - | - | - | - | 0 of 1 | 0 of 0 | 0 | 1 | 72.137 |
| must_refuse | 3 | - | - | - | - | - | - | - | 2 of 3 | 0 of 0 | 0 | 1 | 43.092 |
| exact_lookup | 2 | 50% | 100% | 0.53 | 50% | 50% | 100% | 100% | 0 of 0 | 0 of 2 | 1 | 0 | 45.333 |

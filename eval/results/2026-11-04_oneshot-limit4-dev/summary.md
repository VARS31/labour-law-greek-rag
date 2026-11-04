# 2026-11-04_oneshot-limit4-dev

{"split": "dev", "max_per_document": 4, "embedding": "bge-m3", "retrieval_only": false, "context_chunks": 8, "pool": 30}

| Category | Questions | Recall@8 | Recall@50 | MRR | Key facts | All facts | Gold law cited | Check passed | Correct refusals | Wrong refusals | Search problems | Reading problems | Median time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| all | 32 | 59% | 89% | 0.36 | 51% | 27% | 73% | 54% | 4 of 6 | 1 of 26 | 10 | 11 | 45.302 |
| single_source | 15 | 67% | 87% | 0.45 | 60% | 40% | 67% | 60% | 0 of 0 | 0 of 15 | 5 | 4 | 44.852 |
| sector_trap | 4 | 75% | 100% | 0.47 | 50% | 0% | 100% | 50% | 0 of 0 | 0 of 4 | 1 | 3 | 67.532 |
| vocabulary | 4 | 0% | 75% | 0.05 | 8% | 0% | 50% | 50% | 0 of 0 | 1 of 4 | 4 | 0 | 51.773 |
| follow_reference | 2 | 50% | 100% | 0.10 | 33% | 0% | 100% | 0% | 0 of 1 | 0 of 1 | 0 | 2 | 63.693 |
| must_refuse | 5 | - | - | - | - | - | - | - | 4 of 5 | 0 of 0 | 0 | 1 | 35.462 |
| exact_lookup | 2 | 100% | 100% | 0.29 | 83% | 50% | 100% | 50% | 0 of 0 | 0 of 2 | 0 | 1 | 43.415 |

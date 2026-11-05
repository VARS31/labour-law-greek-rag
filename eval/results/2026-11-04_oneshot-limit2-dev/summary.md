# 2026-11-04_oneshot-limit2-dev

{"split": "dev", "max_per_document": 2, "embedding": "bge-m3", "retrieval_only": false, "context_chunks": 8, "pool": 30}

| Category | Questions | Recall@8 | Recall@50 | MRR | Key facts | All facts | Gold law cited | Check passed | Correct refusals | Wrong refusals | Search problems | Reading problems | Median time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| all | 32 | 48% | 89% | 0.36 | 51% | 35% | 69% | 42% | 4 of 6 | 2 of 26 | 13 | 6 | 36.429 |
| single_source | 15 | 60% | 87% | 0.45 | 58% | 40% | 67% | 47% | 0 of 0 | 0 of 15 | 6 | 3 | 36.963 |
| sector_trap | 4 | 75% | 100% | 0.47 | 62% | 50% | 100% | 0% | 0 of 0 | 0 of 4 | 1 | 1 | 46.43 |
| vocabulary | 4 | 0% | 75% | 0.05 | 8% | 0% | 50% | 75% | 0 of 0 | 1 of 4 | 4 | 0 | 35.32 |
| follow_reference | 2 | 0% | 100% | 0.10 | 67% | 0% | 100% | 0% | 0 of 1 | 0 of 1 | 1 | 1 | 55.383 |
| must_refuse | 5 | - | - | - | - | - | - | - | 4 of 5 | 0 of 0 | 0 | 1 | 28.896 |
| exact_lookup | 2 | 50% | 100% | 0.29 | 50% | 50% | 50% | 50% | 0 of 0 | 1 of 2 | 1 | 0 | 25.07 |

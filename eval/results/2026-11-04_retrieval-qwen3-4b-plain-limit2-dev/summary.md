# 2026-11-04_retrieval-qwen3-4b-plain-limit2-dev

{"split": "dev", "max_per_document": 2, "embedding": "qwen3-4b-plain", "retrieval_only": true, "context_chunks": 8, "pool": 30}

| Category | Questions | Recall@8 | Recall@50 | MRR | Median time (s) |
|---|---:|---:|---:|---:|---:|
| all | 32 | 52% | 93% | 0.39 | 0.147 |
| single_source | 15 | 67% | 93% | 0.47 | 0.149 |
| sector_trap | 4 | 75% | 100% | 0.65 | 0.158 |
| vocabulary | 4 | 0% | 75% | 0.06 | 0.134 |
| follow_reference | 2 | 0% | 100% | 0.10 | 0.139 |
| must_refuse | 5 | - | - | - | 0.141 |
| exact_lookup | 2 | 50% | 100% | 0.19 | 0.141 |

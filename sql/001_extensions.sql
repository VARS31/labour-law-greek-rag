-- Extensions used by the project. Safe to run again.

CREATE EXTENSION IF NOT EXISTS vector;     -- pgvector: the vector type and similarity search
CREATE EXTENSION IF NOT EXISTS unaccent;   -- removes accents, so "άρθρο" and "αρθρο" match in keyword search

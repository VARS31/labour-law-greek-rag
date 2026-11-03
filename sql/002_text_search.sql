-- Full-text search configuration "greek_labour": Postgres' Greek configuration plus accent removal and a
-- stopword list. Safe to run again.
--
-- How a Greek word is processed: unaccent ("Άρθρο" -> "Αρθρο"), then the Greek Snowball stemmer, which
-- lowercases, drops the word if it is in greek_labour.stop ("αρθρο", "και", "περι", …) and otherwise reduces
-- it to its stem ("εργαζομένων" -> "εργαζομεν").
-- The stopword file lives in sql/greek_labour.stop and is mounted into the container by docker-compose.yml
-- (Postgres reads it from $SHAREDIR/tsearch_data/). Its words are lowercase and without accents, because the
-- stemmer checks stopwords after unaccent and lowercasing but before stemming.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_ts_dict WHERE dictname = 'greek_labour_stem') THEN
        CREATE TEXT SEARCH DICTIONARY greek_labour_stem (
            TEMPLATE = snowball,
            Language = greek,
            StopWords = greek_labour
        );
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'greek_labour') THEN
        CREATE TEXT SEARCH CONFIGURATION greek_labour (COPY = greek);
        ALTER TEXT SEARCH CONFIGURATION greek_labour
            ALTER MAPPING FOR word, hword, hword_part, asciiword, asciihword, hword_asciipart
            WITH unaccent, greek_labour_stem;
    END IF;
END
$$;

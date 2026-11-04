# Code tour

This page explains the code for someone who doesn't read Python. It covers everything built so far, in two
parts:

- **Phase 1A** turns the raw dataset into **5,740 clean, labelled chunks** of Greek labour law, saved in
  `data/processed/labour_chunks.jsonl`.
- **Phases 1B and 1C** store those chunks in a database, search them, and answer a question with one call
  to a local model, citing the chunks it used and checking those citations.

A few words used below:

- **Module**: one Python file. The shared modules live in the folder `labour_rag/`.
- **Script**: a file you run from the terminal. Scripts live in `scripts/` and use the modules.
- **Document**: one legal act from the dataset (a law, decree or ministerial decision).
- **Chunk**: a small piece of a document, usually one article, that search returns.
- **Marker**: the words that start an article, such as `Άρθρ.83.-`, `Άρθρο 5` or `Άρθρον μόνον`.
- **JSONL**: a text file with one record per line. Each line of `labour_chunks.jsonl` is one chunk.
- **Embedding**: a list of 1024 numbers that stands for the meaning of a text. Texts with similar meaning
  get similar numbers, so "search by meaning" compares these lists.
- **Prompt**: the written instructions the model gets before the question.

Every example on this page is real: it was copied from the data or from the output of the code.

## Phase 1A: the data flow

```
 data/raw/greek_legal_code/
 ├─ volume/   train, validation, test .parquet   the same 47,563 texts in all three
 ├─ chapter/  train, validation, test .parquet   folders; only the label differs
 └─ subject/  train, validation, test .parquet
        │
        │  dataset.py     join the three labels row by row, keep volume 41 (labour law)
        ▼
 1,284 documents (text + volume, chapter, subject)
        │
        │  normalize.py   fix the characters: µ→μ, τoυ→του, ΕΡΓ ΑΣΙΑΣ→ΕΡΓΑΣΙΑΣ, ΄Αρθρ→Άρθρ
        ▼
 1,284 normalised texts
        │
        │  noise.py       step 1: learn the running page titles from all texts (50 found)
        │                 step 2: remove the printed-page headers (1,959 blocks, 2.5% of the words)
        ▼
 1,284 clean texts
        │
        │  header.py      read act type, number, year, ΦΕΚ and title
        │  articles.py    find where each article starts
        │  chunking.py    cut, move headings, merge small pieces, split long ones, label
        ▼
 5,740 chunks
        │
        │  scripts/build_chunks.py writes the results
        ▼
 data/processed/labour_chunks.jsonl     the chunks, one per line
 data/processed/running_titles.json     the page titles that were removed
 docs/chunking-report.md                the report with numbers and real examples
```

`scripts/explore_data.py` reads the same parquet files, but only measures them (Phase 0). It doesn't feed
this pipeline.

## Phase 1A: the modules, in the order they run

### `labour_rag/dataset.py`: load the documents

**What it does:** reads the nine parquet files and puts the three labels of each document side by side.

- **In:** the folder `data/raw/greek_legal_code/`.
- **Out:** a list of documents, each with its text, its split and its volume, chapter and subject names.

**Example** (document 15034):

- Before: row 15,034 of `train.parquet` exists three times, once per folder, with the same text
  `14. ΝΟΜΟΣ υπ’ αριθ. 751 της 4/10 Αυγ. 1948 Περί προστασίας…`. The labels are only numbers:
  volume `41`, chapter `71`, subject `1683`.
- After: one document with `doc_id 15034`, split `train`, volume `ΕΡΓΑΤΙΚΗ ΝΟΜΟΘΕΣΙΑ`, chapter
  `ΠΡΟΣΤΑΣΙΑ ΠΡΟΣΩΠΩΝ ΕΙΔΙΚΩΝ ΚΑΤΗΓΟΡΙΩΝ`, subject
  `ΠΡΟΣΛΗΨΗ ΕΦΕΔΡΩΝ, ΑΝΑΠΗΡΩΝ ΠΟΛΕΜΟΥ, ΠΟΛΥΤΕΚΝΩΝ ΚΑΙ ΑΛΛΩΝ ΑΤΟΜΩΝ ΜΕ ΕΙΔΙΚΕΣ ΑΝΑΓΚΕΣ`.

**Tests:** none, because it needs the 460 MB download. It checks itself instead: if the three folders
don't hold the same texts in the same order, it stops with an error.

### `labour_rag/normalize.py`: fix the characters

**What it does:** makes sure the same word is always written with the same characters, so that search
can find it. The same module will clean user questions later.

- **In:** any text.
- **Out:** the cleaned text (and, for the report, a count of what changed).

It fixes letters that look right but are the wrong character: the micro sign `µ` instead of Greek `μ`,
Latin `o` inside a Greek word, a loose accent `΄` in front of a capital, capital words split by a stray
space, and a few rarer cases.

**Examples** (all from the labour texts):

| Before | After | What was wrong |
|---|---|---|
| `ΑΠΟΦΑΣΗ ΥΠΟΥΡΓΟΥ ΕΡΓ ΑΣΙΑΣ Αριθ. 50257` | `ΑΠΟΦΑΣΗ ΥΠΟΥΡΓΟΥ ΕΡΓΑΣΙΑΣ Αριθ. 50257` | a space inside the word (505 times) |
| `στην αίθουσα του Υπουργείoυ Εργασίας` | `στην αίθουσα του Υπουργείου Εργασίας` | a Latin `o` inside a Greek word |
| `των µερικώς απασχολουµένων` | `των μερικώς απασχολουμένων` | the micro sign `µ` instead of `μ` (262 times) |
| `διατάσσομεν: ΄Αρθρον μόνον.-Από` | `διατάσσομεν: Άρθρον μόνον.-Από` | a loose accent before the capital (180 times) |

**Tests:** `tests/test_normalize.py`, 20 tests. They check each kind of fix with real strings, and also
that things that must *not* change stay as they are: the ΦΕΚ sign in `ΦΕΚ Α΄ 57`, the unit `μg`, the pair
of real words `ΥΠΕΡ ΑΥΤΩΝ`, and an ordinary question typed by a user.

### `labour_rag/noise.py`: remove the printed-page headers

**What it does:** removes the page headers of the printed book, which ended up in the middle of the text.

- **In:** a normalised text, plus the list of running titles.
- **Out:** the clean text, plus a list of what was removed.

The texts come from a loose-leaf book. Each page header has a page number (`Σελ. 228`), an update issue
(`Τεύχος 1294-Σελ. 33`), a position code (`15.Λ.α.58`) and the title of the chapter printed at the top of
the page. The first three have a fixed shape and are always removed. Titles are ordinary Greek words, so
the module first **learns** them from the data: text that sits between two page markers, at least twice.
That gave 50 titles. A title is then removed only when it touches a page marker. Words that are not on
the list are never removed.

**Examples** (from the labour texts):

- Document 9103, a position code and a running title between two articles:
  - Before: `…(15. Αα. 1). 15.Μ.α.2 Εργατικά ατυχήματα Άρθρον 12 Η αποδεικτική δύναμις…`
  - After: `…(15. Αα. 1). Άρθρον 12 Η αποδεικτική δύναμις…`
- Document 16316, a page header that cut a word in two; the two halves are joined again:
  - Before: `…εις την γενικήν συνδιάσκεΣελ.70(α) Τεύχος1294-Σελ.2 ψιν έκθεσιν…`
  - After: `…εις την γενικήν συνδιάσκεψιν έκθεσιν…`

**Tests:** `tests/test_noise.py`, 10 tests. Among them: a full header in the middle of a sentence, a word
cut by a page break, cross-references that must stay (`ανωτ. σελ. 306,823`), unknown words that must
stay, and a form whose heading is also a chapter name and must not be deleted.

### `labour_rag/header.py`: read the header of each act

**What it does:** reads the first lines of a document and picks out what kind of act it is, its number,
year, ΦΕΚ and title. It also builds the short citation used in each chunk.

- **In:** the clean text of one document.
- **Out:** act type, abbreviation, number, year, ΦΕΚ, title (each one left empty when not found).

**Example** (document 6987):

- Before: `30. ΑΠΟΦΑΣΗ ΥΦΥΠΟΥΡΓΟΥ ΕΡΓΑΣΙΑΣ Αριθ. 12756 της 23 / 23 Μαρτ. 1989 (ΦΕΚ Β΄213) Δημοσίευση στην
  Εφημερίδα της Κυβερνήσεως της από 10.3.89 Εθνικής Γενικής Συλλογικής Σύμβασης Εργασίας (Ε.Γ.Σ.Σ.Ε.)
  έτους 1989. Έχοντας υπόψη: …`
- After: act type `Υπουργική απόφαση`, number `12756`, year `1989`, ΦΕΚ `Β΄ 213`, title
  `Δημοσίευση στην Εφημερίδα της Κυβερνήσεως της από 10.3.89 Εθνικής Γενικής Συλλογικής Σύμβασης
  Εργασίας (Ε.Γ.Σ.Σ.Ε.) έτους 1989`, citation `Υ.Α. 12756/1989`.

It found the act type and year for 99% of the documents and the ΦΕΚ for 69%. Most missing values are
truly missing: old acts often have no number or ΦΕΚ in their header.

**Tests:** `tests/test_header_and_chunking.py`, the 5 `Header` tests: a law, a joint ministerial
decision with ΦΕΚ, a number written without "Αριθ.", a decree with no numbered header, and a title that
contains an abbreviation (`Εθν.`) which must not end it.

### `labour_rag/articles.py`: find where each article starts

**What it does:** finds every article marker in a text and turns it into a clean label and number. It
ignores references to other laws.

- **In:** a clean text.
- **Out:** the position of each marker, with a label (`Άρθρο 83`) and its number (`83`).

The same article can be written in many ways: `Άρθρ.83.-`, `Άρθρο 83`, `Άρθρον 83`, `ΑΡΘΡΟ 83`,
`Άρθρον μόνον`, `Άρθρο πρώτο`, `Άρθρο ΙΙ`. A reference such as `του άρθρου 3` or `Άρθρο 3 της οδηγίας`
points to *another* text and is not a marker.

**Examples** (from the labour texts):

- Document 6121: `…του σχοινίου αναρτήσεως. Λίπανσις, καθαρισμός Άρθρ.83.-Επιδιόρθωσις και λίπανσις…`
  gives one marker: label `Άρθρο 83`, number `83`.
- Document 0: `Άρθρ.13-19.-(Καταργήθηκαν από την παρ. 3 άρθρ. 17 του Π.Δ. 94/10-22 Απρ. 1987 …)` gives one
  marker: label `Άρθρα 13-19`, numbers 13 to 19. The `άρθρ. 17` inside it is a reference and is ignored.

**Tests:** `tests/test_articles.py`, 10 tests: all the ways of writing a marker, damaged spellings,
ranges, a heading glued in front of a marker, and references that must not count. One of them guards
against a bug found in the Phase 0 version, which read `Άρθρο 3 της οδηγίας` as an article.

### `labour_rag/chunking.py`: cut each document into chunks and label them

**What it does:** cuts each clean document into chunks, tidies them and attaches all the labels.

- **In:** the clean text of one document, its header fields and its dataset labels.
- **Out:** a list of chunk records, ready to be written to the JSONL file.

The rules, in order:

1. Cut at article markers. The header and preamble before the first article is its own chunk.
2. A document without markers is cut at numbered paragraphs (`1.`, `2.`, `3.`) instead; failing that,
   by size. A short document without structure stays whole.
3. An article heading left at the end of the previous piece is moved to the article it belongs to.
4. A piece under 20 words is joined to the piece before it.
5. A piece over 500 words is cut into windows of at most 500 words that share about 50 words, so a
   sentence on the border is never lost.
6. Each chunk gets its labels, its flags and a *text to embed*: a short header plus the chunk text.

**Examples** (from the labour texts):

- Document 6121, rule 3. In this old decree the heading of an article comes *before* its marker.
  - Before: article 82 ends with `…του σχοινίου αναρτήσεως. Λίπανσις, καθαρισμός` and article 83 starts
    with `Άρθρ.83.-Επιδιόρθωσις και λίπανσις…`.
  - After: article 82 ends with `…του σχοινίου αναρτήσεως.` and article 83 starts with
    `Λίπανσις, καθαρισμός Άρθρ.83.-Επιδιόρθωσις και λίπανσις…`. This happened 1,222 times.
- Document 0, rule 4. The header (15 words) and the note `Άρθρ.13-19.-(Καταργήθηκαν …)` are both too
  short to stand alone. They are joined with article 1 into one chunk labelled
  `Προοίμιο, Άρθρο 1, Άρθρα 13-19`, and the repeal sentence is saved in its own field.

**Tests:** `tests/test_header_and_chunking.py`, the 4 `Rules` tests (window size and overlap, merging,
moving a heading, numbered paragraphs after the decision formula) and the 2 `Records` tests (flags,
repeal sentence and text to embed on two real documents).

### `labour_rag/__init__.py`

Marks the folder as one package. It contains no logic.

## Phase 1A: the scripts

### `scripts/build_chunks.py`: run Phase 1A

**What it does:** runs all the modules above, in order, on the labour-law volume and writes the results.

- **In:** the parquet files in `data/raw/greek_legal_code/`.
- **Out:** `data/processed/labour_chunks.jsonl`, `data/processed/running_titles.json` and
  `docs/chunking-report.md`.

**Example:** before, 1,284 documents (769,486 words) with page headers, broken characters and no line
breaks. After, 5,740 labelled chunks with a median of 81 words, in about five seconds. The report is
written by the script itself, so its numbers always match the file.

**Tests:** none of its own. It only connects modules that are tested, and the report it writes (15
random chunks and the 5 worst cases) is the check a person reads.

### `scripts/explore_data.py`: measure the dataset (Phase 0)

**What it does:** measures the whole dataset (47 volumes) and writes the numbers behind
`docs/data-exploration.md`.

- **In:** the parquet files.
- **Out:** `data/exploration/stats.json` and three sample texts.

**Example:** before, nine parquet files of about 460 MB. After, for instance, this summary for labour
law in `stats.json`: 1,284 documents, 769,486 words, about 5,300 chunks (the Phase 0 estimate).

**Tests:** none. It is a one-off measuring script. It keeps an older copy of the article pattern on
purpose, so that the Phase 0 numbers can be reproduced exactly.

## Phases 1B and 1C: from chunks to answers

```
 data/processed/labour_chunks.jsonl
        │
        │  load.py           store every chunk; get an embedding of its text from bge-m3 (model_client.py)
        ▼
 Postgres + pgvector (in Docker, port 5433), table "chunks":
 text and labels, the embedding (1024 numbers), the words for keyword search
        │
 question ─── normalize.py   the same cleaning as the chunks
        │
        │  search.py         search by meaning + search by words, combined (hybrid), top 30
        │  retrieve.py       skip near-identical chunks and a 3rd chunk from the same document → 8 chunks
        ▼
 8 numbered chunks [1]–[8] + the instructions in prompts/answer.md
        │
        │  model_client.py   ministral-3:8b writes the answer and cites [1]…[8]
        ▼
 answer
        │
        │  citations.py      does every [n] exist? is every «quote» really in its chunk?
        ▼
 answer + sources + citation check + time per step            (ask.py prints all of this)
```

### The modules

Each entry: what it does, then what goes in → what comes out.

- **`labour_rag/config.py`** reads the project's settings from the `.env` file.
  `.env` → the database address and password, the model names and their settings.
- **`labour_rag/db.py`** connects to the database and creates the tables from the files in `sql/`.
  settings + `sql/*.sql` → an open connection; the table, the Greek keyword-search setup and the indexes.
- **`labour_rag/model_client.py`** is the only place that talks to the models, through Ollama.
  texts → their embeddings; or instructions + question + chunks → the model's answer, with token counts
  and time.
- **`labour_rag/load.py`** puts the chunks into the database and embeds the ones that are new or changed.
  `labour_chunks.jsonl` → 5,740 rows in the table, each with its embedding.
- **`labour_rag/search.py`** searches three ways: by meaning, by words, and both combined.
  a question → three ranked lists of chunks with scores; as a command it prints them side by side.
- **`labour_rag/retrieve.py`** chooses the chunks the model will read.
  a question → 8 numbered chunks, plus the chunks it skipped and why (near-identical, or a third chunk
  from the same document).
- **`labour_rag/citations.py`** checks an answer against the chunks it was based on.
  answer + the 8 chunks → OK or failed, the list of failed citations (a number that doesn't exist, a quote
  without a source, a quote that isn't in its chunk) and warnings.
- **`labour_rag/ask.py`** runs the whole one-shot answer.
  a question → the answer with the closing note, its sources, the citation check and the time per step;
  as a command it prints them, and `--show-chunks` also shows exactly what the model received.

### The scripts

- **`scripts/search_report.py`** measures the database and compares the three search methods.
  the database + 8 example questions → `docs/search-report.md`.
- **`scripts/answer_report.py`** answers the same 8 questions and lays the results out for assessment.
  8 questions → `data/processed/answer_results.json` and `docs/answer-report.md`.

### Files that are not Python

- **`docker-compose.yml`** starts Postgres with pgvector in Docker. It reads the password from `.env`
  (template: `.env.example`).
- **`sql/001_extensions.sql` … `sql/004_hnsw_index.sql`** create the database step by step: extensions,
  the Greek keyword-search setup, the `chunks` table (every column has a comment) and the index for search
  by meaning. **`sql/greek_labour.stop`** lists the very common words keyword search ignores.
- **`prompts/answer.md`** holds the instructions for the model; **`prompts/closing_note.md`** the note
  every answer must end with. Both can be edited without touching any code.

**Tests:** `tests/test_search_parts.py` (settings, rank fusion) and `tests/test_answering.py` (choosing the
chunks, checking citations with the real Α.Ν. 539/1945 text). Searching and answering themselves need the
database and the model, so they are checked through the two reports instead.

## Running the tests

```bash
.venv/bin/python -m unittest discover -s tests -t .
```

A test is a small example with a known right answer: "this input must give exactly this output". There
are 76 of them, almost all with real strings from the data, and they run in under a second. If a later
change breaks one of the rules above, a test fails and says which one.

## How to explain Phase 1A in an interview

> I took 1,284 Greek labour-law documents, which came from the Word files of a printed loose-leaf book,
> and turned them into 5,740 labelled chunks ready for search, using plain rules and no AI. The text had
> no line breaks, page headers in the middle of sentences, Latin look-alike letters inside Greek words and
> articles out of order, so I first wrote a normalisation step that I will reuse on user questions. To
> remove page headers without losing law text, I learned the list of running titles from the data
> itself and only delete words that are on that list. Then I cut each document at its article markers,
> with fallbacks to numbered paragraphs or size, merged tiny pieces, split long ones with overlap, and
> labelled every chunk with the act, year, ΦΕΚ and article number. Every rule has unit tests with real
> examples, and the pipeline writes its own report with random and worst-case chunks so a person can
> check the result. The main lesson was to read the data before writing rules: that is how I found that
> article headings sit before their markers, and moved 1,222 of them to the right chunk.

## One chunk, field by field

This is one line of `data/processed/labour_chunks.jsonl`, spread over several lines to make it readable:

```json
{
  "id": "glc-10979-026",
  "doc_id": 10979,
  "seq": 26,
  "split": "train",
  "volume": "ΕΡΓΑΤΙΚΗ ΝΟΜΟΘΕΣΙΑ",
  "chapter": "ΥΓΙΕΙΝΗ ΚΑΙ ΑΣΦΑΛΕΙΑ ΕΡΓΑΖΟΜΕΝΩΝ",
  "subject": "ΥΓΙΕΙΝΗ ΚΑΙ ΑΣΦΑΛΕΙΑ ΧΩΡΩΝ ΕΡΓΑΣΙΑΣ ΚΑΙ ΕΡΓΑΖΟΜΕΝΩΝ",
  "act_type": "Προεδρικό διάταγμα",
  "act_abbr": "Π.Δ.",
  "act_number": "70",
  "year": 1990,
  "fek": "Α΄ 31",
  "title": "Υγιεινή και Ασφάλεια των Εργαζομένων σε ναυπηγικές εργασίες",
  "citation": "Π.Δ. 70/1990",
  "citation_fallback": false,
  "method": "article",
  "kind": "article",
  "article": "Άρθρο 28",
  "article_numbers": [28],
  "part": 1,
  "parts": 1,
  "words": 49,
  "is_stub": false,
  "is_note": false,
  "repeal_sentences": [],
  "text": "Εργασίες με αμίαντο Άρθρ.28.-Για την προστασία των εργαζομένων που εκτίθενται σε αμίαντο κατά την διάρκεια της εργασίας, όπως σε περίπτωση αποζημίωσης μονώσεων διαφραγμάτων, λεβήτων, σωληνώσεων κ.λπ. πρέπει να λαμβάνονται τα προβλεπόμενα μέτρα, που καθορίζονται στο Π.Δ. 70α «Προστασία των εργαζομένων, που εκτίθενται σε αμίαντο κατά την εργασία» (Α΄ 31).",
  "embed_text": "Π.Δ. 70/1990, Άρθρο 28, Υγιεινή και Ασφάλεια των Εργαζομένων σε ναυπηγικές εργασίες\nΕργασίες με αμίαντο Άρθρ.28.-Για την προστασία των εργαζομένων που εκτίθενται σε αμίαντο κατά την διάρκεια της εργασίας, όπως σε περίπτωση αποζημίωσης μονώσεων διαφραγμάτων, λεβήτων, σωληνώσεων κ.λπ. πρέπει να λαμβάνονται τα προβλεπόμενα μέτρα, που καθορίζονται στο Π.Δ. 70α «Προστασία των εργαζομένων, που εκτίθενται σε αμίαντο κατά την εργασία» (Α΄ 31)."
}
```

| Field | Value here | What it means |
|---|---|---|
| `id` | `glc-10979-026` | The chunk's name: document 10979, chunk number 26 of that document. It stays the same every time the pipeline runs on the same data. |
| `doc_id` | `10979` | Which document the chunk comes from. Same numbering as in Phase 0. |
| `seq` | `26` | The chunk's place inside its document, counting from 0. |
| `split` | `train` | Which part of the original dataset the document was in. It doesn't matter for search. |
| `volume` | `ΕΡΓΑΤΙΚΗ ΝΟΜΟΘΕΣΙΑ` | The broadest topic label from the dataset: labour law. |
| `chapter` | `ΥΓΙΕΙΝΗ ΚΑΙ ΑΣΦΑΛΕΙΑ ΕΡΓΑΖΟΜΕΝΩΝ` | The middle topic label: health and safety at work. |
| `subject` | `ΥΓΙΕΙΝΗ ΚΑΙ ΑΣΦΑΛΕΙΑ ΧΩΡΩΝ ΕΡΓΑΣΙΑΣ ΚΑΙ ΕΡΓΑΖΟΜΕΝΩΝ` | The narrowest topic label. |
| `act_type` | `Προεδρικό διάταγμα` | What kind of act this is, read from the header: a presidential decree. |
| `act_abbr` | `Π.Δ.` | The usual Greek abbreviation of that act type. |
| `act_number` | `70` | The act's number. |
| `year` | `1990` | The year the act was published. |
| `fek` | `Α΄ 31` | Where it was published in the Government Gazette: series Α, issue 31. Empty when the header doesn't say. |
| `title` | `Υγιεινή και Ασφάλεια …` | The title of the act: health and safety of workers in shipyards. |
| `citation` | `Π.Δ. 70/1990` | How the chunk names its source. Without an act number it is longer: act type, «title» and (chapter, year). |
| `citation_fallback` | `false` | `true` when that longer form had to be used. |
| `method` | `article` | How the whole document was cut: by article (others: `paragraph`, `size`, `whole`). |
| `kind` | `article` | What this chunk is: an article (others: `preamble`, `paragraph`, `whole`, `size`). |
| `article` | `Άρθρο 28` | Which article it is. When short pieces were joined, all their labels are listed. |
| `article_numbers` | `[28]` | The same as numbers, so a program can look up "article 28". A range like `Άρθρα 13-19` lists every number. |
| `part`, `parts` | `1`, `1` | Long articles are cut into windows; this is window 1 of 1, so the article was short enough to stay whole. |
| `words` | `49` | How long the chunk is. |
| `is_stub` | `false` | `true` when the whole document is under 30 words, usually a header with nothing else. |
| `is_note` | `false` | `true` when the chunk is mainly an editor's note about the law ("repealed by…", "amended by…") rather than the law itself: the notes make up at least half of it. |
| `repeal_sentences` | `[]` | The short sentence around each "was repealed" (`Κατηργήθη δια…`), kept word for word for a later phase. Empty here. |
| `text` | `Εργασίες με αμίαντο Άρθρ.28.-…` | The cleaned text of the chunk. It starts with the heading "Εργασίες με αμίαντο" (work with asbestos), which was moved here from the end of article 27. |
| `embed_text` | `Π.Δ. 70/1990, Άρθρο 28, …` | What is turned into an embedding and indexed for keyword search (Phase 1B): a short header (citation, article, title), a line break (`\n`), then the text. The header tells search which law the article belongs to, which the text alone doesn't say. |

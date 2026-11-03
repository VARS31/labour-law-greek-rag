# Data exploration: Greek Legal Code (Phase 0)

What is in the dataset [`AI-team-UoA/greek_legal_code`](https://huggingface.co/datasets/AI-team-UoA/greek_legal_code),
and what it means for building RAG over it. No embeddings and no database yet: this is only about the data.

Every number here comes from [`scripts/explore_data.py`](../scripts/explore_data.py). It reads the 9 parquet
files in `data/raw/` and writes `data/exploration/stats.json` plus the three sample texts. "Words" means
pieces of text between spaces, the simplest possible count.

## At a glance

| | |
|---|---|
| Documents | **47,563** legal acts (laws, decrees, ministerial decisions, …) |
| Text | **28.3 million words**, 356.5 MB of UTF-8 text |
| Groupings | **47 volumes** → **389 chapters** → **2,285 subjects** |
| Typical document | **79 words** (median). The average is 594, because a few huge codes pull it up |
| Dates | **1821 – 2009** (median 1974), from the header of 96% of documents |
| Labour law | Volume 41 *ΕΡΓΑΤΙΚΗ ΝΟΜΟΘΕΣΙΑ*: **1,284 documents, 0.77 M words, about 5,300 chunks** |
| Database size | Labour law ≈ **90 MB** → fits the Supabase free plan (500 MB). Full dataset ≈ **3.2 GB** → does not fit |

Two things to keep in mind from the start:

- **It is a historical snapshot.** The labour-law volume stops at **1999**, and the whole dataset at 2009.
  Greek labour law has changed a lot since then (for example the 2010s reforms and Ν. 4808/2021), so this
  corpus can only tell us what the law said back then.
- **The text is messy.** It was converted from the Word files of a printed collection. There are no line
  breaks, page headers sit in the middle of sentences, article order is sometimes shuffled, and some
  letters are not what they seem. Details are in [Data quality problems](#data-quality-problems).

## What one document looks like

A document is one legal act, taken from the *Permanent Greek Legislation Code – Raptarchis* (a big
catalogue of Greek legislation from 1834 on). It has one field, `text`, with the header followed by the
articles, **all on a single line**. No document contains a line break.

Most headers follow this pattern:

```
<running no.>. <TYPE OF ACT> <issuer> Αριθ. <number> της <signed>/<published date> (ΦΕΚ <issue> <no.>) <title>.
14. ΝΟΜΟΣ υπ’ αριθ. 751 της 4/10 Αυγ. 1948 Περί προστασίας των απολυομένων …
```

The type of act, read from the header:

| Type of act | Documents |
|---|---:|
| Υπουργική απόφαση (ministerial decision) | 20,269 |
| Νόμος (law) | 6,621 |
| Προεδρικό διάταγμα (presidential decree) | 5,787 |
| Νομοθετικό διάταγμα (legislative decree) | 4,743 |
| Βασιλικό διάταγμα (royal decree) | 4,160 |
| Αναγκαστικός νόμος (emergency law) | 3,009 |
| Πράξη, mostly Πράξη Υπουργικού Συμβουλίου (cabinet act) | 835 |
| Διεθνής σύμβαση (international convention) | 8 |
| other header (e.g. Διάταγμα, Κανονιστικό διάταγμα, Συντακτική πράξη, Εγκύκλιος ΙΚΑ, Κανονισμός, Αγορανομική διάταξη, Ψήφισμα) | 984 |
| no numbered header at all | 1,147 |

The dataset also comes split into `train` (28,536), `validation` (9,511) and `test` (9,516). That split is
for its original purpose, classifying documents by topic. For RAG it doesn't matter, so we use all
47,563 documents.

## How volume, chapter and subject relate

The groupings form a three-level tree, from broad to narrow:

```
volume (47)            e.g. ΕΡΓΑΤΙΚΗ ΝΟΜΟΘΕΣΙΑ                   (labour law)
 └─ chapter (389)      e.g. ΣΥΛΛΟΓΙΚΕΣ ΣΥΜΒΑΣΕΙΣ ΕΡΓΑΣΙΑΣ        (collective agreements)
     └─ subject (2,285)
         └─ documents
```

- A volume has 3 to 17 chapters (median 8).
- A chapter has 1 to 56 subjects (median 5) and 1 to 1,321 documents (median 81).
- A subject has 1 to 1,348 documents (median 9).

On Hugging Face, the dataset comes as **three copies of the same 47,563 texts**: the `volume`, `chapter`
and `subject` configs. Only the label changes. The rows are in the same order in all three (the script
checks that every text matches), so we join them by row position and get all three labels for each document.

The tree is *almost* perfect. Labels are names, and a few generic names are shared by different parents:

- 3 chapter names belong to 2 volumes each (e.g. *ΔΙΑΦΟΡΑ* "Miscellaneous" under both agricultural
  and church legislation).
- 31 subject names belong to several chapters (e.g. *ΓΕΝΙΚΕΣ ΔΙΑΤΑΞΕΙΣ* "General provisions" under 35
  chapters, and *ΟΡΓΑΝΙΚΕΣ ΔΙΑΤΑΞΕΙΣ* "Organisational provisions" under 11).

So a subject alone does not always tell you where a document belongs. **Store the full
(volume, chapter, subject) triple as metadata.**

## The 47 volumes

Sorted by number of documents. "Id" is the label number in the dataset, not the volume number in the
printed book. English names are my own short translations.

| Id | Volume | In English | Documents | Words | Chapters | Subjects |
|---:|---|---|---:|---:|---:|---:|
| 44 | ΕΠΙΣΤΗΜΕΣ ΚΑΙ ΤΕΧΝΕΣ | Sciences and arts | 3,492 | 1,328,964 | 16 | 153 |
| 21 | ΕΚΠΑΙΔΕΥΤΙΚΗ ΝΟΜΟΘΕΣΙΑ | Education | 2,862 | 1,168,659 | 11 | 85 |
| 24 | ΣΥΓΚΟΙΝΩΝΙΕΣ | Transport | 2,311 | 1,559,280 | 8 | 51 |
| 1 | ΓΕΩΡΓΙΚΗ ΝΟΜΟΘΕΣΙΑ | Agriculture | 1,946 | 1,059,579 | 14 | 66 |
| 45 | ΕΜΠΟΡΙΚΗ ΝΑΥΤΙΛΙΑ | Merchant shipping | 1,840 | 1,167,957 | 11 | 100 |
| 18 | ΔΙΟΙΚΗΣΗ ΔΙΚΑΙΟΣΥΝΗΣ | Administration of justice | 1,738 | 872,455 | 10 | 60 |
| 4 | ΥΓΕΙΟΝΟΜΙΚΗ ΝΟΜΟΘΕΣΙΑ | Public health | 1,730 | 989,364 | 12 | 99 |
| 17 | ΔΗΜΟΣΙΑ ΕΡΓΑ | Public works | 1,480 | 1,076,094 | 12 | 58 |
| 25 | ΕΘΝΙΚΗ ΑΜΥΝΑ | National defence | 1,462 | 877,879 | 11 | 82 |
| 19 | ΑΣΦΑΛΙΣΤΙΚΑ ΤΑΜΕΙΑ | Insurance funds | 1,421 | 1,009,740 | 6 | 71 |
| **41** | **ΕΡΓΑΤΙΚΗ ΝΟΜΟΘΕΣΙΑ** | **Labour law** | **1,284** | **769,486** | **17** | **66** |
| 3 | ΒΙΟΜΗΧΑΝΙΚΗ ΝΟΜΟΘΕΣΙΑ | Industry | 1,218 | 646,884 | 7 | 53 |
| 34 | ΔΙΠΛΩΜΑΤΙΚΗ ΝΟΜΟΘΕΣΙΑ | Diplomatic law | 1,154 | 724,943 | 5 | 58 |
| 36 | ΑΜΕΣΗ ΦΟΡΟΛΟΓΙΑ | Direct taxation | 1,128 | 591,857 | 9 | 46 |
| 6 | ΤΑΧΥΔΡΟΜΕΙΑ - ΤΗΛΕΠΙΚΟΙΝΩΝΙΕΣ | Post and telecoms | 1,122 | 1,014,408 | 13 | 42 |
| 46 | ΣΥΝΤΑΓΜΑΤΙΚΗ ΝΟΜΟΘΕΣΙΑ | Constitutional law | 1,115 | 601,550 | 10 | 48 |
| 28 | ΔΗΜΟΣΙΟΙ ΥΠΑΛΛΗΛΟΙ | Civil servants | 1,074 | 418,923 | 4 | 32 |
| 23 | ΤΕΛΩΝΕΙΑΚΗ ΝΟΜΟΘΕΣΙΑ | Customs | 1,036 | 685,109 | 9 | 92 |
| 31 | ΛΙΜΕΝΙΚΗ ΝΟΜΟΘΕΣΙΑ | Ports | 960 | 446,626 | 7 | 37 |
| 39 | ΑΣΤΥΝΟΜΙΚΗ ΝΟΜΟΘΕΣΙΑ | Police | 945 | 833,191 | 13 | 51 |
| 0 | ΚΟΙΝΩΝΙΚΗ ΠΡΟΝΟΙΑ | Social welfare | 935 | 572,254 | 8 | 57 |
| 11 | ΝΟΜΟΘΕΣΙΑ ΑΝΩΝΥΜΩΝ ΕΤΑΙΡΕΙΩΝ ΤΡΑΠΕΖΩΝ ΚΑΙ ΧΡΗΜΑΤΙΣΤΗΡΙΩΝ | Companies, banks, stock exchanges | 918 | 627,574 | 9 | 40 |
| 26 | ΣΤΡΑΤΟΣ ΞΗΡΑΣ | Army | 850 | 435,847 | 8 | 60 |
| 14 | ΚΟΙΝΩΝΙΚΕΣ ΑΣΦΑΛΙΣΕΙΣ | Social insurance | 847 | 501,408 | 13 | 78 |
| 10 | ΝΟΜΙΚΑ ΠΡΟΣΩΠΑ ΔΗΜΟΣΙΟΥ ΔΙΚΑΙΟΥ | Public-law bodies | 800 | 545,555 | 8 | 39 |
| 15 | ΝΟΜΟΘΕΣΙΑ ΔΗΜΩΝ ΚΑΙ ΚΟΙΝΟΤΗΤΩΝ | Municipalities | 774 | 598,046 | 6 | 34 |
| 13 | ΕΜΜΕΣΗ ΦΟΡΟΛΟΓΙΑ | Indirect taxation | 762 | 345,188 | 7 | 29 |
| 30 | ΟΙΚΟΝΟΜΙΚΗ ΔΙΟΙΚΗΣΗ | Financial administration | 664 | 404,215 | 3 | 28 |
| 37 | ΤΥΠΟΣ ΚΑΙ ΤΟΥΡΙΣΜΟΣ | Press and tourism | 649 | 294,856 | 6 | 35 |
| 20 | ΕΚΚΛΗΣΙΑΣΤΙΚΗ ΝΟΜΟΘΕΣΙΑ | Church law | 648 | 431,121 | 15 | 47 |
| 42 | ΠΟΙΝΙΚΗ ΝΟΜΟΘΕΣΙΑ | Criminal law | 620 | 612,024 | 15 | 58 |
| 29 | ΠΕΡΙΟΥΣΙΑ ΔΗΜΟΣΙΟΥ ΚΑΙ ΝΟΜΙΣΜΑ | State property and currency | 611 | 316,717 | 6 | 35 |
| 22 | ΔΗΜΟΣΙΟ ΛΟΓΙΣΤΙΚΟ | Public accounting | 590 | 348,089 | 5 | 17 |
| 35 | ΔΙΟΙΚΗΤΙΚΗ ΝΟΜΟΘΕΣΙΑ | Administrative law | 557 | 276,390 | 5 | 15 |
| 7 | ΔΑΣΗ ΚΑΙ ΚΤΗΝΟΤΡΟΦΙΑ | Forests and livestock | 553 | 479,874 | 4 | 44 |
| 43 | ΕΜΠΟΡΙΚΗ ΝΟΜΟΘΕΣΙΑ | Commercial law | 552 | 370,475 | 7 | 35 |
| 5 | ΠΟΛΕΜΙΚΟ ΝΑΥΤΙΚΟ | Navy | 542 | 310,024 | 8 | 61 |
| 38 | ΕΘΝΙΚΗ ΟΙΚΟΝΟΜΙΑ | National economy | 541 | 306,053 | 3 | 24 |
| 27 | ΑΓΟΡΑΝΟΜΙΚΗ ΝΟΜΟΘΕΣΙΑ | Market and price control | 532 | 341,477 | 7 | 28 |
| 32 | ΑΣΤΙΚΗ ΝΟΜΟΘΕΣΙΑ | Civil law | 516 | 232,308 | 9 | 31 |
| 16 | ΝΟΜΟΘΕΣΙΑ ΕΠΙΜΕΛΗΤΗΡΙΩΝ ΣΥΝΕΤΑΙΡΙΣΜΩΝ ΚΑΙ ΣΩΜΑΤΕΙΩΝ | Chambers, cooperatives, associations | 509 | 337,203 | 4 | 31 |
| 8 | ΕΛΕΓΚΤΙΚΟ ΣΥΝΕΔΡΙΟ ΚΑΙ ΣΥΝΤΑΞΕΙΣ | Court of Audit and pensions | 457 | 214,661 | 4 | 15 |
| 40 | ΑΓΡΟΤΙΚΗ ΝΟΜΟΘΕΣΙΑ | Rural law | 419 | 339,247 | 5 | 30 |
| 12 | ΠΟΛΙΤΙΚΗ ΑΕΡΟΠΟΡΙΑ | Civil aviation | 415 | 391,163 | 7 | 35 |
| 2 | ΡΑΔΙΟΦΩΝΙΑ ΚΑΙ ΤΥΠΟΣ | Radio and press | 393 | 210,571 | 6 | 18 |
| 9 | ΠΟΛΕΜΙΚΗ ΑΕΡΟΠΟΡΙΑ | Air force | 354 | 190,060 | 3 | 32 |
| 33 | ΠΟΛΙΤΙΚΗ ΔΙΚΟΝΟΜΙΑ | Civil procedure | 237 | 385,949 | 6 | 35 |

## How long the documents are

Words per document:

| Shortest | 10% | 25% | **Median (typical)** | Average | 75% | 90% | 95% | 99% | Longest |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | 26 | 36 | **79** | 594 | 333 | 1,132 | 2,363 | 8,913 | 146,309 |

(The dataset card says "about 600 words on average", which matches our 594.)

| Words | Documents | Share |
|---|---:|---:|
| under 30 | 7,331 | 15% |
| 30 – 100 | 18,331 | 39% |
| 100 – 500 | 12,864 | 27% |
| 500 – 2,000 | 6,202 | 13% |
| 2,000 – 10,000 | 2,437 | 5% |
| 10,000 or more | 398 | 1% |

In simple words: **most documents are short**, often just a header plus one or two sentences. A small
number are enormous, because whole codes were stored as a single document:

| Words | Volume | Document |
|---:|---|---|
| 146,309 | ΑΜΕΣΗ ΦΟΡΟΛΟΓΙΑ | Ν. 2238/1994, Income Tax Code (Κώδικας Φορολογίας Εισοδήματος) |
| 113,760 | ΠΟΛΙΤΙΚΗ ΔΙΚΟΝΟΜΙΑ | Β.Δ. 657/1971, codification of the Code of Civil Procedure |
| 111,974 | ΠΟΛΙΤΙΚΗ ΔΙΚΟΝΟΜΙΑ | Π.Δ. 503/1985, Code of Civil Procedure |
| 105,834 | ΑΓΟΡΑΝΟΜΙΚΗ ΝΟΜΟΘΕΣΙΑ | Αγορανομική Διάταξη 14/1989, market regulation code |
| 98,481 | ΠΟΙΝΙΚΗ ΝΟΜΟΘΕΣΙΑ | Ν. 1493/1950, Code of Criminal Procedure |

The shortest "documents" are fragments, such as ` άρθρου 1984 §3. ` (3 words).

## Dates

The text has no date field, but most headers contain one: `… της 18/19 Μαρτ. 1968 (ΦΕΚ …)`. The first
date is when the act was signed, the second when it was published. We take the year of the second.

- A header date was found in **45,799 documents (96%)**.
- Range: **1821 to 2009**. 5% are from before 1923, the median is **1974**, and 95% are from before 2000.
- The oldest are revolutionary-era texts, e.g. *Οργανισμός της Πελοποννησιακής Γερουσίας* (1821).
- The dataset card says the catalogue runs to 2015, but no header date after 2009 was found.
- The other 4% have no usable header date (usually no header at all). Guessing from "the first year in
  the text" gives wrong answers (e.g. "Ν. 2026/1992" read as the year 2026), so we leave them undated.

| Decade | 1820s–1900s | 1910s | 1920s | 1930s | 1940s | 1950s | 1960s | 1970s | 1980s | 1990s | 2000s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Documents | 980 | 830 | 1,618 | 2,809 | 4,217 | 4,288 | 4,642 | 9,689 | 8,275 | 6,693 | 1,758 |

## Three sample documents

All three come from the labour-law volume. They were picked by length against the whole dataset:
**short** = the 10th percentile, **typical** = the median, **long** = the 90th percentile (and it
must contain articles). Text is shown exactly as in the dataset, including the original
errors.

### Short: 26 words (doc #7219, train)

A header and nothing else. About one document in six is under 30 words, and most of those look like
this: they tell you *that* an act exists, but not what it says.

> 9\. ΑΠΟΦΑΣΙΣ ΠΡΩΘΥΠΟΥΡΓΟΥ ΚΑΙ ΥΠΟΥΡΓΩΝ ΣΥΝΤΟΝΙΣΜΟΥ  ΚΑΙ  ΠΡΟΓΡΑΜΜΑΤΙΣΜΟΥ ΒΙΟΜΗΧΑΝΙΑΣ  ΚΑΙ ΑΠΑΣΧΟΛΗΣΕΩΣ Αριθ. 8371/1583 της 4/4 Δεκ. 1973 (ΦΕΚ Β΄1426) Περί αναπροσαρμογής κατωτάτων ορίων μισθών ιδιωτικών υπαλλήλων.

### Typical: 79 words (doc #15034, train)

A header plus an editorial note from the collection's editors: which acts amended this one, and that it
was later repealed (*Κατηργήθη*). Many documents are like this. They are useful for "what happened to
law X" questions, but they contain no rules.

> 14\. ΝΟΜΟΣ υπ’ αριθ. 751 της 4/10 Αυγ. 1948 Περί προστασίας των απολυομένων εκ των υπηρετούντων εις τας τάξεις του στρατού κατά την διάρκειαν της παρούσης κατά του Έθνους συμμοριακής δράσεως. Τροποποιηθείς και συμπληρωθείς υπό των α)Ν.Δ. 1196 της 7/18 Οκτωβρ. 1949 περί τροποποιήσεως και συμπληρώσεως ενίων διατάξεων του Νόμ. 751/1948 και β)Α.Ν. 1544 της 29/29 Οκτ. 1950 περί συμπληρώσεως ενίων διατάξεων του ν. 751/1948 και του Ν.Δ. 1196/1949. Κατηργήθη δια του άρθρ. 12 Α.Ν. 1836/1951 κατωτ. αριθ. 15.

### Long: 1,121 words (doc #3244, train)

A 1922 law that ratifies an International Labour Conference convention on lead paint. Look for:

- **Two article numberings in one document:** the law's own *Άρθρον μόνον* … *Άρθρον δεύτερον*, and the
  convention's *Άρθρον 1* to *15*.
- **Shuffled order:** the text runs *Άρθρον 9 → 15*, then *Άρθρον δεύτερον*, then *Άρθρον 1 → 8*.
- **Printed-page noise in mid-sentence:** `15.Λ.β.3 Απαγόρευση χρήσης επιβλαβών ουσιών`,
  `Σελίς 307 15.Λ.α.58 Υγιεινή και ασφάλεια χώρων εργασίας …`, `Σελίς 308`.
- **Typing errors** from the source: *οισίας* (ουσίας), *ταύτος* (ταύτας).

> 3\. ΝΟΜΟΣ 2994 της 3/31 Αυγ. 1922 Περί κυρώσεως της διεθνούς συμβάσεως της Γ΄ Διεθνούς Συνδιασκέψεως Εργασίας της Γενεύης, της κανονιζούσης την χρήσιν του ανθρακικού μολύβδου (στουπετσίου) εν τοις χρωματισμοίς. Άρθρον μόνον Κυρούται η περί της χρήσης του ανθρακικού μολύβδου (στουπετσίου) εν τοις χρωματισμοίς σύμβασις, η ψηφισθείσα υπό της εν Γενεύη της Ελβετίας την 12/26 Οκτ. 1921 συνελθούσης Γ΄ Διεθνούς Συνδιασκέψεως Εργασίας, έχουσα ως έπεται: ΔΙΕΘΝΗΣ ΣΥΝΔΙΑΣΚΕΨΙΣ ΕΡΓΑΣΙΑΣ Σχέδιον συμβάσεως περί της χρήσεως του  ανθρακικού μολύβδου (στουπετσίου) εν τοις  χρωματισμοίς. Η γενική συνδιάσκεψις της διεθνούς οργανώσεως εργασίας της Κ.Τ.Ε. Συγκληθείσα εν Γενεύη υπό του διοικητικού συμβουλίου του διεθνούς γραφείου εργασίας και συνελθούσα εν τη τρίτη αυτής συνόδω την 23 Οκτ. 1921. Αποδεχθείσα διαφόρους προτάσεις εν σχέσει προς την απαγόρευσιν της χρήσεως του ανθρακικού μολύβδου (στουπετσίου) εν τοις χρωματισμοίς, ζήτημα αποτελούν το έκτον θέμα της ημερησίας διατάξεως της συνόδου, και  Αποφασίσασα ίνα αι προτάσεις αύται λάβωσι τον τύπον διεθνούς συμβάσεως. Αποδέχεται το ακόλουθον σχέδιον συμβάσεως προς έγκρισιν υπό των μελών της διεθνούς οργανώσεως εργασίας συνωδά ταις διατάξεσι του ΧΙΙΙ μέρους της συνθήκης των Βερσαλλιών και των συναφών μερών των λοιπών συνθηκών ειρήνης. Άρθρον 9 Η παρούσα σύμβασις τεθήσεται εν ισχύϊ άμα αι επικυρώσεις δύο μελών της διεθνούς οργανώσεως εργασίας πρωτοκολληθώσιν υπό του γενικού γραμματέως. Θέλει δε υποχρεώσει μόνον τα μέλη, ων η επικύρωσις κατεχωρίσθη παρά τη γενική γραμματεία. Συνεπώς η σύμβασις αύτη τεθήσεται εν ισχύι δι’ έκαστον μέλος αφ’ ης η επικύρωσις αυτού κατεχωρίσθη παρά τη γραμματεία. 15.Λ.β.3 Απαγόρευση χρήσης επιβλαβών ουσιών Άρθρον 10 Ευθύς ως αι επικυρώσεις δύο μελών της διεθνούς οργανώσεως εργασίας ήθελον καταχωρισθή παρά τη γραμματεία ο γενικός γραμματεύς της Κ.Τ.Ε. θέλει κοινοποιήσει τούτο εις πάντα τα μέλη της διεθνούς οργανώσεως εργασίας. Ωσύτως θέλει κοινοποιήσει την καταχώρησιν των επικυρώσεων, των μεταγενεστέρως ανακοινωθεισών αυτώ υπό των λοιπών μελών της οργανώσεως. Άρθρον 11 Παν μέλος επικυρούν την παρούσα σύμβασις υποχρεούται εις την εφαρμογήν των διατάξεων των άρθρ. 1, 2, 3, 4, 5, 6 και 7 το βραδύτερον την 1 Ιαν.1924 κατά την λήψιν μέτρων χρησίμων δια την πραγματοποίησιν των διατάξεων τούτων. Άρθρον 12 Παν μέλος της διεθνούς οργανώσεως εργασίας επικυρούν την παρούσαν σύμβασιν υποχρεούται εις την εφαρμογήν αυτής εις τας αποικίας, κτήσεως και προτεκτοράτα αυτού, συνωδά ταις διατάξεσι του άρθρ. 421 της συνθήκης των Βερσαλλιών και των αντιστοίχων άρθρων των λοιπών συνθηκών ειρήνης. Άρθρον 13 Παν μέλος επικυρώσαν την παρούσαν συνθήκην δύναται να την καταγγείλη μετά παρέλευσιν δεκαετίας αφ’ ης αρχικώς ετέθη εν ισχύι δια πράξεως κοινοποιουμενής τω γενικώ γραμματεί της Κ.Τ.Ε. και παρ’ αυτού καταχωρισμένης. Η καταγγελία καθίσταται ισχυρά μόνον μετά παρέλευσιν έτους από της καταχωρήσεως αυτής παρά τη γραμματεία. Άρθρον 14 Το διοικητικόν συμβούλιον του διεθνούς γραφείου εργασίας οφείλει άπαξ τουλάχιστον κατά δεκαετίαν να παρουσίαση εις την γενικήν συνδιάσκεψιν έκθεσιν περί της εφαρμογής της παρούσης συμβάσεως και ν’ αποφασίση εάν υπάρχη λόγος περί εγγραφής εις την ημερησίαν διάταξιν της συνδιασκέψεως του ζητήματος της αναθεωρήσεως ή μεταρρυθμίσεως της παρούσης συμβάσεως. Άρθρον 15 Τα κείμενα, γαλλικόν και αγγλικόν, της παρούσης συμβάσεως θεωρούνται αμφότερα αυθεντικά. Άρθρον δεύτερον Δια Β.Δ/τος κωδικοποιηθήσονται αι ανωτέρω διατάξεις της παρούσης συμβάσεως εις τους οικείους νόμους. Επίσης δια Β.Δ/τος κανονισθήσονται αι λεπτομέρειαι της εφαρμογής των διατάξεων της δια του παρόντος κυρουμένης συμβάσεως. Άρθρον 1 Έκαστον μέλος της διεθνούς οργανώσεως εργασίας, επικυροί την παρούσαν σύμβασιν, οφείλει ν’ απαγορεύση υπό επιφύλαξιν των εν τω άρθρ. 2 προβλεπομένων εξαιρέσεων την χρήσιν του ανθρακικού μολύβδου (στουπετσίου), του θειϊκού μολύβδου και λοιπών προϊόντων Σελίς 307 15.Λ.α.58 Υγιεινή και ασφάλεια χώρων εργασίας και εργαζομένων Απαγόρευση χρήσης επιβλαβών ουσιών 15.Λ.β.1-3 περιεχόντων τας ουσίας ταύτος εις τα έργα εσωτερικών χρωματισμούς οικοδομών, πλην των σιδηροδρομικών σταθμών και των βιομηχανικών καταστημάτων, εις α η χρήσις του ανθρακικού μολύβδου, του θειϊκού μολύβδου, και λοιπών προϊόντων περιεχόντων τας οισίας ταύτας θεωρείται αναγκαία υπό των αρμοδίων αρχών, μετά προηγουμένην γνωμοδότησιν των οργανώσεων εργοδοτών και εργατών. Η χρήσις λευκών οισιών περιεχουσών κατ’ ανώτατον όριον 2% μόλυβδον, εκφραζομένων εις μεταλλικόν μόλυβδον, δεν απαγορεύεται. Άρθρον 2 Αι διατάξεις του άρθρ. 1 δεν εφαρμόζονται ούτε εις την κοσμηματογραφίαν, ούτε εις την διάστρωσιν και αναζωγόνησιν πινάκων ζωγραφικής. Εκάστη κυβέρνησις θέλει ορίσει το όριον μεταξύ των διαφόρων ειδών χρωματισμού και κατομομάσει την χρήσιν του ανθρακικού μολύβδου (στουπετσίου), του θειϊκού μολύβδου και λοιπών προϊόντων περιεχόντων τας ουσίας ταύτας εν τη εκτελέσει των έργων τούτων, συμφώνως, ταις διατάξεσι των άρθρ. 5, 6 και 7 της παρούσης συμβάσεως. Άρθρον 3 Απαγορεύεται η πρόσληψις νέων κάτω του δεκάτου ογδόου έτους και γυναικών εις έργα βιομηχανικής βαφής, εις α γίνεται χρήσις του ανθρακικού μολύβδου, θειϊκού μολύβδου και λοιπών ειδών περιεχόντων τας ουσίας ταύτας. Αι αρμόδιαι αρχαί κέκτηνται το δικαίωμα, μετά προηγουμένην γνωμοδότησιν των οργανώσεων εργοδοτών και εργατών, όπως επιτρέψωσιν ίνα οι μαθητευόμενοι χρωματισταί προσλαμβάνωνται δια την επαγγελματικήν αυτών εκπαίδευσιν εις έργα απαγορευόμενα εν τη ανωτέρω παραγράφω. Άρθρον 4 Αι υπό των άρθρ. 1 και 3 προβλεπόμεναι απαγορεύσεις τεθήσονται εν ισχύϊ μετά εξαετίαν από της λήψεως αυτών υπό της τρίτης συνόδου της διεθνούς συνδιασκέψεως εργασίας. Άρθρον 5 Παν μέλος της διεθνούς οργανώσεως εργασίας επικυρούν την παρούσαν σύμβασιν οφείλει να κανονίση επί τη βάσει των κάτωθι αρχών την χρήσιν του ανθρακικού μολύβδου, του θειϊκού μολύβδου και λοιπών ειδών περιεχόντων τας ουσίας ταύτας εις έργα ένθα η χρήσις αυτών δεν απαγορεύεται: Α΄. α)Ο ανθρακικός μόλυβδος, ο θειϊκός μόλυβδος και τα είδη τα περιέχοντα τας ουσίας ταύτας δύνανται μόνον υπό μορφήν πολτού ή χρώματος ετοίμου  Σελίς 308 προς χρήσιν ν’ αναμιχθώσι. β)Θέλουσι ληφθή μέτρα προς αποσόβησιν παντός κινδύνου πηγάζοντος εκ της χρήσεως της βαφής δια κονιοποιήσεως. γ)Θέλουσι ληφθή μέτρα, οσάκις είναι δυνατόν προς αποσόβησιν παντός κινδύνου εκ κόνεων προερχομένων εκ θρυμματίσεως και ξέσεως εν ξηρώ. Β΄. α)Δια διατάξεως θέλει κανονισθή ίνα οι εργάται βαφείς λαμβάνωσι πάσαν φροντίδα απαιτουμένης καθαριότητος κατά την διάρκειαν και μετά το πέρας της εργασίας. β)Οι εργάται βαφείς καθ’ όλην την διάρκειαν της εργασίας των δέον να φέρουσιν ενδύματα εργασίας. γ)Δι’ ειδικών διατάξεων θέλει ορισθή ίνα τα παρά των εργατών αφινόμενα κατά την διάρκειαν της εργασίας ενδύματα μη λερώνωνται δι’ υλικών χρησιμοποιουμένων εν τη βαφή. Γ΄. α)Αι περιπτώσεις μολυβδιάσεως και αι περιπτώσεις αι προβλεπόμεναι εκ μολυβδιάσεως θέλουσιν αποτελέσει αντικείμενον δηλώσεως και μεταγενεστέρας ιατρικής βεβαιώσεως παρά ιατρού διοριζομένου υπό της αρμόδιας αρχής. β)Η αρμόδια αρχή δύναται ν’ απαιτήση ιατρικήν εξέτασιν των εργατών οπόταν ήθελε κρίνει αναγκαίον τούτο. Δ΄.Σχετικαί οδηγίαι ως προς τας ειδικάς προφυλάξεις υγείας θέλουσι διανεμηθή εις τους εργάτας βαφείς. Άρθρον 6 Προς εξασφάλισιν του εν τοις προηγουμένοις άρθροις προβλεπομένου κανονισμού η αρμόδια αρχή θέλει λάβει οιαδήποτε μέτρα κρίνει κατάλληλα μετά προηγουμένην γνωμοδοτησιν των ενδιαφερομένων οργανώσεων εργοδοτών και εργατών. Άρθρον 7 Σχετικαί περί μολυβδιάσεως στατιστικαί των εργατών βαφέων θέλουσι γίνει: α)Περί θνησιμότητος, δια δηλώσεως και εξελέγξεως πασών των περιπτώσεων μολυβδιάσεως. β)Περί θνησιμότητος, κατά μέθοδον εγκεκριμένην υπό της επισήμου υπηρεσίας στατικής εν εκάστη χώρα. Άρθρον 8 Αι επίσημοι επικυρώσεις της παρούσης συμβάσεως, εντός των όρων των διαγραφομένων εν τω ΧΙΙΙ μέρει της συνθήκης των Βερσαλλιών και των αντιστοίχων μερών των λοιπών συνθηκών ειρήνης, ανακοινωθήσονται τω γενικώ γραμματεί της Κ.Τ.Ε. και θέλουσι παρ’ αυτού καταχωρισθή.

(Document numbers count from 0 across train, then validation, then test, as in `scripts/explore_data.py`.)

## How articles are marked

We plan to chunk by article, so this section matters most. Since there are no line breaks, an article
can only be found by its **marker word** in the running text. The script found **135,210 markers** in
**15,435 documents**. The main styles:

| Style | Example from the data | Markers | Documents |
|---|---|---:|---:|
| Abbreviated, with a dash (editors' style) | `Άρθρ.1.-Έκαστος εν γένει τελωνειακός υπόλογος …` | 101,622 | 11,200 |
| Modern | `Άρθρο 1 Διάρθρωση και αρμοδιότητες …` | 17,084 | 1,018 |
| Katharevousa | `Άρθρον 1 Απαγορεύεται εις τας εργ…` | 11,554 | 960 |
| Single-article act | `Άρθρον μόνον.-Οσάκις …`, `Άρθρο μόνο.-` | 3,097 | 3,049 |
| Ordinal word | `Άρθρο πρώτο`, `Άρθρον δεύτερον` | 1,083 | 394 |
| Roman numeral | `Άρθρο ΙΙ` | 770 | 97 |

The same marker often appears in a damaged form, and a chunker has to accept these too:

| Variant | Example | Markers |
|---|---|---:|
| Spacing tonos before the capital (instead of `Ά`) | `΄Αρθρ.2.-` | 8,041 |
| No accent | `Αρθρ.26.-`, `Αρθρο πρώτο` | 1,054 |
| All capitals | `ΑΡΘΡΟ 5` | 626 |
| A **Latin** letter inside | `Άρθρo 3` (Latin `o`) | 121 |

Other forms you meet in the text:

- **Ranges and inserted articles:** `Άρθρ.13-19.-(Καταργήθηκαν …)`, `Άρθρ.5 δις.-`.
  Ranges are usually editorial notes saying a group of articles was repealed.
- **Not markers, but references** to other laws: lowercase `άρθρο`/`άρθρ.`, `(Άρθρ. 1 του Ν.Δ. 131/1974 …)`,
  `Άρθρ. 5 παρ. 2`, `του άρθρου 3`. The script skips these: it requires a capital letter, and
  rejects a marker that follows `(`/`του`/`το` or is followed by `παρ.`/`της`/`του`/`Ν.` …
- **Headings glued to the marker:** the article title, which was on its own line in the original,
  now runs straight into the previous sentence: `… Φυτοτεχνολόγοι Άρθρ.4.-1.Παροχή βοηθητικής εργασίας …`.

How many articles a document has:

| Article markers | 0 | 1 | 2–5 | 6–20 | 21–100 | over 100 |
|---|---:|---:|---:|---:|---:|---:|
| Documents | 32,128 (68%) | 3,450 | 6,017 | 4,745 | 1,129 | 94 |

**Two out of three documents have no article marker at all.** Most of these are short (median 45
words): a header, a summary, or a "repealed" note. 3,320 of them are longer than 300 words: 2,464 of
those are ministerial decisions, and 2,574 have numbered paragraphs (`1.Η … 2.Οι … 3.Το …`) instead of
articles. They need a fallback, such as splitting by numbered paragraph or by size.

**Article order cannot be trusted.** In 3,701 of the 9,805 documents with at least 3 numbered articles,
the numbers go backwards somewhere. The most common pattern (2,527 documents) is
`1, 9, 10, …, 16, 2, 3, …, 8`: the last articles of the act appear right after article 1. And 325
documents contain an "article 1" more than once, because they hold two numberings (a ratifying law plus
the convention it ratifies, as in the long sample, or an amending law quoting the articles it replaces).
So we should keep each article's number as metadata and never rely on its position in the text.

## Data quality problems

| Problem | How much | Example | What to do later |
|---|---|---|---|
| **No line breaks** | all 47,563 documents | headings and articles run together | find structure only through markers |
| **Micro sign `µ` instead of Greek `μ`** | 30,756 times, 115 docs | `Ολυµπιακής`, `δηµόσιο` | replace `µ` (U+00B5) with `μ` (U+03BC) |
| **Lost `μ`** (probably a Symbol-font letter that got dropped) | some docs | `Οργανισ ός Κανονισ οί`, `σιδ ου` | can't be fixed reliably; just be aware |
| **Latin letters inside Greek words** | 30,868 times, 1,865 docs | `τoυ`, `τωv`, `Άρθρo`, `AΠΟΦΑΣΗ`, `Εurοpοl` | map Latin look-alikes to Greek inside Greek words |
| **Private-use "Symbol font" characters** | 2,078 times, 233 docs | `περί ατμολεβήτων` (used as quotes) | replace or drop |
| **Cyrillic letters** | 163 times, 76 docs | `νόμου ΒπИΘ΄` (old law numbers written as Greek numerals) | leave; rare |
| Soft hyphens and no-break spaces | 72 docs | `(Α\xad 15)` | remove / turn into normal spaces |
| Broken characters (`�`) | **0** | none | nothing (no classic "mojibake") |
| **Accents: spacing tonos** instead of an accented letter | 12,766 times, 2,933 docs | `΄Αργει`, `΄Αρθρ.` | join `΄`+vowel into the accented letter |
| **Accents: missing** | e.g. `Αρθρο` 1,823 and `Αρθρ.` 7,419 times | `Αρθρ.1.-` | accent-insensitive search (e.g. Postgres `unaccent`) |
| Accents: polytonic / non-NFC | 661 polytonic characters; 14 docs change under NFC | `ἰ`, `ὕ` | apply NFC normalisation |
| **Old and new Greek mixed** | everywhere | `ΑΠΟΦΑΣΙΣ` / `ΑΠΟΦΑΣΗ`, `Άρθρον` / `Άρθρο` | matters for keyword search; embeddings handle it better |
| **Printed-page headers in the text** | `Σελ./Σελίς N` in 17,367 docs, `Τεύχος` in 13,334 | `… Σελ. 228 18.Ζ.γ.9 Προσωπικό ξενοδοχείων Άρθρ.2.- …` | strip page number + position code + running title |
| Book position codes | 16,752 docs | `15.Λ.α.58`, `16.Α.α.307-310` | strip, or keep as metadata |
| **Missing header** | 1,147 docs (2.4%) | starts with the title only, or straight with `Άρθρ.1.-…` (208 docs) | no act type / number / date for these |
| **Stubs** | 7,331 docs under 30 words; 18,010 under 50 | header + `Κατηργήθη …` | keep (they answer "what happened to X"), but flag them |
| Editorial notes instead of law text | 4,605 docs | `(Τροποποιείται το εδάφ. 6 …)`, `(Καταργήθηκαν …)` | label them as notes, not as the law itself |
| Words split by stray spaces, typing errors | common in places | `ΕΡΓ ΑΣΙΑΣ`, `οισίας` | can't fix in general |
| Form placeholders | 421 docs | `Αριθ.(2):……………` | harmless |
| **Shuffled article order** | 3,701 docs | `1, 9, 2, 3, …` | store article numbers; don't trust position |
| Mixed scripts in the **labels** too | a few names | `ΥΠΟΥΡΓΕΙΟ ΔΗΜΟΣΙΑΣ TAΞΗΣ` (Latin `TA`), `ΥΠΟΥΡΓΕΊΟ ΚΟΙΝΩΝΙΚΏΝ` | normalise label names as well |
| **Duplicates** | rare | see below | ignore, or dedupe in Phase 1 |

**Duplicates, more closely.** No two texts are byte-for-byte identical, but each starts with its own
running number (`23. …`), which hides copies. With that number removed (and case, accents and punctuation
ignored), there are only **8 groups of identical texts (9 extra copies)**. Matching on the first 300
characters finds **34 groups (37 extra copies)**: the same act filed under two subjects, sometimes in two
volumes or two splits, often with different body lengths. That's too few to worry about.

**Time coverage** is the biggest "quality" issue for our use case. The texts are as Raptarchis printed
them. Many acts were later repealed or amended, and nothing after 2009 is included (nothing after 1999 for
labour law).

## Labour law

Labour law is **volume 41, ΕΡΓΑΤΙΚΗ ΝΟΜΟΘΕΣΙΑ**:

| | |
|---|---|
| Documents | **1,284** (2.7% of the dataset) |
| Words | **769,486** (median 126 per document, average 599, longest 18,264) |
| Text size | 9.7 MB |
| Chapters / subjects | 17 / 66 |
| Years (header dates) | **1852 – 1999**, median 1974. Nothing after 1999 |
| Documents with article markers | 445 (35%), with 3,923 markers |
| **Estimated chunks (by article)** | **≈ 5,300** (5,301; 5,906 if long articles are cut at 300 words, 5,082 at 800) |

| Chapter | In English | Documents |
|---|---|---:|
| ΡΥΘΜΙΣΗ ΤΗΣ ΑΓΟΡΑΣ ΕΡΓΑΣΙΑΣ | Labour market regulation | 386 |
| ΔΙΟΙΚΗΣΗ ΕΡΓΑΣΙΑΣ | Labour administration | 193 |
| ΟΡΓΑΝΙΣΜΟΙ ΥΠΟΥΡΓΕΙΟΥ ΕΡΓΑΣΙΑΣ | Organisation of the Labour Ministry | 173 |
| ΣΥΛΛΟΓΙΚΕΣ ΣΥΜΒΑΣΕΙΣ ΕΡΓΑΣΙΑΣ | Collective labour agreements | 142 |
| ΟΡΓΑΝΩΣΗ ΧΡΟΝΟΥ ΕΡΓΑΣΙΑΣ | Working time | 96 |
| ΥΓΙΕΙΝΗ ΚΑΙ ΑΣΦΑΛΕΙΑ ΕΡΓΑΖΟΜΕΝΩΝ | Health and safety at work | 69 |
| ΔΙΑΚΟΠΕΣ ΤΗΣ ΕΡΓΑΣΙΑΣ | Time off (rest days, holidays, leave) | 54 |
| ΕΠΑΓΓΕΛΜΑΤΙΚΟΣ ΚΙΝΔΥΝΟΣ | Occupational risk | 31 |
| ΕΡΓΑΣΙΑ ΓΥΝΑΙΚΩΝ ΚΑΙ ΑΝΗΛΙΚΩΝ | Work of women and minors | 31 |
| ΠΡΟΣΤΑΣΙΑ ΠΡΟΣΩΠΩΝ ΕΙΔΙΚΩΝ ΚΑΤΗΓΟΡΙΩΝ | Protection of special groups | 31 |
| ΠΛΗΡΩΜΗ ΕΡΓΑΣΙΑΣ | Pay | 28 |
| ΕΚΠΑΙΔΕΥΣΗ ΕΡΓΑΤΩΝ | Worker training | 23 |
| ΚΑΤΑΓΓΕΛΙΑ ΣΥΜΒΑΣΕΩΣ ΕΡΓΑΣΙΑΣ | Dismissal (ending the contract) | 18 |
| ΕΛΕΥΘΕΡΙΑ ΤΗΣ ΕΡΓΑΣΙΑΣ | Freedom of work | 4 |
| ΚΑΤΟΧΥΡΩΣΗ ΕΠΑΓΓΕΛΜΑΤΩΝ | Protected professions | 3 |
| ΜΕΤΑΝΑΣΤΕΥΣΗ | Emigration | 1 |
| ΕΙΔΙΚΕΣ ΜΟΡΦΕΣ ΑΠΑΣΧΟΛΗΣΗΣ | Special forms of employment | 1 |

The three longest labour documents are a 1971 ministerial regulation (18,264 words), Π.Δ. 70/1990 on
health and safety in shipyards (18,100) and Π.Δ. 136/1999 on the Labour Inspectorate (13,277).

**Labour-related material outside volume 41**, in case we want to widen the scope later:
chapter *ΣΥΜΒΑΣΗ ΝΑΥΤΙΚΗΣ ΕΡΓΑΣΙΑΣ* (seafarers' employment, 457 docs, in Merchant shipping), chapter
*ΠΑΡΟΧΕΣ ΑΝΕΡΓΙΑΣ* (unemployment benefits, 42 docs, in Social insurance), and the related volumes
Social insurance (847), Insurance funds (1,421) and Civil servants (1,074).

## Size estimate for the database decision

### How chunks are counted

The script applies these rules to every document:

1. Split at each article marker (the regex described above).
2. The text before the first marker (header + preamble) is its own chunk. A document with no marker is
   one piece.
3. Pieces under 20 words (e.g. `Άρθρ.13-19.-(Καταργήθηκαν …)`) are merged into the piece before them.
4. Pieces over 500 words are cut into equal parts of at most 500 words, so that one chunk stays
   about one topic. (The script also reports the counts for 300 and 800.)

This gives about **4 chunks per labour document**, with a median of 91 words per chunk.

### What one chunk costs in Postgres + pgvector

The sizes come from the pgvector 0.8.6 headers installed with Postgres.app:

- **Vector:** `vector(1024)` = 4 B header + 2 B dimensions + 2 B unused + 4 B × 1024 = **4,104 bytes**.
  pgvector stores it out of line (TOAST, `STORAGE = external`) without compression, so with storage
  overhead it takes about 4.2 KB. `halfvec(1024)` (16-bit numbers) is **2,056 bytes**.
- **Search index (HNSW):** each entry holds a full copy of the vector plus its neighbour list, and an
  entry must fit in one 8 KB page. With 1024-d float32 vectors only one entry fits per page, so
  **≈ 8 KB per chunk**. With halfvec, 3 fit, so ≈ 2.7 KB. *This is an estimate. Phase 1 should measure
  it with `pg_relation_size`.*
- **Text:** the real UTF-8 bytes (Greek letters take 2 bytes each). Postgres may compress long texts, so
  this is an upper bound.
- **Rows:** about 150 B per chunk (ids, article number, labels) plus 500 B per document (header, title,
  labels).
- **+20% margin** for page free space and small indexes.

### Result

| | (a) Labour law only | (b) Full dataset |
|---|---:|---:|
| Documents | 1,284 | 47,563 |
| Chunks | **5,301** | **181,654** |
| Text | 9.7 MB | 356.5 MB |
| Vectors, float32 | 22.4 MB | 767 MB |
| HNSW index, float32 | 43.4 MB | 1,488 MB |
| Rows + document table | 1.4 MB | 51 MB |
| **Total, float32 (+20%)** | **≈ 92 MB** | **≈ 3.2 GB** |
| Total, halfvec (+20%) | ≈ 44 MB | ≈ 1.55 GB |
| …plus a full-text index for hybrid search (≈ text size, +20%) | ≈ 104 MB / 56 MB | ≈ 3.6 GB / 2.0 GB |
| **Supabase free plan: 500 MB** | **fits** (≈ 18% of the limit; 9% with halfvec) | **does not fit** (≈ 6× over; 3× with halfvec) |

What this means:

- **Labour law fits easily** in the Supabase free plan, even with float32 vectors, an HNSW index and a
  full-text index. With only about 5,300 vectors, we may not need an HNSW index at all: an exact scan
  over 5,300 vectors is fast. That removes the biggest item and brings it to about 40 MB.
- **The full dataset does not fit.** The text alone is 357 MB, already 71% of the limit, before any
  vectors. Even halfvec without HNSW would be well over 500 MB.
- Supabase's own built-in schemas also use part of the 500 MB, so the real room is a bit smaller.
- Since the project runs locally anyway, **local Postgres is the simple default**: Postgres.app 16 with
  pgvector 0.8.6 is already installed on this machine. Supabase only matters if we later want to host a
  demo of the labour-law subset.

## What this means for Phase 1

1. **Normalise the text before anything else:** NFC; `µ`→`μ`; Latin look-alikes → Greek inside Greek
   words; spacing tonos + vowel → accented vowel; Symbol-font quotes → `«»`; drop soft hyphens.
   Without this, even the article regex misses markers like `Άρθρo`.
2. **Strip printed-page noise** (`Σελ./Σελίς N`, `Τεύχος …`, position codes like `15.Λ.α.58` and the
   running title after them). Test this carefully, because the running titles are ordinary Greek words.
3. **Chunk by article** with the marker regex from `scripts/explore_data.py` as a starting point. Keep as
   metadata: volume / chapter / subject, act type, act number, year, ΦΕΚ, article number, and whether
   the chunk is an editorial note.
4. **Fallback for the 68% of documents without markers:** split by numbered paragraph or by size.
5. **Search:** accent-insensitive keyword search (`unaccent`) next to vectors, because old and new Greek
   spellings and missing accents are everywhere.
6. **Be honest about time:** the agent should say that its sources stop in 1999 (labour) or 2009 (all).

# Evaluation set: items for review

20 of the 52 items in `eval/questions.jsonl`. I read the source passage for every item, and code has checked that each quote below appears in its chunk. I picked the items where my reading could most easily be wrong, so this sample is harder than the rest.

For each item, replace the Verdict line with one word (keep, edit or reject) and add a note if you wish. Expected answers follow our data, even where today's law says something else.

## single-06 (answerable from one place, test)

**Question:** Είμαι υπάλληλος αορίστου χρόνου με πέντε χρόνια υπηρεσία. Πόσο νωρίτερα πρέπει να με ειδοποιήσουν γραπτά αν θέλουν να με διώξουν;

**Answerable from our data:** yes

**Expected key facts:**

- Τρεις μήνες πριν από την απόλυση
- Η καταγγελία πρέπει να είναι έγγραφη

**Gold source:**

- Ν. 2112/1920, Άρθρο 1 (glc-41850-005): «γ)Δι’ υπαλλήλους συμπληρώσαντας τετραετή υπηρεσίαν, τρεις μήνας προ της απολύσεως. δ)Δι’ υπαλλήλους συμπληρώσαντας εξαετή υπηρεσίαν, τέσσαρας μήνας προ της απολύσεως.»

**Notes:** Five years falls in step γ (four years completed), not δ (six). Phase 1C found this chunk outside the top 50 for a dismissal question, so it is a good retrieval test. Trap: Β.Δ. 16/18 Ιουλ. 1920 art. 3 gives far shorter periods, but only for manual workers (see sector-01).

Verdict: keep

## single-12 (answerable from one place, test)

**Question:** Πόσες ώρες ξεκούραση πρέπει να έχω τουλάχιστον μέσα σε κάθε εικοσιτετράωρο;

**Answerable from our data:** yes

**Expected key facts:**

- Τουλάχιστον 12 συνεχείς ώρες
- Το 24ωρο αρχίζει στις 00:01 και λήγει στις 24:00

**Gold source:**

- Π.Δ. 88/1999, Άρθρο 3 (glc-14869-011): «Για κάθε περίοδο 24 ωρών, η ελάχιστη ανάπαυση δεν μπορεί να είναι κατώτερη από 12 συνεχείς ώρες. Η περίοδος των 24 ωρών αρχίζει την 00:01 και λήγει την 24:00 ώρα.»

**Notes:** The expected answer follows our 1999 text, whatever later law says. A model answering from memory may give another number, and this item would catch that. Trap: the rule for minors (Ν. 1837/1989 art. 5, Π.Δ. 62/1998 art. 9) also says 12 hours but covers another group; it would be a wrong source, though it gives the same number.

Verdict: keep

## single-15 (answerable from one place, dev)

**Question:** Πόσο κρατάει η άδεια μητρότητας και πώς μοιράζεται πριν και μετά τη γέννα;

**Answerable from our data:** yes

**Expected key facts:**

- 16 εβδομάδες συνολικά
- 8 εβδομάδες πριν από την πιθανή ημερομηνία τοκετού
- 8 εβδομάδες μετά τον τοκετό

**Gold source:**

- Π.Δ. 176/1997, Άρθρο 8 (glc-10348-002): «Η συνολική διάρκεια της άδειας μητρότητας ορίζεται σε 16 εβδομάδες, 8 εβδομάδες θα χορηγούνται υποχρεωτικά πριν από την πιθανή ημερομηνία τοκετού και οι υπόλοιπες 8 μετά τον τοκετό.»

**Notes:** Trap: the collective agreements of 1984 to 1986 in our data (glc-02055-004, glc-21033-005, glc-39164-004) say 14 weeks; the 1997 decree is newer, so 16 is the expected answer. Follows our data, not today's law. In Phase 1C the 2-per-document limit removed this very chunk. Same topic as a Phase 1C question, so kept in dev.

Verdict: keep

## single-17 (answerable from one place, dev)

**Question:** Μπορεί να απολυθεί μια εργαζόμενη όσο είναι έγκυος;

**Answerable from our data:** yes

**Expected key facts:**

- Απαγορεύεται η απόλυση (καταγγελία)
- Εξαίρεση μόνο για σπουδαίο λόγο, αιτιολογημένη γραπτώς
- Ο εργοδότης το κοινοποιεί στις υπηρεσίες επιθεώρησης εργασίας

**Gold source:**

- Π.Δ. 176/1997, Άρθρο 10 (glc-10348-004): «Απαγορεύεται η καταγγελία της σχέσης εργασίας των εργαζομένων γυναικών, κατά την έννοια του άρθρ. 2, σύμφωνα με το άρθρ. 15 του Νόμ. 1483/84. 2.Σε περίπτωση καταγγελίας της σχέσης εργασίας εφόσον υπάρχει σπουδαίος λόγος σύμφωνα με το άρθρ. 15 του Νόμ.1483/84, ο εργοδότης οφείλει να αιτιολογήσει δεόντως την καταγγελία γραπτώς και να προβεί σε σχετική κοινοποίηση και προς τις αρμόδιες υπηρεσίες επιθεώρησης εργασίας των Νομαρχιακών Αυτοδιοικήσεων.»

**Notes:** Ν. 1483/1984 itself isn't in our data, so how long the ban lasts can't be answered from it. An answer that adds a period (for example one year after birth) is using outside knowledge. Phase 1C found this chunk outside the top 50. Same topic as a Phase 1C question, so kept in dev.

Verdict: edit. Keep "dismissal is forbidden" and "exception only for a serious reason, justified in writing". Keep "informs the Labour Inspectorate" only if the chunk literally says so. It does («να προβεί σε σχετική κοινοποίηση και προς τις αρμόδιες υπηρεσίες επιθεώρησης εργασίας»), so all three facts stay; the facts and quote above are the edited ones.

## single-22 (answerable from one place, test)

**Question:** Από πόσα άτομα και πάνω μια εταιρεία χρειάζεται τεχνικό ασφαλείας και γιατρό εργασίας;

**Answerable from our data:** yes

**Expected key facts:**

- Από 50 εργαζομένους και πάνω
- Υποχρέωση του εργοδότη
- Τεχνικός ασφάλειας και γιατρός εργασίας

**Gold source:**

- Π.Δ. 17/1996, Άρθρο 4 (glc-21935-017): «Στις επιχειρήσεις που απασχολούν 50 και άνω εργαζομένους ο εργοδότης έχει την υποχρέωση να χρησιμοποιεί τις υπηρεσίες τεχνικού ασφαλείας και γιατρού εργασίας»
- Ν. 1568/1985, Άρθρο 4 (glc-40488-032): «Στις επιχειρήσεις που απασχολούν κατά ετήσιο μέσο όρο πάνω από 50 εργαζομένους, ο εργοδότης έχει υποχρέωση να χρησιμοποιεί τις υπηρεσίες τεχνικού ασφάλειας και γιατρού εργασίας.»

**Notes:** The two laws differ slightly: 'πάνω από 50' in 1985, '50 και άνω' in 1996. The newer one sets the expected fact; an answer saying 'πάνω από 50' and citing Ν. 1568/1985 is close enough to count. Trap: Π.Δ. 17/1996 art. 3 is about 20 people, but concerns employee representatives.

Verdict: keep

## single-25 (answerable from one place, test)

**Question:** Χτύπησα στη δουλειά και έμεινα σπίτι μία εβδομάδα. Μου χρωστάει αποζημίωση ο εργοδότης;

**Answerable from our data:** yes

**Expected key facts:**

- Το ατύχημα πρέπει να έγινε κατά την εργασία ή εξ αφορμής της
- Η διακοπή εργασίας πρέπει να κράτησε πάνω από τέσσερις ημέρες
- Όχι αν ο παθών το προκάλεσε εκ προθέσεως

**Gold source:**

- Β.Δ. 24 Ιουλ./25 Αυγ. 1920, Άρθρο 1 (glc-09103-001): «Ατύχημα εκ βιαίου συμβάντος, επερχόμενον εις εργάτην ή υπάλληλον των εν τω άρθρ. 2 εργασιών και επιχειρήσεων, εν τη εκτελέσει της εργασίας ή εξ αφορμής αυτής, παρέχει εις τα κατά τας διατάξεις του παρόντος νόμου δικαιούμενα πρόσωπα δικαίωμα αποζημιώσεως απέναντι του κυρίου της επιχειρήσεως, εάν η εις τον παθόντα εκ του ατυχήματος προελθούσα διακοπή εργασίας διήρκεσε πλέον των τεσσάρων ημερών»

**Notes:** The rule covers only the works and businesses listed in art. 2. Old law, kept as our data gives it; later social-insurance rules may limit it, and I did not try to work that out.

Verdict: keep

## single-32 (answerable from one place, dev)

**Question:** Πόσες ώρες την εβδομάδα είναι η κανονική δουλειά στον ιδιωτικό τομέα;

**Answerable from our data:** yes

**Expected key facts:**

- 40 ώρες την εβδομάδα
- Οι αποδοχές δεν μειώνονται παρά τις λιγότερες ώρες

**Gold source:**

- Υ.Α. 12440/1986, Άρθρο 6 (glc-39164-006): «Η διάρκεια της εβδομαδιαίας εργασίας των εργαζομένων, που απασχολούνται σε οποιοδήποτε εργοδότη με σχέση εργασίας ιδιωτικού δικαίου όλης της Χώρας, ορίζεται σε 40 ώρες.»
- Υ.Α. 11117/1985, Άρθρο 6 (glc-21033-007): «Η διάρκεια της εβδομαδιαίας εργασίας των εργαζομένων, που απασχολούνται σε οποιοδήποτε εργοδότη με σχέση εργασίας ιδιωτικού δικαίου όλης της Χώρας, ορίζεται σε 40 ώρες.»
- Υ.Α. 11770/1984, Άρθρο 6 (glc-02055-006): «Η διάρκεια της εβδομαδιαίας εργασίας των εργαζομένων, που απασχολούνται σε οποιοδήποτε εργοδότη με σχέση εργασίας ιδιωτικού δικαίου όλης της Χώρας, ορίζεται σε 40 ώρες.»

**Notes:** The same sentence in three national agreements, so any of the three counts. Strong trap: Π.Δ. 1932 art. 2 and Ν.Δ. 1037/1971 art. 9 say 48 hours and are the more famous laws, but the agreements are newer. Near-duplicate removal keeps only one of the three, which is fine, since any one is enough.

Verdict: keep

## sector-01 (sector trap, dev)

**Question:** Είμαι εργάτης σε εργοστάσιο εδώ και έξι χρόνια. Πόσες μέρες πριν πρέπει να με ειδοποιήσουν για απόλυση;

**Answerable from our data:** yes

**Expected key facts:**

- Τουλάχιστον 30 ημέρες πριν
- Ισχύει για εργάτες και τεχνίτες με πάνω από πέντε χρόνια

**Gold source:**

- Β.Δ. 16/18 Ιουλ. 1920, Άρθρο 3 (glc-23368-009): «Σύμβασις εργασίας διαρκέσασα υπέρ την πενταετίαν καταγγέλλεται τουλάχιστον προ 30 ημερών, εάν δε διήρκεσε υπέρ την δεκαετίαν, τουλάχιστον προ 60 ημερών.»

**Notes:** General vs specific rule. The famous law, Ν. 2112/1920 art. 1, gives 4 months for six years, but only for 'υπάλληλοι'. For a factory worker the 1920 royal decree applies. An answer of 4 months is wrong. The rest of the chunk lists severance in daily wages, which is a different thing.

Verdict: keep

## sector-02 (sector trap, dev)

**Question:** Δουλεύω σε κατάστημα και μου ζήτησαν να μείνω παραπάνω για απογραφή. Πόσες ώρες επιτρέπεται το πολύ;

**Answerable from our data:** yes

**Expected key facts:**

- Το πολύ δύο ώρες την ημέρα
- Το πολύ 120 ώρες τον χρόνο για κάθε μισθωτό
- Για απογραφή χρειάζεται άδεια της αρμόδιας υπηρεσίας

**Gold source:**

- Ν.Δ. 1037/1971, Άρθρο 12 (glc-23803-006): «Η κατά την προηγουμένην παράγραφον υπέρβασις δεν δύναται να είναι μακροτέρα των δύο ωρών καθ’ εκάστην ουδέ των 120 ωρών ετησίως δι’ έκαστον μισθωτόν.»

**Notes:** Trap: the factory rule, Π.Δ. 1932 art. 4 par. 2, allows 3 hours a day. Shops have their own decree. Also the 75% in the same chunk applies only to work beyond the permitted cases. Same topic as a Phase 1C question, so kept in dev.

Verdict: keep

## sector-03 (sector trap, dev)

**Question:** Πόσο παραπάνω πληρώνεται ένας εργάτης σε αρτοποιείο για τις υπερωρίες του;

**Answerable from our data:** yes

**Expected key facts:**

- 25% μέχρι 60 ώρες τον χρόνο
- 50% από 60 έως 120 ώρες τον χρόνο
- 75% πάνω από 120 ώρες τον χρόνο

**Gold source:**

- Υ.Α. Φ.20023/19/1954, Άρθρο 2 (glc-35409-004): «οι αρτεργάται δικαιούνται επί του αναλογούντος ωρομισθίου προσαυξήσεως 25% δια τας μέχρι 60 ώρας ετησίως, 50% δια τας πέραν των 60 και μέχρις 120 ώρας ετησίως, και 75% δια τας πέραν των 120 ώρας ετησίως»

**Notes:** Trap: the ΚΤΕΛ decree gives 30/50/75 and cinema staff 25/50, so the first step tells the sources apart. This paragraph covers overtime on Saturdays, the eves of two-day bread and the Christmas and Easter periods. The word 'αρτοποιείο' is kept in the question so that the sector is clear.

Verdict: keep

## sector-04 (sector trap, test)

**Question:** Είμαι οδηγός σε υπεραστικό ΚΤΕΛ. Πώς υπολογίζεται η πληρωμή μου για τις υπερωρίες;

**Answerable from our data:** yes

**Expected key facts:**

- Ωρομίσθιο: μηνιαίες αποδοχές διά 200
- 30% μέχρι 60 ώρες τον χρόνο
- 50% από 60 έως 120 ώρες τον χρόνο
- 75% πάνω από 120 ώρες τον χρόνο

**Gold source:**

- Π.Δ. 119/1973, Άρθρο 5 (glc-45483-010): «η αμοιβή εκάστης ώρας υπερωριακής απασχολήσεως των κατά το παρόν άρθρον οριζομένων υπερωριών ισούται προς το ωρομίσθιον εξευρισκόμενον δια διαιρέσεως των καταβαλλομένων μηνιαίως αποδοχών του μισθωτού δια του αριθμού 200 και προσηυξημένον κατά ποσοστόν: α)30% δια τας μέχρις 60 ώρας ετησίως. β)50% δια τας πέραν των 60 ωρών ετησίως και μέχρις 120 και γ)75% δια τας πέραν των 120 ωρών ετησίως.»

**Notes:** The reverse of reference-01: here the sector rule is the right answer. Trap: Π.Δ. 288/1976 covers urban ΚΤΕΛ with a double shift and has other limits, so 'υπεραστικό' is in the question. In Phase 1C this same chunk was wrongly offered as the general overtime rule.

Verdict: keep

## vocab-01 (vocabulary mismatch, dev)

**Question:** Ποιος νόμος βάζει κανόνες ασφαλείας στις οικοδομές;

**Answerable from our data:** yes

**Expected key facts:**

- Π.Δ. 305/1996
- Αφορά τα προσωρινά ή κινητά εργοτάξια
- Στα αποσπάσματα υπάρχει μόνο ο τίτλος, όχι οι κανόνες

**Gold source:**

- Π.Δ. 305/1996, Τίτλος (glc-42215-000): ««Ελάχιστες προδιαγραφές ασφάλειας και υγείας που πρέπει να εφαρμόζονται στα προσωρινά ή κινητά εργοτάξια σε συμμόρφωση προς την οδηγία 92/57/ΕΟΚ.»

**Notes:** Trap: a 32-word header with no rules, only the title. A good answer names the decree and says the rules aren't in the sources. Π.Δ. 16/1996 art. 1 (glc-00550-028) explicitly excludes temporary sites, so citing its rules is wrong. Π.Δ. 1073/1981 is named once (glc-38853-004) but its text isn't in our data. Same topic as a Phase 1C question, so kept in dev.

Verdict: keep

## vocab-03 (vocabulary mismatch, dev)

**Question:** Επιτρέπεται στους φούρνους να ζυμώνουν μέσα στη νύχτα;

**Answerable from our data:** yes

**Expected key facts:**

- Απαγορεύεται η εργασία μεταξύ 21:30 και 06:00
- Εξαίρεση το Σάββατο και οι παραμονές που ετοιμάζεται ψωμί για δύο ή περισσότερες ημέρες

**Gold source:**

- Υ.Α. Φ.20023/19/1954, Άρθρο 2 (glc-35409-004): «Απαγορεύεται πάσα εργασία προς παρασκευήν, ζύμωσιν και έψησιν άρτου μεταξύ της 09.30έσπερινής και 06.00΄ πρωϊνής ώρας, πλην του Σαββάτου»

**Notes:** 'φούρνος' vs 'αρτοποιείο'. The source writes '09.30' with the word for evening, so 21:30 is the correct reading. The wording is from a 1981 amendment, quoted in the chunk. Trap: Β.Δ. 1938 on bakeries gives other hours but is older; art. 8 and 9 of the same decision allow exceptions by permit and for indirectly heated ovens.

Verdict: keep

## vocab-04 (vocabulary mismatch, test)

**Question:** Πόσα ένσημα χρειάζομαι για να πάρω ταμείο ανεργίας;

**Answerable from our data:** yes

**Expected key facts:**

- 125 ημέρες εργασίας στην ασφάλιση ανεργίας
- Μέσα στους τελευταίους 14 μήνες πριν από τη λύση της σχέσης
- Χωρίς να μετράνε οι τελευταίοι δύο μήνες

**Gold source:**

- Ν.Δ. 2961/1954, Άρθρο 17 (glc-11069-011): «δικαιούται επιδόματος ανεργίας, εφ’ όσον επραγματοποίησε 125 ημέρας εργασίας εν τη ασφαλίσει ανεργίας εντός των τελευταίων προ της λύσεως της σχέσεως εργασίας 14 μηνών των ημερών εργασίας των τελευταίων δύο μηνών μη συνυπολογιζομένων.»

**Notes:** 'ένσημα' and 'ταμείο ανεργίας' appear nowhere in the law. Traps: 100 days for hotel workers and builders by later decisions; glc-10290-007 says the same 125 days but only for fishery workers. Ν. 1545/1985 art. 4 is mentioned by other decisions as the later rule, yet its text isn't in our data, so 125 days is the best our data gives.

Verdict: keep

## reference-01 (follow a reference, dev)

**Question:** Δουλεύω σε εργοστάσιο και κάνω υπερωρίες. Με τι ποσοστό αυξάνεται το ωρομίσθιό μου;

**Answerable from our data:** no, the right answer says it wasn't found

**Expected key facts:**

- Το γενικό ποσοστό βρίσκεται στο άρθρο 1 του Ν. 435/1976
- Το κείμενο του Ν. 435/1976 δεν υπάρχει στα αποσπάσματα
- Δεν παρουσιάζει τα ποσοστά των ΚΤΕΛ ή των αρτοποιείων ως γενικό κανόνα

**Gold source:**

- Ν.Δ. 515/1970, Προοίμιο, Άρθρο 1 (glc-05222-000): «Δια το ηυξημένον ωρομίσθιον των υπερωριών βλ. ήδη άρθρ. 1 Νόμ. 435/1976 (τόμ. 15 σελ. 136,03).»
- Ν.Δ. 1037/1971, Άρθρο 11 (glc-23803-005): «Δια το ηυξημένον ωρομίσθιον των υπερωριών βλ. ήδη άρθρ. 1 Νόμ. 435/1976 (τόμ. 15 σελ. 136,03).»
- Π.Δ. 8/13 Απρ. 1932, Άρθρο 18 (glc-30636-001): «Δια το ηυξημένον ωρομίσθιον των υπερωριών βλ. ήδη άρθρ. 1 Νόμ. 435/1976 (τόμ. 15 σελ. 136,03).»
- Β.Δ. 28/29 Απρ. 1937, Άρθρο 4 (glc-32123-004): «Δια το ηυξημένον ωρομίσθιον των υπερωριών βλ. ήδη άρθρ. 1 Νόμ. 435/1976 (τόμ. 15 σελ. 136,03).»

**Notes:** I checked: Ν. 435/1976 is not a document in our data; 15 chunks only mention it, plus one that misprints it as '4435/1976'. So the right answer says where the rule is and that its text is missing. Ν.Δ. 4020/1959 art. 8, the other pointer, isn't in the data either. I went through all 14 chunks that have both overtime and a percentage: each one covers a single sector or a special case, so no general rate exists. Traps: the 25% in Π.Δ. 1932 art. 9 was repealed; the 75% in Ν.Δ. 515/1970 is for special permits only. Same topic as a Phase 1C question, so kept in dev.

Verdict: keep

## reference-02 (follow a reference, dev)

**Question:** Είμαι υπάλληλος και με ειδοποίησαν κανονικά πριν με απολύσουν. Δικαιούμαι και αποζημίωση; Πόση;

**Answerable from our data:** yes

**Expected key facts:**

- Ναι, αποζημίωση οφείλεται και με προειδοποίηση
- Το μισό της αποζημίωσης που οφείλεται χωρίς προειδοποίηση
- Πληρώνεται όταν λήξει η προθεσμία

**Gold source:**

- Ν. 2112/1920, Άρθρο 3 (glc-41850-007): «Δια του άρθρ. 4 του Νόμ. 3198/1955 (τόμ. 15 σελ. 98, 01) η αποζημίωσις αύτη ωρίσθη εις το ήμισυ.»
- Ν. 3198/1955, Άρθρο 4 (glc-22895-006): «ο εργοδότης υποχρεούται να καταβάλη εις τον απολυόμενον, άμα τη εκπνοή της προθεσμίας ταύτης, το ήμισυ της προβλεπομένης υπό του ως άνω Νόμου αποζημιώσεως δια την περίπτωσιν της απροειδοποίητου καταγγελίας της συμβάσεως εργασίας.»

**Notes:** A reference that can be followed: the 1920 law says a quarter, and a note in the same chunk points to Ν. 3198/1955 art. 4, which makes it a half. Either chunk gives the half. Trap: an answer of one quarter reads the old text and misses the note. The word 'υπάλληλος' matters, because art. 4 applies 'μόνον περί υπαλλήλων'.

Verdict: keep

## reference-03 (follow a reference, test)

**Question:** Τι άδεια δικαιούται κάποιος με 20 χρόνια προϋπηρεσίας;

**Answerable from our data:** no, the right answer says it wasn't found

**Expected key facts:**

- Το Α.Ν. 539/1945 παραπέμπει στο άρθρο 22 του Ν. 2556/1997
- Το κείμενο αυτού του άρθρου δεν υπάρχει στα αποσπάσματα

**Gold source:**

- Α.Ν. 539/1945, Άρθρο 2 (glc-40073-002): «Για την ετήσια άδεια των εργαζομένων με προϋπηρεσία 20 ετών βλέπε άρθρ. 22 Νόμ. 2556/23-24 Δεκ. 1997 (ΦΕΚ Α΄ 270), κατωτ. αριθ. 31.»

**Notes:** I checked: Ν. 2556/1997 is not a document in our data, only notes mention it, and no other chunk has a 20-year leave rule. The closest real rule is 25 years (see single-31); an answer may mention that if it says it's a different threshold. Applying 25-year days to 20 years is wrong.

Verdict: keep

## refuse-03 (must be refused, dev)

**Question:** Πόσα ευρώ είναι σήμερα ο κατώτατος μισθός;

**Answerable from our data:** no, the right answer says it wasn't found

**Expected key facts:**

- Λέει καθαρά ότι δεν βρέθηκε απάντηση στα αποσπάσματα
- Δεν παρουσιάζει ποσό σε δραχμές ως σημερινό κατώτατο μισθό

**Gold source:**

- None: the data has nothing on this.

**Notes:** I searched: no chunk gives an amount in euro. Trap: many ΕΓΣΣΕ chunks give minimum wages in drachmas up to the 1990s. Mentioning them as historical is fine if the answer also says today's figure isn't in the sources.

Verdict: keep

## refuse-05 (must be refused, test)

**Question:** Μπορεί ο εργοδότης να βάλει κάμερες στον χώρο δουλειάς για να παρακολουθεί τους υπαλλήλους;

**Answerable from our data:** no, the right answer says it wasn't found

**Expected key facts:**

- Λέει καθαρά ότι δεν βρέθηκε απάντηση στα αποσπάσματα
- Δεν βγάζει συμπέρασμα από γενικούς κανόνες υγιεινής και ασφάλειας

**Gold source:**

- None: the data has nothing on this.

**Notes:** Labour topic with no source. I searched: 'καμερ*' and 'βιντεοεπιτηρ*' are in no chunk. Harder than the others, because the question sounds like it should be covered.

Verdict: keep

## lookup-01 (exact law lookup, dev)

**Question:** Τι λέει το άρθρο 2 του Ν. 1837/1989;

**Answerable from our data:** yes

**Expected key facts:**

- Απαγορεύεται η απασχόληση ανηλίκων κάτω των 15 ετών
- Με την επιφύλαξη του άρθρου 3
- Απαγορεύονται στους ανηλίκους οι επικίνδυνες, βαριές ή ανθυγιεινές εργασίες

**Gold source:**

- Ν. 1837/1989, Άρθρο 2 (μέσα στο chunk με ετικέτα «Άρθρο 18») (glc-33848-010): «Με την επιφύλαξη του άρθρ. 3 ανήλικοι που δεν έχουν συμπληρώσει το 15ο έτος της ηλικίας τους απαγορεύεται να απασχοληθούν σε οποιαδήποτε εργασία.»

**Notes:** Strong trap: the source text is out of order, so art. 2 sits in the middle of art. 18 and our chunk is labelled only 'Άρθρο 18'. A search by article label can't find it. A model that sees the chunk under the heading 'Άρθρο 18' may still read it correctly. Same topic as a Phase 1C question, so kept in dev.

Verdict: keep

"""Phase 1C parts that run without a database or model: choosing chunks and checking citations."""

import unittest

from labour_rag.citations import check, closest, is_refusal, quote_found
from labour_rag.retrieve import rule_numbers, select

# glc-40073-002, Α.Ν. 539/1945 Άρθρο 2 (start)
LEAVE = ("Άρθρ.2.-«1.Κάθε μισθωτός, μετά από συνεχή απασχόληση τουλάχιστο δώδεκα μηνών (βασικός χρόνος) σε "
         "υπόχρεη επιχείρηση δικαιούται κάθε ημερολογιακό έτος άδεια με αποδοχές 24 εργάσιμες ημέρες και αν στην "
         "επιχείρηση εφαρμόζεται σύστημα πενθήμερης εβδομάδας εργασίας 20 εργάσιμες ημέρες.")
OTHER = "Άρθρον 5 1.Πάσα συμφωνία μεταξύ εργοδότου και μισθωτού, περιλαμβάνουσα την εγκατάλειψιν του δικαιώματος."
CHUNKS = [{"n": 1, "text": LEAVE}, {"n": 2, "text": OTHER}]
NOTE = "Σημείωση: Οι πηγές φτάνουν μέχρι το 1999."


class Quotes(unittest.TestCase):
    def test_exact_quote_ignoring_accents_case_and_bold(self):
        self.assertTrue(quote_found("**24 εργάσιμες ημέρες** και αν στην ΕΠΙΧΕΙΡΗΣΗ", LEAVE))

    def test_ellipsis_skips_words_but_keeps_order(self):
        self.assertTrue(quote_found("Κάθε μισθωτός … δικαιούται κάθε ημερολογιακό έτος άδεια", LEAVE))
        self.assertFalse(quote_found("δικαιούται … Κάθε μισθωτός", LEAVE))

    def test_changed_words_fail_but_closest_passage_is_shown(self):
        # Real model output: "(βασικός χρόνος) σε υπόχρεη επιχείρηση" dropped, "τουλάχιστο" modernised.
        quote = ("Κάθε μισθωτός μετά από συνεχή απασχόληση τουλάχιστον δώδεκα μηνών δικαιούται κάθε ημερολογιακό "
                 "έτος άδεια με αποδοχές 24 εργάσιμες ημέρες")
        self.assertFalse(quote_found(quote, LEAVE))
        similarity, passage = closest(quote, LEAVE)
        self.assertGreater(similarity, 0.75)
        self.assertIn("τουλάχιστο", passage)


class Check(unittest.TestCase):
    def test_good_answer(self):
        answer = ("**Σύντομη απάντηση:** Σύμφωνα με τον Α.Ν. 539/1945, ο μισθωτός δικαιούται «άδεια με αποδοχές 24 "
                  "εργάσιμες ημέρες» [1].\n" + NOTE)
        result = check(answer, CHUNKS, NOTE)
        self.assertTrue(result["ok"], result["failures"])
        self.assertEqual(result["warnings"], [])           # "Α.Ν. 539/1945" is not split into two sentences
        self.assertEqual(result["quotes"][0]["found_in"], [1])

    def test_unknown_source(self):
        result = check("Σύμφωνα με τον Α.Ν. 539/1945 η άδεια είναι 24 ημέρες [1][9].", CHUNKS)
        self.assertFalse(result["ok"])
        self.assertIn("[9]", result["failures"][0])

    def test_quote_in_the_wrong_source(self):
        result = check("Το 1945 ορίστηκε ότι «Πάσα συμφωνία μεταξύ εργοδότου και μισθωτού» είναι άκυρη [1].", CHUNKS)
        self.assertFalse(result["ok"])
        self.assertIn("not found in [1]", result["failures"][0])

    def test_quote_without_citation(self):
        result = check("Ο νόμος του 1945 λέει «Κάθε μισθωτός, μετά από συνεχή απασχόληση». Άρα ισχύει [1].", CHUNKS)
        self.assertIn("quote without a citation", result["failures"][0])

    def test_several_numbers_in_one_marker(self):
        result = check("Ο Α.Ν. 539/1945 ρυθμίζει την άδεια και τις συμφωνίες για αυτήν [1, 2].", CHUNKS)
        self.assertEqual(result["citations"], [1, 2])
        self.assertTrue(result["ok"])

    def test_refusal_needs_no_citation(self):
        result = check("**Σύντομη απάντηση:** Δεν βρέθηκε απάντηση στα διαθέσιμα κείμενα.\n" + NOTE, CHUNKS, NOTE)
        self.assertTrue(result["ok"])
        self.assertTrue(result["refusal"])

    def test_refusal_in_other_words_needs_no_citation(self):
        answer = ("**Σύντομη απάντηση:**\nΤο άρθρο 2 του Ν. 1837/1989 δεν αναφέρεται στα αποσπάσματα που σου δόθηκαν. "
                  "Ωστόσο, το άρθρο 1 του ίδιου νόμου ορίζει το πεδίο εφαρμογής του.")
        result = check(answer, CHUNKS)
        self.assertTrue(result["refusal"])
        self.assertTrue(result["ok"])

    def test_ways_of_saying_it_isnt_in_the_sources(self):
        for answer in ("Τα αποσπάσματα δεν αναφέρουν τίποτα για τον Ν. 3863/2010.",
                       "Ο Ν. 3863/2010 δεν αναφέρεται στα αποσπάσματα που σου δώσαμε.",
                       "Η απάντηση δεν περιέχεται στα διαθέσιμα κείμενα.",
                       "Δεν βρέθηκε απάντηση στα διαθέσιμα κείμενα."):
            self.assertTrue(is_refusal(answer), answer)

    def test_a_missing_detail_in_an_answer_is_not_a_refusal(self):
        for answer in ("Η προθεσμία δεν ορίζεται συγκεκριμένα σε αυτό το απόσπασμα, αλλά γενικά είναι πέντε χρόνια.",
                       "Η προθεσμία δεν αναφέρεται στα αποσπάσματα, αλλά γενικά είναι πέντε χρόνια.",
                       "Ο νόμος δεν αναφέρει άλλες υποχρεωτικές αργίες εκτός από αυτές τις τέσσερις [2].",
                       "Ο μισθωτός δικαιούται άδεια [1]. " + "Αυτή δίνεται κάθε έτος [1]. " * 12
                       + "Το ποσό δεν αναφέρεται στα αποσπάσματα."):
            self.assertFalse(is_refusal(answer), answer)

    def test_answer_without_any_citation_fails(self):
        result = check("Ο μισθωτός δικαιούται είκοσι τέσσερις ημέρες άδεια κάθε χρόνο από το 1945.", CHUNKS)
        self.assertIn("the answer cites no source", result["failures"])

    def test_warnings(self):
        result = check("Ο μισθωτός δικαιούται άδεια με αποδοχές [1]. Η άδεια αυτή δίνεται κάθε ημερολογιακό έτος "
                       "σε όλους τους εργαζόμενους.", CHUNKS, NOTE)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["warnings"]), 3)          # uncited sentence, no year, no closing note


def result(rid, doc, text, rank, year=1980):
    return {"id": rid, "doc_id": doc, "text": text, "rank": rank, "year": year}


class Select(unittest.TestCase):
    def test_near_duplicates_and_document_limit(self):
        clause = ("Κάθε Μέλος που έχει επικυρώσει αυτή τη σύμβαση θα μπορεί να την καταγγείλει μετά τη λήξη "
                  "δεκαετίας από την ημερομηνία της αρχικής θέσης της σε ισχύ")
        results = [result("a", 1, clause, 1),
                   result("b", 2, clause.replace("θα μπορεί", "μπορεί"), 2),     # same clause, other convention
                   result("c", 3, LEAVE, 3), result("d", 3, OTHER, 4),
                   result("e", 3, "Άρθρ.3.-Κατά την διάρκειαν της αδείας ο μισθωτός δικαιούται των αποδοχών", 5),
                   result("f", 4, "Άρθρ.7.-Η κανονική άδεια χορηγείται κατά την περίοδο των θερινών διακοπών", 6)]
        kept, removed = select(results, k=4, max_per_document=2)
        self.assertEqual([r["id"] for r in kept], ["a", "c", "d", "f"])
        self.assertEqual([r["n"] for r in kept], [1, 2, 3, 4])
        self.assertEqual([(r["id"], r["reason"]) for r in removed], [("b", "near-duplicate"), ("e", "same document")])
        self.assertEqual(removed[0]["of"], "a")

    # The real pair behind single-15: same words around different numbers, Υ.Α. 12756/1989 and Π.Δ. 176/1997.
    MATERNITY = "Η συνολική διάρκεια της άδειας μητρότητας ορίζεται σε {} εβδομάδες πριν και μετά τον τοκετό"
    # The real kind of pair behind the yearly bonus decisions: the same rule, with another decision number and date.
    BONUS = ("{}. ΑΠΟΦΑΣΙΣ ΥΠΟΥΡΓΩΝ Αριθ. {} (ΦΕΚ Β΄{}) Περί χορηγήσεως δώρου Χριστουγέννων εις τους μισθωτούς. "
             "Οι εργοδόται υποχρεούνται να καταβάλουν εις τους μισθωτούς δώρον ίσον προς 25 ημερομίσθια")

    def test_different_numbers_are_never_repeats(self):
        results = [result("old", 1, self.MATERNITY.format(15), 1, 1989), result("new", 2, self.MATERNITY.format(16), 2, 1997)]
        kept, removed = select(results, k=4, max_per_document=2)
        self.assertEqual([r["id"] for r in kept], ["old", "new"])
        self.assertEqual(removed, [])

    def test_numbers_that_only_name_a_decision_dont_stop_a_repeat(self):
        results = [result("a", 1, self.BONUS.format(18, "111700/6570", 808), 1, 1969),
                   result("b", 2, self.BONUS.format(19, "103100/4990", 897), 2, 1969)]
        kept, removed = select(results, k=4, max_per_document=2)
        self.assertEqual([r["id"] for r in kept], ["a"])
        self.assertEqual(removed[0]["of"], "a")

    def test_the_literal_rule_counts_every_digit(self):
        results = [result("a", 1, self.BONUS.format(18, "111700/6570", 808), 1), result("b", 2, self.BONUS.format(19, "103100/4990", 897), 2)]
        kept, _ = select(results, k=4, max_per_document=2, number_rule="digits")
        self.assertEqual([r["id"] for r in kept], ["a", "b"])

    def test_among_repeats_the_newest_act_takes_the_place(self):
        results = [result("old", 1, self.BONUS.format(18, "111700/6570", 808), 1, 1969), result("other", 2, OTHER, 2, 1980),
                   result("new", 3, self.BONUS.format(19, "103100/4990", 897), 3, 1970)]
        kept, removed = select(results, k=4, max_per_document=2)
        self.assertEqual([(r["id"], r["n"]) for r in kept], [("new", 1), ("other", 2)])
        self.assertEqual([(r["id"], r["reason"], r["of"]) for r in removed], [("old", "near-duplicate", "new")])

    def test_a_newer_repeat_is_found_even_after_all_places_are_taken(self):
        results = [result("old", 1, self.BONUS.format(18, "111700/6570", 808), 1, 1969), result("next", 2, OTHER, 2),
                   result("late", 3, LEAVE, 3), result("new", 4, self.BONUS.format(19, "103100/4990", 897), 4, 1970)]
        kept, _ = select(results, k=2, max_per_document=2)
        self.assertEqual([r["id"] for r in kept], ["new", "next"])

    def test_a_repeat_with_an_unknown_year_or_an_older_year_doesnt_replace(self):
        for year in (None, 1950):
            results = [result("kept", 1, self.BONUS.format(18, "111700/6570", 808), 1, 1969),
                       result("other", 2, self.BONUS.format(19, "103100/4990", 897), 2, year)]
            self.assertEqual([r["id"] for r in select(results, k=4)[0]], ["kept"])

    def test_a_newer_repeat_respects_the_limit_per_document(self):
        results = [result("old", 1, self.BONUS.format(18, "111700/6570", 808), 1, 1969), result("x", 2, OTHER, 2, 1970),
                   result("y", 2, LEAVE, 3, 1970), result("new", 2, self.BONUS.format(19, "103100/4990", 897), 4, 1970)]
        kept, removed = select(results, k=4, max_per_document=2)
        self.assertEqual([r["id"] for r in kept], ["old", "x", "y"])
        self.assertEqual(removed[-1]["id"], "new")

    def test_rule_numbers(self):
        self.assertEqual(rule_numbers("σε 16 εβδομάδες, δηλαδή πέντε ημέρες και 10%, δρχ. 27.012"),
                         {("16", "εβδομάδα"), ("5", "ημέρα"), ("10", "%"), ("27012", "δραχμή")})
        self.assertEqual(rule_numbers("Άρθρ. 8 παρ. 2 του Ν. 1414/1984, Αριθ. 103100/4990 της 10/12 Δεκ. 1970 (ΦΕΚ Β΄897)"), set())


if __name__ == "__main__":
    unittest.main()

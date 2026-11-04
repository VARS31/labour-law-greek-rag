"""Phase 1C parts that run without a database or model: choosing chunks and checking citations."""

import unittest

from labour_rag.citations import check, closest, quote_found
from labour_rag.retrieve import select

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

    def test_answer_without_any_citation_fails(self):
        result = check("Ο μισθωτός δικαιούται είκοσι τέσσερις ημέρες άδεια κάθε χρόνο από το 1945.", CHUNKS)
        self.assertIn("the answer cites no source", result["failures"])

    def test_warnings(self):
        result = check("Ο μισθωτός δικαιούται άδεια με αποδοχές [1]. Η άδεια αυτή δίνεται κάθε ημερολογιακό έτος "
                       "σε όλους τους εργαζόμενους.", CHUNKS, NOTE)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["warnings"]), 3)          # uncited sentence, no year, no closing note


def result(rid, doc, text, rank):
    return {"id": rid, "doc_id": doc, "text": text, "rank": rank}


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


if __name__ == "__main__":
    unittest.main()

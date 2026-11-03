"""Article marker detection, with real strings from the dataset."""

import unittest

from labour_rag.articles import describe, find_markers
from labour_rag.normalize import normalize


def labels(text):
    return [describe(m)[0] for m in find_markers(text)]


def numbers(text):
    return [describe(m)[1] for m in find_markers(text)]


class Markers(unittest.TestCase):
    def test_main_styles(self):
        self.assertEqual(labels("Άρθρ.1.-Έκαστος εν γένει τελωνειακός υπόλογος"), ["Άρθρο 1"])
        self.assertEqual(labels("απφασίζουμε: Άρθρο 1 Διάρθρωση και αρμοδιότητες"), ["Άρθρο 1"])
        self.assertEqual(labels("μολυβδούχων χρωμάτων. Άρθρον 1 Απαγορεύεται εις τας εργασίας"), ["Άρθρο 1"])
        self.assertEqual(labels("Άρθρ.2.–1.Έκαστον Μέλος οφείλει"), ["Άρθρο 2"])

    def test_single_article_acts(self):
        self.assertEqual(labels("χωροφυλάκων Άρθρον μόνον.-Οσάκις λόγοι"), ["Άρθρο μόνο"])
        self.assertEqual(labels("Νομαρχιακών Ταμείων Άρθρο μόνο.-1.Το τακτικό"), ["Άρθρο μόνο"])
        self.assertEqual(numbers("Άρθρο μόνο.-1.Το τακτικό"), [[]])

    def test_ordinals_and_roman_numerals(self):
        self.assertEqual(numbers("Ευρωπαϊκής Ένωσης. Αρθρο πρώτο Κυρώνεται"), [[1]])
        self.assertEqual(labels("ψαν την παρούσα Σύμβαση. Άρθρον δεύτερον Δια Β.Δ/τος"), ["Άρθρο δεύτερο"])
        self.assertEqual(numbers("Άρθρο ΙΙ Το παρόν"), [[2]])

    def test_damaged_forms(self):
        self.assertEqual(numbers("Συλλόγου. Αρθρ.26.-Η Πρόεδρος εκάστου"), [[26]])
        self.assertEqual(numbers("ΑΡΘΡΟ 5 Οι εργοδότες"), [[5]])
        self.assertEqual(numbers(normalize("Πρόνοιας, αποφασίζουμε: ΄Αρθρ.1.-Αυξάνονται")), [[1]])
        self.assertEqual(numbers(normalize("άμεσα. Άρθρo 3 Η εφαρμογή")), [[3]])

    def test_ranges_and_inserted_articles(self):
        self.assertEqual(describe(find_markers("μόλυβδον. Άρθρ.13-19.-(Καταργήθηκαν από την")[0]),
                         ("Άρθρα 13-19", list(range(13, 20))))
        self.assertEqual(labels("1967. Άρθρ.5 δις.-1.Χαριστική προθεσμία"), ["Άρθρο 5 δις"])

    def test_heading_glued_before_marker(self):
        text = "γχου τροφίμων. Φυτοτεχνολόγοι Άρθρ.4.-1.Παροχή βοηθητικής εργασίας"
        markers = find_markers(text)
        self.assertEqual(len(markers), 1)
        self.assertEqual(text[markers[0].start():][:7], "Άρθρ.4.")

    def test_reading_order(self):
        text = "Άρθρον 9 Η παρούσα σύμβασις. 15.Λ.β.3 Άρθρον 10 Ευθύς ως αι επικυρώσεις. Άρθρον 1 Έκαστον μέλος"
        self.assertEqual(numbers(text), [[9], [10], [1]])


class References(unittest.TestCase):
    """References to other texts must not be read as markers."""

    def test_lowercase_references(self):
        self.assertEqual(labels("Κατηργήθη δια του άρθρ. 12 Α.Ν. 1836/1951"), [])
        self.assertEqual(labels("σύμφωνα με τις διατάξεις του άρθρου 3"), [])

    def test_bracketed_and_qualified_references(self):
        self.assertEqual(labels("φυτών μεγάλης καλλιέργειας. (Άρθρ. 1 του Ν.Δ. 131/1974 ΦΕΚ 320Α΄)"), [])
        self.assertEqual(labels("Άρθρ. 5 παρ. 2 του παρόντος"), [])
        self.assertEqual(labels("ες αρχές του παρόντος άρθρου.(Άρθρο 3 της οδηγίας 89/608/ΕΟΚ) Η υπο"), [])

    def test_qualified_reference_without_bracket(self):
        # The Phase 0 regex read "Άρθρο 3 της" as a marker (its letter suffix swallowed the "τ").
        self.assertEqual(labels("όπως ορίζεται. Άρθρο 3 της οδηγίας"), [])
        # And "Άρθρο 15 της" must not shrink to "Άρθρο 1".
        self.assertEqual(labels("όπως ορίζεται. Άρθρο 15 της οδηγίας"), [])


if __name__ == "__main__":
    unittest.main()

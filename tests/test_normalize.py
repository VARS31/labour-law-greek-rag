"""Normalisation, with real strings from the dataset (docs/data-exploration.md and volume 41)."""

import unittest

from labour_rag.normalize import fold, normalize, normalize_with_counts


class MicroSign(unittest.TestCase):
    def test_micro_sign_becomes_greek_mu(self):
        self.assertEqual(normalize("“Έξοδος Ολυµπιακής Αεροπορίας Α.Ε. από το δηµόσιο"),
                         "“Έξοδος Ολυμπιακής Αεροπορίας Α.Ε. από το δημόσιο")


class LookAlikes(unittest.TestCase):
    def test_latin_letters_inside_greek_words_become_greek(self):
        self.assertEqual(normalize("τoυ τωv"), "του των")
        self.assertEqual(normalize("Άρθρo 3"), "Άρθρο 3")
        self.assertEqual(normalize("AΠΟΦΑΣΗ ΥΠΟΥΡΓΟΥ"), "ΑΠΟΦΑΣΗ ΥΠΟΥΡΓΟΥ")
        self.assertEqual(normalize("στην αίθουσα του Υπουργείoυ Εργασίας"), "στην αίθουσα του Υπουργείου Εργασίας")

    def test_latin_words_with_greek_letters_become_latin(self):
        self.assertEqual(normalize("Εurοpοl"), "Europol")
        self.assertEqual(normalize("ΚG"), "KG")
        self.assertEqual(normalize("άρθρο ΙV"), "άρθρο IV")
        self.assertEqual(normalize("140dΒ"), "140dB")

    def test_real_mixed_units_are_left_alone(self):
        self.assertEqual(normalize("50 μg/m3"), "50 μg/m3")
        self.assertEqual(normalize("(VITIS L.)"), "(VITIS L.)")


class SpacingTonos(unittest.TestCase):
    def test_tonos_before_vowel_joins_it(self):
        self.assertEqual(normalize("εν ΄Αργει"), "εν Άργει")
        self.assertEqual(normalize("ΦΕΚ 10/4.2.85 τ.Α΄). ΄Αρθρ.2.-Η αμοιβή"), "ΦΕΚ 10/4.2.85 τ.Α΄). Άρθρ.2.-Η αμοιβή")
        self.assertEqual(normalize("κουρείων. ΄Εχοντες υπ’ όψιν"), "κουρείων. Έχοντες υπ’ όψιν")
        self.assertEqual(normalize("αποφασίζουμε: ΄ Αρθρο Μόνο"), "αποφασίζουμε: Άρθρο Μόνο")

    def test_numeral_sign_and_apostrophe_are_kept(self):
        for text in ["(ΦΕΚ Α΄ 57)", "Γ΄ Διεθνούς Συνδιασκέψεως", "κατ΄Αύγουστον του 1821", "ΦΕΚ Β΄1426"]:
            self.assertEqual(normalize(text), text)

    def test_single_letter_word_is_not_guessed(self):
        self.assertEqual(normalize("εργασίες. ΄ Ο ΠΡΟΕΔΡΟΣ"), "εργασίες. ΄ Ο ΠΡΟΕΔΡΟΣ")


class SymbolFont(unittest.TestCase):
    def test_symbol_quotes_become_guillemets(self):
        self.assertEqual(normalize("Β.Δ/μα περί ατμολεβήτων, τον Ν. 6422"),
                         "Β.Δ/μα «περί ατμολεβήτων», τον Ν. 6422")

    def test_symbol_characters_are_mapped(self):
        self.assertEqual(normalize("βαριά σωματική 65"), "βαριά σωματική >65")
        self.assertEqual(normalize("100  "), "100 × Σ")

    def test_bracket_pieces_are_dropped(self):
        self.assertEqual(normalize("10log 10   x"), "10log 10 x")


class InvisibleAndSpaces(unittest.TestCase):
    def test_soft_hyphen_removed(self):
        self.assertEqual(normalize("Ν. 4035/1960 (Α\xad 15)"), "Ν. 4035/1960 (Α 15)")

    def test_no_break_spaces_become_spaces(self):
        self.assertEqual(normalize("αναφέρθηκαν.\xa0ΚΕΦΑΛΑΙΟΝ Γ΄"), "αναφέρθηκαν. ΚΕΦΑΛΑΙΟΝ Γ΄")

    def test_nfc(self):
        self.assertEqual(normalize("άρθρο"), "άρθρο")          # alpha with oxia -> alpha with tonos
        self.assertEqual(normalize("άρθρο"), "άρθρο")         # decomposed accent


class BrokenWords(unittest.TestCase):
    def test_split_capitals_are_joined(self):
        self.assertEqual(normalize("84. ΑΠΟΦΑΣΗ ΥΠΟΥΡΓΟΥ ΕΡΓ ΑΣΙΑΣ Αριθ. 50257"), "84. ΑΠΟΦΑΣΗ ΥΠΟΥΡΓΟΥ ΕΡΓΑΣΙΑΣ Αριθ. 50257")
        self.assertEqual(normalize("ΟΡΓ ΑΝΙΣΜΟΥ ΑΠΑΣΧΟΛΗΣΕΩΣ"), "ΟΡΓΑΝΙΣΜΟΥ ΑΠΑΣΧΟΛΗΣΕΩΣ")
        self.assertEqual(normalize("ΠΡ ΑΞΙΣ ΥΠΟΥΡΓΙΚΟΥ"), "ΠΡΑΞΙΣ ΥΠΟΥΡΓΙΚΟΥ")

    def test_real_word_pairs_are_not_joined(self):
        self.assertEqual(normalize("ΥΠΕΡ ΑΥΤΩΝ"), "ΥΠΕΡ ΑΥΤΩΝ")
        self.assertEqual(normalize("ΚΕΦΑΛΑΙΟΝ Γ ΑΡΜΟΔΙΟΤΗΤΕΣ"), "ΚΕΦΑΛΑΙΟΝ Γ ΑΡΜΟΔΙΟΤΗΤΕΣ")

    def test_number_glued_to_word_is_split(self):
        self.assertEqual(normalize("Προεδρικό Διάταγμα 1991/508Ποσό σύνταξης"), "Προεδρικό Διάταγμα 1991/508 Ποσό σύνταξης")
        self.assertEqual(normalize("Σελ. 333 -333΄Αδειες μισθωτών"), "Σελ. 333 -333 Άδειες μισθωτών")


class Questions(unittest.TestCase):
    def test_clean_text_is_unchanged(self):
        question = "Πόσες ημέρες άδεια δικαιούται ο μισθωτός μετά από ένα έτος εργασίας;"
        self.assertEqual(normalize(question), question)

    def test_idempotent(self):
        text = "΄Αρθρ.2.-Η αμοιβή τoυ ΕΡΓ ΑΣΙΑΣ µισθωτού"
        self.assertEqual(normalize(normalize(text)), normalize(text))

    def test_counts(self):
        _, counts = normalize_with_counts("τoυ δηµόσιο")
        self.assertEqual(counts["micro_sign"], 1)
        self.assertEqual(counts["lookalike_words_to_greek"], 1)

    def test_fold(self):
        self.assertEqual(fold("Εργατικά  Ατυχήματα"), "εργατικα ατυχηματα")


if __name__ == "__main__":
    unittest.main()

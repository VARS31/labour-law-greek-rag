"""Printed-page noise removal, with real strings from volume 41."""

import unittest

from labour_rag.normalize import fold
from labour_rag.noise import learn_running_titles, strip_page_noise


def titles(*names):
    return {fold(n): n for n in names}


OAED = "Ασφάλιση κατά της Ανεργίας Οργ/σμός Απασ/σης Εργατ/κού Δυν/κού (Ο.Α.Ε.Δ.)"


class Strip(unittest.TestCase):
    def test_full_header_inside_a_sentence(self):
        text = (f"κατά το χρονικό διάστημα από 1 (Αντί για τη σελ. 91(θ) Σελ. 91(ι) Τεύχος 1294-Σελ. 33 {OAED} "
                "15.Γ .β.20 Ιανουαρίου έως 30 Απριλίου")
        clean, blocks = strip_page_noise(text, titles(OAED))
        self.assertEqual(clean, "κατά το χρονικό διάστημα από 1 Ιανουαρίου έως 30 Απριλίου")
        self.assertEqual(len(blocks), 1)

    def test_title_and_page_number_around_a_code(self):
        text = ("από τας παραδόσεις. Σελίς 271 Διεθνείς Συμβάσεις περί Κυριακής Αργίας 15.Κ.β.1 21 Άρθρον 3 "
                "Έκαστον μέλος")
        clean, _ = strip_page_noise(text, titles("Διεθνείς Συμβάσεις περί Κυριακής Αργίας"))
        self.assertEqual(clean, "από τας παραδόσεις. Άρθρον 3 Έκαστον μέλος")

    def test_page_number_before_a_code(self):
        text = "άνευ επιζημίου τινός συνεπείας δι’ αυτόν. 451 15.Β.β.4 Οργανισμός Εργατικής Κατοικίας Άρθρ.19.-Αντιπροσφοραί"
        clean, _ = strip_page_noise(text, titles("Οργανισμός Εργατικής Κατοικίας"))
        self.assertEqual(clean, "άνευ επιζημίου τινός συνεπείας δι’ αυτόν. Άρθρ.19.-Αντιπροσφοραί")

    def test_word_cut_by_a_page_break_is_joined(self):
        text = "να υποβάλη εις την γενικήν συνδιάσκεΣελ.70(α) Τεύχος1294-Σελ.2 ψιν έκθεσιν"
        clean, blocks = strip_page_noise(text, {})
        self.assertEqual(clean, "να υποβάλη εις την γενικήν συνδιάσκεψιν έκθεσιν")
        self.assertTrue(blocks[0]["rejoined"])

    def test_cross_references_are_kept(self):
        text = "(Καταργήθηκαν από την παρ. 3 άρθρ. 17 του Π.Δ. 94/1987, ανωτ. σελ. 306,823). τόμ. 2Α σελ. 354"
        self.assertEqual(strip_page_noise(text, {})[0], text)

    def test_unknown_words_next_to_a_code_are_kept(self):
        clean, _ = strip_page_noise("δημοσιευθήτω. 15.Λ.α.54 Κάποιος άγνωστος τίτλος εδώ", {})
        self.assertEqual(clean, "δημοσιευθήτω. Κάποιος άγνωστος τίτλος εδώ")

    def test_weak_title_followed_by_text_is_kept(self):
        # A chapter name that is also the heading of a form must survive.
        text = "15.Γ .β.24 Καταγγελία συμβάσεως εργασίας (Αριθ. υποδείγμ. 1) Προς τον"
        clean, _ = strip_page_noise(text, {}, weak_titles=titles("Καταγγελία συμβάσεως εργασίας"))
        self.assertEqual(clean, "Καταγγελία συμβάσεως εργασίας (Αριθ. υποδείγμ. 1) Προς τον")

    def test_code_with_letter_suffix(self):
        clean, _ = strip_page_noise("της Κυβερνήσεως. 15.Λ.α.6α Υγιεινή και ασφάλεια χώρων εργασίας και εργαζομένων "
                                    "Άρθρ.3.-Όταν", titles("Υγιεινή και ασφάλεια χώρων εργασίας και εργαζομένων"))
        self.assertEqual(clean, "της Κυβερνήσεως. Άρθρ.3.-Όταν")


class Learn(unittest.TestCase):
    def test_title_between_anchors_seen_twice_is_learned(self):
        texts = ["α. Σελ. 41 Οργανισμός Εργατικής Εστίας 15.Β.α.1 β.", "γ. Σελ. 57(β) Οργανισμός Εργατικής Εστίας 15.Β.α.6 δ."]
        self.assertEqual(list(learn_running_titles(texts).values()), ["Οργανισμός Εργατικής Εστίας"])

    def test_seen_once_or_fragment_is_not_learned(self):
        self.assertEqual(learn_running_titles(["Σελ. 41 Οργανισμός Εργατικής Εστίας 15.Β.α.1"]), {})
        self.assertEqual(learn_running_titles(["Σελ. 1 α 15.Β.α.1", "Σελ. 2 α 15.Β.α.2"]), {})


if __name__ == "__main__":
    unittest.main()

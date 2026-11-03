"""Header parsing and chunking rules, with real documents from volume 41."""

import unittest

from labour_rag.chunking import Piece, chunk_document, merge_small, move_trailing_headings, split_document, split_words
from labour_rag.header import citation, parse_header

TYPICAL = ("14. ΝΟΜΟΣ υπ’ αριθ. 751 της 4/10 Αυγ. 1948 Περί προστασίας των απολυομένων εκ των υπηρετούντων εις "
           "τας τάξεις του στρατού κατά την διάρκειαν της παρούσης κατά του Έθνους συμμοριακής δράσεως. "
           "Τροποποιηθείς και συμπληρωθείς υπό των α)Ν.Δ. 1196 της 7/18 Οκτωβρ. 1949. "
           "Κατηργήθη δια του άρθρ. 12 Α.Ν. 1836/1951 κατωτ. αριθ. 15.")
DOC = {"doc_id": 15034, "split": "train", "volume": "ΕΡΓΑΤΙΚΗ ΝΟΜΟΘΕΣΙΑ", "chapter": "Κ", "subject": "Σ"}


class Header(unittest.TestCase):
    def test_law(self):
        meta = parse_header(TYPICAL)
        self.assertEqual((meta["act_type"], meta["act_number"], meta["year"], meta["fek"]), ("Νόμος", "751", 1948, None))
        self.assertTrue(meta["title"].startswith("Περί προστασίας") and meta["title"].endswith("δράσεως"))

    def test_joint_decision_with_fek(self):
        meta = parse_header("9. ΑΠΟΦΑΣΙΣ ΠΡΩΘΥΠΟΥΡΓΟΥ ΚΑΙ ΥΠΟΥΡΓΩΝ ΣΥΝΤΟΝΙΣΜΟΥ ΚΑΙ ΠΡΟΓΡΑΜΜΑΤΙΣΜΟΥ ΒΙΟΜΗΧΑΝΙΑΣ ΚΑΙ "
                            "ΑΠΑΣΧΟΛΗΣΕΩΣ Αριθ. 8371/1583 της 4/4 Δεκ. 1973 (ΦΕΚ Β΄1426) Περί αναπροσαρμογής "
                            "κατωτάτων ορίων μισθών ιδιωτικών υπαλλήλων.")
        self.assertEqual(meta["fek"], "Β΄ 1426")
        self.assertEqual(citation(meta), "Κ.Υ.Α. 8371/1583/1973")

    def test_number_without_arith(self):
        self.assertEqual(citation(parse_header("3. ΝΟΜΟΣ 2994 της 3/31 Αυγ. 1922 Περί κυρώσεως της διεθνούς")),
                         "Ν. 2994/1922")

    def test_headerless_presidential_decree(self):
        meta = parse_header("Προεδρικό Διάταγμα 1991/508 Ποσό σύνταξης των μερικώς απασχολουμένων. - Ο ΠΡΟΕΔΡΟΣ")
        self.assertEqual(citation(meta), "Π.Δ. 508/1991")
        self.assertEqual(meta["title"], "Ποσό σύνταξης των μερικώς απασχολουμένων")

    def test_unclosed_fek_and_abbreviation_in_title(self):
        meta = parse_header("54. ΠΡΟΕΔΡΙΚΟ ΔΙΑΤΑΓΜΑ υπ’ αριθ. 17 της 18 - 18 Ιαν. 1996 (ΦΕΚ Α΄ 110 Μέτρα για τη βελτίωση")
        self.assertEqual((meta["fek"], meta["title"]), ("Α΄ 110", "Μέτρα για τη βελτίωση"))
        meta = parse_header("58. ΑΠΟΦΑΣΗ ΥΠΟΥΡΓΩΝ ΕΘΝΙΚΗΣ ΟΙΚΟΝΟΜΙΑΣ Αριθ. 52545 της 7/13 Οκτ. 1988 (ΦΕΚ Β΄ 747) "
                            "Τροποποίηση της κοινής Απόφασης των Υπουργών Εθν. Οικονομίας και Εργασίας. Έχοντας υπόψη:")
        self.assertEqual(meta["title"], "Τροποποίηση της κοινής Απόφασης των Υπουργών Εθν. Οικονομίας και Εργασίας")


class Rules(unittest.TestCase):
    def test_windows_respect_limit_and_overlap(self):
        words = [f"w{i}" for i in range(1200)]
        windows = split_words(words, max_words=500, overlap=50)
        self.assertTrue(all(len(w) <= 500 for w in windows))
        self.assertEqual(windows[0][0], "w0")
        self.assertEqual(windows[-1][-1], "w1199")
        for a, b in zip(windows, windows[1:]):
            shared = len(set(a) & set(b))
            self.assertTrue(40 <= shared <= 60, shared)

    def test_small_pieces_are_merged(self):
        pieces = [Piece("x " * 10, "preamble", ["Προοίμιο"]), Piece("y " * 100, "article", ["Άρθρο 1"], [1]),
                  Piece("Άρθρ.13-19.-(Καταργήθηκαν)", "article", ["Άρθρα 13-19"], list(range(13, 20)))]
        merged = merge_small(pieces)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].labels, ["Προοίμιο", "Άρθρο 1", "Άρθρα 13-19"])

    def test_heading_moves_to_its_article(self):
        pieces = [Piece("Άρθρ.16.-… προς το οποίον οδηγεί η κλίμαξ. Φορηταί κλίμακες", "article"),
                  Piece("Άρθρ.17.-Αι φορηταί κλίμακες", "article")]
        self.assertEqual(move_trailing_headings(pieces), 1)
        self.assertEqual(pieces[0].text, "Άρθρ.16.-… προς το οποίον οδηγεί η κλίμαξ.")
        self.assertEqual(pieces[1].text, "Φορηταί κλίμακες Άρθρ.17.-Αι φορηταί κλίμακες")

    def test_numbered_paragraphs_after_the_decision_formula(self):
        text = ("15. ΑΠΟΦΑΣΙΣ ΥΠΟΥΡΓΟΥ ΕΡΓΑΣΙΑΣ Αριθ. 35025/2363 της 23/24 Αυγ. 1976 Περί αυξήσεως. Έχοντες υπ’ όψει: "
                "1.Τας διατάξεις του Ν.Δ. 212/1969. 2.Την γνώμην του Συμβουλίου, αποφασίζομεν: "
                "1.Αυξάνομεν κατά 25% τα ημερομίσθια. 2.Η ισχύς της παρούσης άρχεται από της δημοσιεύσεως.")
        method, pieces = split_document(text)
        self.assertEqual(method, "paragraph")
        self.assertEqual([p.labels for p in pieces], [["Προοίμιο"], ["παρ. 1"], ["παρ. 2"]])
        self.assertTrue(pieces[0].text.endswith("αποφασίζομεν:"))


class Records(unittest.TestCase):
    def test_flags_and_embed_text(self):
        (record,) = chunk_document(DOC, TYPICAL, parse_header(TYPICAL))
        self.assertEqual(record["id"], "glc-15034-000")
        self.assertEqual(record["method"], "whole")
        self.assertTrue(record["is_note"])          # header + editorial note, no rules
        self.assertFalse(record["is_stub"])         # 52 words
        self.assertEqual(record["repeal_sentences"], ["Κατηργήθη δια του άρθρ. 12 Α.Ν. 1836/1951 κατωτ. αριθ. 15."])
        self.assertTrue(record["embed_text"].startswith("Ν. 751/1948, Περί προστασίας των απολυομένων"))

    def test_stub(self):
        text = "2. ΑΝΑΓΚ.ΝΟΜΟΣ της 11/12 Νοεμ. 1935 Περί Οργανισμού του Υπουργείου Εργασίας."
        (record,) = chunk_document(DOC, text, parse_header(text))
        self.assertTrue(record["is_stub"])
        self.assertFalse(record["is_note"])
        self.assertEqual(record["embed_text"].split("\n")[0], "Α.Ν. (1935), Περί Οργανισμού του Υπουργείου Εργασίας")


if __name__ == "__main__":
    unittest.main()

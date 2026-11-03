"""Header parsing and chunking rules, with real documents from volume 41."""

import unittest

from labour_rag.chunking import (Piece, chunk_document, merge_small, move_trailing_headings, note_words,
                                 repeal_sentences, split_document, split_words)
from labour_rag.header import citation, parse_header

TYPICAL = ("14. ΝΟΜΟΣ υπ’ αριθ. 751 της 4/10 Αυγ. 1948 Περί προστασίας των απολυομένων εκ των υπηρετούντων εις "
           "τας τάξεις του στρατού κατά την διάρκειαν της παρούσης κατά του Έθνους συμμοριακής δράσεως. "
           "Τροποποιηθείς και συμπληρωθείς υπό των α)Ν.Δ. 1196 της 7/18 Οκτωβρ. 1949. "
           "Κατηργήθη δια του άρθρ. 12 Α.Ν. 1836/1951 κατωτ. αριθ. 15.")
DOC = {"doc_id": 15034, "split": "train", "volume": "ΕΡΓΑΤΙΚΗ ΝΟΜΟΘΕΣΙΑ", "chapter": "ΔΙΟΙΚΗΣΗ ΕΡΓΑΣΙΑΣ",
       "subject": "ΟΡΓΑΝΙΣΜΟΣ ΥΠΟΥΡΓΕΙΟΥ ΕΡΓΑΣΙΑΣ"}


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

    def test_stub_without_number_uses_the_fallback_source(self):
        text = "2. ΑΝΑΓΚ.ΝΟΜΟΣ της 11/12 Νοεμ. 1935 Περί Οργανισμού του Υπουργείου Εργασίας."
        (record,) = chunk_document(DOC, text, parse_header(text))
        self.assertTrue(record["is_stub"])
        self.assertFalse(record["is_note"])
        self.assertTrue(record["citation_fallback"])
        self.assertEqual(record["embed_text"].split("\n")[0],
                         "Α.Ν. «Περί Οργανισμού του Υπουργείου Εργασίας» (ΔΙΟΙΚΗΣΗ ΕΡΓΑΣΙΑΣ, 1935)")

    def test_headerless_document_names_title_and_chapter(self):
        text = ("Ελάχιστες προδιαγραφές για τη βελτίωση της προστασίας των εργαζομένων στις εξορυκτικές βιομηχανίες. "
                "Άρθρο 1 Αντικείμενο Το παρόν διάταγμα ορίζει τις ελάχιστες προδιαγραφές για τους χώρους εργασίας.")
        records = chunk_document(DOC, text, parse_header(text))
        self.assertTrue(all(r["citation_fallback"] for r in records))
        self.assertEqual(records[-1]["embed_text"].split("\n")[0],
                         "«Ελάχιστες προδιαγραφές για τη βελτίωση της προστασίας των εργαζομένων στις εξορυκτικές "
                         "βιομηχανίες» (ΔΙΟΙΚΗΣΗ ΕΡΓΑΣΙΑΣ), Προοίμιο, Άρθρο 1")


class Notes(unittest.TestCase):
    """is_note: only when the note is the main content (real snippets from volume 41)."""

    def share(self, body):
        return note_words(body) / len(body.split())

    def test_run_of_numbered_bracket_notes(self):      # glc-00401-001
        body = ("(Προστίθεται φράσις εν τέλει της πρώτης περιόδου της παρ. 1 άρθρ. 1 Α.Ν. 99/67 (σελ. 100,3)). "
                "2.(Διαγράφεται η πρώτη περίοδος της παρ. 3 άρθρ. 1 Α.Ν. 99/67).")
        self.assertEqual(self.share(body), 1)

    def test_followed_by_more_editorial_sentences(self):     # glc-05131-000
        body = ("Τροποποιήθηκε από την υπ’ αριθ. 108285/19-30 Μαρτ. 1999 (ΦΕΚ Β΄ 272) απ. Υπ. Εργασ. και Κοιν. "
                "Ασφαλίσεων. Επίσης τροποποιήθηκε και συμπληρώθηκε από την 119442/11-30 Δεκ. 1999 (ΦΕΚ Β΄ 2243).")
        self.assertEqual(self.share(body), 1)

    def test_source_reference_before_law_text_is_not_a_note(self):     # glc-34649-016
        body = ("(άρθρ. 18 Δ. 23 Νοεμ. 1928, άρθρ. 7 ν. 4388). 1.Κατά τας Κυριακάς και τας εορτάς των Χριστουγέννων "
                "και του Ευαγγελισμού τα κουρεία μένουν κλειστά καθ’ όλην την ημέραν.")
        self.assertLess(self.share(body), 0.5)

    def test_lost_bracket_counts_only_its_first_sentence(self):     # glc-13904-015
        first = ("(Προέβλεπε την ίδρυσιν Ειδικού Γραφείου Προστασίας Π.Π. παρά τω Τμήματι Ανεργίας του Υπουργείου "
                 "Εργασίας.")
        body = (first + " Η αρμοδιότης αύτη υπήχθη εις το Τμήμα Τοποθετήσεως εις Εργασίας δια του Άρθρον 29 "
                "1.Διευθυνταί ή μέλη του διοικητικού συμβουλίου ανωνύμων εταιριών τιμωρούνται δια χρηματικής "
                "ποινής (10.000 έως 50.000 δραχ.), εν υποτροπή δε και δια φυλακίσεως. " * 2 + "(κατωτ. αρ. 9).")
        self.assertEqual(note_words(body), len(first.split()))


class Repeals(unittest.TestCase):
    def test_bracketed_note(self):     # glc-00000-000
        text = ("μεταλλικόν μόλυβδον. Άρθρ.13-19.-(Καταργήθηκαν από την παρ. 3 άρθρ. 17 του Π.Δ. 94/10-22 Απρ. 1987 "
                "(ΦΕΚ Α΄ 54), ανωτ. σελ. 306,823). Άρθρ.20.-Η ισχύς")
        self.assertEqual(repeal_sentences(text), ["(Καταργήθηκαν από την παρ. 3 άρθρ. 17 του Π.Δ. 94/10-22 Απρ. 1987 "
                                                  "(ΦΕΚ Α΄ 54), ανωτ. σελ. 306,823)"])

    def test_only_the_short_clause_around_the_verb(self):     # glc-45189-025
        text = ("1.-Η Διεύθυνση Όρων Εργασίας απαρτίζεται από τα εξής Τμήματα: α)Τμήμα Ατομικής Σύμβασης Εργασίας "
                "β)Τμήμα Χρονικών Ορίων Εργασίας γ)(Τμήμα Κανονισμών Εργασίας) Το μέσα ( ) Τμήμα Κανονισμών Εργασίας "
                "(περ. γ΄) καταργήθηκε & οι αρμοδιότητές του μεταφέρθηκαν στα Τμήματα Ατομικής Σύμβασης Εργασίας. "
                "δ)Τμήμα Ισότητας Φύλων 2.-Οι αρμοδιότητες")
        (sentence,) = repeal_sentences(text)
        self.assertTrue(sentence.startswith("γ)(Τμήμα Κανονισμών Εργασίας)"))
        self.assertTrue(sentence.endswith("Ατομικής Σύμβασης Εργασίας."))

    def test_abbreviation_does_not_end_the_sentence(self):     # glc-13034-000
        text = "Εκ των ανωτέρω, οι υπό στοιχ. β΄ και δ΄ κατηργήθησαν και δια της Πράξεως Υπουργ. Συμβουλίου αριθ. 325."
        self.assertEqual(repeal_sentences(text), [text])


if __name__ == "__main__":
    unittest.main()

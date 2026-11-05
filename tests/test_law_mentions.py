"""Finding law mentions in chunk text. The examples are real sentences from the chunks."""

import unittest

from labour_rag.law_mentions import find_mentions, names_a_law, resolve


def laws(text):
    return [(m.abbr, m.number, m.year) for m in find_mentions(text)]


class Forms(unittest.TestCase):
    def test_number_and_year(self):
        self.assertEqual(laws("Δια το ηυξημένον ωρομίσθιον των υπερωριών βλ. ήδη άρθρ. 1 Νόμ. 435/1976 (τόμ. 15)."),
                         [("Ν.", "435", 1976)])

    def test_two_digit_year(self):
        self.assertEqual(laws("του άρθρ. 8 του Ν.Δ. 4020/59 και του Α.Ν. 435 / 68"),
                         [("Ν.Δ.", "4020", 1959), ("Α.Ν.", "435", 1968)])

    def test_number_followed_by_a_date(self):
        self.assertEqual(laws("βλέπε άρθρ. 22 Νόμ. 2556/23-24 Δεκ. 1997 (ΦΕΚ Α΄ 270)"), [("Ν.", "2556", 1997)])
        self.assertEqual(laws("άρθρο μόνο Π.Δ. 180/28 Απρ.-10 Μαΐου 1993"), [("Π.Δ.", "180", 1993)])

    def test_date_with_spaces_around_the_dash_is_not_a_year(self):
        self.assertEqual(laws("κυρώθηκε με το άρθρ. 22 Νόμ. 2556/23 – 24 Δεκ. 1997 (ΦΕΚ Α΄270)"), [("Ν.", "2556", 1997)])

    def test_date_only_decree_written_in_digits(self):
        self.assertEqual(laws("άρθρ. 18 του Π.Δ. 8/13.4.32"), [])

    def test_year_before_number(self):
        self.assertEqual(laws("ΠΡΟΕΔΡΙΚΟ ΔΙΑΤΑΓΜΑ 1990/198 Λειτουργία"), [("Π.Δ.", "198", 1990)])

    def test_year_at_the_end_of_a_sentence(self):
        self.assertEqual(laws("οι ποινικές κυρώσεις του άρθρ. 25 του Νόμ. 2224/94."), [("Ν.", "2224", 1994)])

    def test_date_in_digits(self):
        self.assertEqual(laws("πολιτικού μηχανικού (άρθρ. 113 Π.Δ. 1073/16-9-81 ΦΕΚ 260/Α)"), [("Π.Δ.", "1073", 1981)])

    def test_number_then_the_word_of_and_a_date(self):
        self.assertEqual(laws("δια του άρθρ. 3 του Ν.Δ. 3755 της 14/17 Σεπτ. 1957"), [("Ν.Δ.", "3755", 1957)])
        self.assertEqual(laws("15. ΝΟΜΟΣ υπ’ αριθ. 1387 της 18/19 Αυγ. 1983 (ΦΕΚ Α΄ 110)"), [("Ν.", "1387", 1983)])
        self.assertEqual(laws("κατά το άρθρον 3 του Νόμου 2943 του 1922"), [("Ν.", "2943", 1922)])

    def test_number_before_the_type(self):
        self.assertEqual(laws("του υπ’ αριθ. 748/66 Β.Δ/τος"), [("Β.Δ.", "748", 1966)])

    def test_no_year(self):
        self.assertEqual(laws("Περί καταβολής κατά το άρθρ. 7 του ν. 2112 (ανωτ. αρ. 1)"), [("Ν.", "2112", None)])

    def test_decree_with_only_a_date_is_not_a_number(self):
        self.assertEqual(laws("του Β.Δ. 16/18 Ιουλ. 1920 και του Π.Δ. της 27/6-4/7/32 και Α.Ν. 16/21 Νοεμ. 1935"), [])

    def test_small_number_with_a_date_range_is_a_number(self):
        self.assertEqual(laws("με το Π.Δ. 94/10-22 Απρ. 1987 (ΦΕΚ Α΄ 54)"), [("Π.Δ.", "94", 1987)])

    def test_prefecture_and_plain_words_are_not_laws(self):
        self.assertEqual(laws("Ανθοπωλεία Νομού Λαρίσης. Ο νόμος αυτός ισχύει. 1ν.Για υπηρεσίες παραγωγής"), [])

    def test_abbreviation_inside_another_is_not_counted_twice(self):
        self.assertEqual(laws("Α.Ν. 99/1967"), [("Α.Ν.", "99", 1967)])


class NamesALaw(unittest.TestCase):
    def test_a_law_or_an_article(self):
        for question in ("Τι λέει το άρθρο 2 του Ν. 1837/1989;", "Τι προβλέπει ο Α.Ν. 380/1968 για την Πρωτομαγιά;",
                         "Τι προβλέπει ο Ν. 4808/2021 για την ψηφιακή κάρτα εργασίας;", "Τι ορίζει το άρθρο 5;"):
            self.assertTrue(names_a_law(question), question)

    def test_other_numbers_dont_count(self):
        for question in ("Η εταιρεία μου έχει 40 άτομα. Πόσες απολύσεις μετράνε ως ομαδικές;",
                         "Ένα παιδί 15 χρονών πόσες ώρες μπορεί να δουλεύει;", "Ποιο άρθρο μιλά για άδεια;"):
            self.assertFalse(names_a_law(question), question)


class Resolve(unittest.TestCase):
    def setUp(self):
        self.documents = {("Ν.", "2112", 1920), ("Α.Ν.", "99", 1936), ("Α.Ν.", "99", 1967)}

    def group(self, *texts):
        mentions = [(m, t) for t in texts for m in find_mentions(t)]
        return resolve(mentions, self.documents)

    def test_law_in_the_data_is_not_missing(self):
        found, missing = self.group("Ν. 2112/1920", "ν. 2112")
        self.assertEqual(len(found[("Ν.", "2112", 1920)]), 2)
        self.assertEqual(missing, {})

    def test_year_one_away_still_counts_as_the_same_law(self):
        found, missing = self.group("Ν. 2112/1921")
        self.assertIn(("Ν.", "2112", 1920), found)
        self.assertEqual(missing, {})

    def test_plain_law_label_on_a_decree_joins_the_decree(self):
        found, missing = self.group("Ν. 99/1967")
        self.assertIn(("Α.Ν.", "99", 1967), found)
        self.assertEqual(missing, {})

    def test_rows_of_one_law_with_near_years_are_joined(self):
        _, missing = self.group("Νόμ. 2224/1994", "Νόμ. 2224/94.", "Νόμ. 2224/1993")
        self.assertEqual({k: len(v) for k, v in missing.items()}, {("Ν.", "2224", 1994): 3})

    def test_rows_of_one_law_with_another_type_join_the_most_mentioned(self):
        _, missing = self.group("Νόμ. 3239/1955", "Ν. 3239/55", "Ν.Δ. 3239/55")
        self.assertEqual({k: len(v) for k, v in missing.items()}, {("Ν.", "3239", 1955): 3})

    def test_law_not_in_the_data_is_missing(self):
        _, missing = self.group("Νόμ. 435/1976", "ν. 435")
        self.assertEqual(len(missing[("Ν.", "435", 1976)]), 2)

    def test_missing_law_without_a_year_is_kept_only_if_its_number_is_large(self):
        _, missing = self.group("ν. 6424", "ν. 12")
        self.assertEqual(list(missing), [("Ν.", "6424", None)])


if __name__ == "__main__":
    unittest.main()

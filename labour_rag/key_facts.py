"""Does an answer contain a key fact? A tolerant check that needs no model.

A fact counts as present when every number in it appears in the answer and enough of its other words do: half of them
if the fact has a number, MIN_WORD_SHARE if it has none. Accents, case and word endings are ignored ("αποδοχές" = "αποδοχών"), and numbers may be written in words
or digits ("τρεις μήνες" = "3 μήνες" = "τρίμηνο"). It can't see meaning: "δεν απαγορεύεται" counts as "απαγορεύεται".
"""

import re

from .citations import CITATION
from .normalize import fold, normalize

MIN_WORD_SHARE = 0.6
MIN_WORD_SHARE_WITH_NUMBERS = 0.5
MIN_PREFIX = 5      # two word stems also match if one starts with the other and the shorter has this many letters

_STOPWORDS = set("""
    ο η το οι τα του της των τον την τη τους τις στο στη στην στον στα στις στους στων σε με απο για και η ως να θα δεν
    που πως οτι αν κι αλλα ομως ενω αυτο αυτη αυτα αυτος ενα εναν ενας μια μιας ενος κατα ανα εως εαν αλλιως ειναι
    αφορα ισχυει οσους οσοι οσες τουλαχιστον πολυ ακομη μονο οταν παρα δια προς μεσα
""".split())
_NUMBER_WORDS = {
    "δυο": 2, "τρεις": 3, "τρια": 3, "τριων": 3, "τεσσερις": 4, "τεσσερα": 4, "τεσσαρες": 4, "τεσσαρων": 4, "πεντε": 5,
    "εξι": 6, "επτα": 7, "εφτα": 7, "οκτω": 8, "οχτω": 8, "εννεα": 9, "εννια": 9, "δεκα": 10, "δωδεκα": 12,
    "δεκατεσσερις": 14, "δεκατεσσαρων": 14, "δεκαπεντε": 15, "εικοσι": 20, "εικοσιπεντε": 25, "εικοσιτεσσερις": 24,
    "τριαντα": 30, "σαραντα": 40, "πενηντα": 50, "εξηντα": 60, "εκατο": 100, "εκατον": 100,
}
# "διμήνου", "τρίμηνο", "πενταετής", "πενθήμερο", "οκτάωρο": a number glued to a unit of time
_NUMBER_PREFIX = re.compile(r"^(δι|τρι|τετρα|πεντα|πενθ|εξα|οκτα|δεκα|δωδεκα|εικοσα)(?=μην|ετ|ωρ|ημερ|εβδομ)")
_PREFIX_VALUE = {"δι": 2, "τρι": 3, "τετρα": 4, "πεντα": 5, "πενθ": 5, "εξα": 6, "οκτα": 8, "δεκα": 10, "δωδεκα": 12,
                 "εικοσα": 20}
HALF = 0.5          # "half" counts as a number: a fact about half a salary is not met by "one salary"
_HALF_WORDS = {"μισο", "μισος", "μιση", "μισης", "μισου", "μισα", "ημισυ", "ημισεος", "ημισεως", "ημισεια", "ημισειαν"}
# Longest first. Enough for the nouns, adjectives and passive verbs in our facts; not a full Greek stemmer.
_ENDINGS = sorted("""
    ουμενος ομενος ομενοι ομενων ομενους ονται εται ουνται ειται ουν ουν ει
    σεων σεις σης ση σεως εως ιων ιας ιες ια ιος ιου ιους ιοι ειας ειες ειων εια
    ους ου ος οι ων ες ας ης εις α η ο ι ε υ
""".split(), key=len, reverse=True)
_WORD = re.compile(r"[^\W\d_]+")
_TIME = re.compile(r"(?<!\d)(\d{1,2})[:.](\d{2})(?!\d)")
_YEAR_AFTER_SLASH = re.compile(r"(\d{3,4})\s*/\s*(\d{2})(?!\d)")


def stem(word):
    """A word without its ending: "αποδοχών" -> "αποδοχ", "απόλυσης" -> "απολυ" (the word must already be folded)."""
    word = word.replace("ς", "σ")
    for ending in _ENDINGS:
        ending = ending.replace("ς", "σ")
        if word.endswith(ending) and len(word) - len(ending) >= 3:
            return word[:-len(ending)]
    return word


def _times_and_numbers(text, is_fact):
    """The numbers in folded text. A time also gives its 12-hour twin, so 21:30 is found in "09.30 το βράδυ"; a fact's
    ":00" asks for nothing, so "06:00" is found in "6 το πρωί"."""
    numbers = set()

    def take_time(match):
        hour, minutes = int(match.group(1)), int(match.group(2))
        if hour <= 24 and minutes < 60:
            numbers.add(hour)
            if not is_fact:
                numbers.update({(hour + 12) % 24, (hour - 12) % 24})
            if minutes or not is_fact:
                numbers.add(minutes)
            return " "
        return match.group(0)

    text = _TIME.sub(take_time, text)
    text = _YEAR_AFTER_SLASH.sub(lambda m: f"{m.group(1)} 19{m.group(2)}", text)   # "1648/86" = "1648/1986"
    numbers.update(int(n) for n in re.findall(r"\d+", text))
    if "1/2" in text:
        numbers.add(HALF)
    return numbers


def parse(text, is_fact=False):
    """(numbers, word stems) of a text. Citations such as [2] are not numbers of the text."""
    folded = fold(normalize(CITATION.sub(" ", text)))
    numbers = _times_and_numbers(folded, is_fact)
    stems = []
    for word in _WORD.findall(folded):
        if word in _HALF_WORDS:
            numbers.add(HALF)
        elif word in _NUMBER_WORDS:
            numbers.add(_NUMBER_WORDS[word])
        elif word == "τεταρτο":
            numbers.update({1, 4})
        elif word not in _STOPWORDS and len(word) > 1:
            prefix = _NUMBER_PREFIX.match(word)
            if prefix:
                numbers.add(_PREFIX_VALUE[prefix.group(1)])
                stems.append(stem(word[prefix.end():]))       # "διμήνου" also counts as "μήνες"
            stems.append(stem(word))
    return numbers, stems


def _word_found(word, answer_stems):
    return any(word == other or (min(len(word), len(other)) >= MIN_PREFIX
                                 and (word.startswith(other) or other.startswith(word))) for other in answer_stems)


def fact_present(fact, answer):
    """True if the fact's numbers are all in the answer and enough of its other words are."""
    fact_numbers, fact_stems = parse(fact, is_fact=True)
    answer_numbers, answer_stems = parse(answer)
    if not fact_numbers <= answer_numbers:
        return False
    if not fact_stems:
        return True
    found = sum(_word_found(word, answer_stems) for word in fact_stems)
    return found / len(fact_stems) >= (MIN_WORD_SHARE_WITH_NUMBERS if fact_numbers else MIN_WORD_SHARE)

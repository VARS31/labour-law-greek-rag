"""Text normalisation for Greek legal text.

Used on the corpus now and on user questions later, so every step is safe on clean text too.
`normalize(text)` returns the cleaned text; `normalize_with_counts(text)` also says how often each
step changed something (for the chunking report).
"""

import collections
import re
import unicodedata

# Word stores a Symbol-font character with code c as U+F000 + c. This table maps codes 0x20-0xFF to
# Unicode, generated from Unicode's Adobe Symbol mapping
# (https://www.unicode.org/Public/MAPPINGS/VENDORS/ADOBE/symbol.txt). "\0" marks a code without a plain
# Unicode equivalent (bracket and radical pieces of big formulas); those are dropped.
_SYMBOL_FONT = (
    ' !∀#∃%&∋()∗+,−./0123456789:;<=>?'
    '≅ΑΒΧΔΕΦΓΗΙϑΚΛΜΝΟΠΘΡΣΤΥςΩΞΨΖ[∴]⊥_'
    '\x00αβχδεφγηιϕκλμνοπθρστυϖωξψζ{|}∼\x00'
    '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    '€ϒ′≤⁄∞ƒ♣♦♥♠↔←↑→↓°±″≥×∝∂•÷≠≡≈…\x00\x00↵'
    'ℵℑℜ℘⊗⊕∅∩∪⊃⊇⊄⊂⊆∈∉∠∇\x00\x00\x00∏√⋅¬∧∨⇔⇐⇑⇒⇓'
    '◊〈\x00\x00\x00∑\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00〉∫⌠\x00⌡\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
)
SYMBOL_QUOTE = ""  # Symbol 0xB2 (double prime), used in these texts as quotation marks
_PRIVATE_USE = re.compile("[-]")

_INVISIBLE = re.compile("[­​-‍⁠﻿\u0080-\u009f]")  # soft hyphen, zero-width, C1 controls
_NO_BREAK_SPACE = re.compile("[   ]")

# A spacing accent (΄ ´ ῾) that starts a word and sits before an unaccented vowel: "΄Αρθρ.2.-" -> "Άρθρ.2.-".
# Not touched: the numeral/ordinal sign after a letter ("ΦΕΚ Α΄ 57", "Γ΄ Διεθνούς"), the apostrophe inside
# "κατ΄Αύγουστον", and single-letter words, where we can't tell what was meant.
_SPACING_TONOS = re.compile(r"(?<![^\W\d_]|[΄´])[΄´´]\s?([ΑΕΗΙΟΥΩαεηιουω])(?=[^\W\d_])")
_ADD_TONOS = str.maketrans("ΑΕΗΙΟΥΩαεηιουω", "ΆΈΉΊΌΎΏάέήίόύώ")

# Look-alike letters. A word mixing scripts is converted to Greek when every Latin letter in it has a Greek
# twin ("τoυ" -> "του", "AΠΟΦΑΣΗ"); otherwise to Latin when every Greek letter has a Latin twin
# ("ΚG" -> "KG", "ΙV" -> "IV"); otherwise left alone ("μg" stays, it is a real unit).
_LATIN_TO_GREEK = str.maketrans("ABEHIKMNOPTXYZoviukxap", "ΑΒΕΗΙΚΜΝΟΡΤΧΥΖονιυκχαρ")
_GREEK_TO_LATIN = str.maketrans("ΑΒΕΖΗΙΚΜΝΟΡΤΥΧο", "ABEZHIKMNOPTYXo")
_LATIN_TWINS = set("ABEHIKMNOPTXYZoviukxap")
_GREEK_TWINS = set("ΑΒΕΖΗΙΚΜΝΟΡΤΥΧο")
_LETTERS = re.compile(r"[^\W\d_]+")
_GREEK = re.compile("[Ͱ-Ͽἀ-῿]")
_LATIN = re.compile("[A-Za-z]")

# Capital words split by a stray space after Γ or after consonant+Ρ (a kerning artefact before Α):
# "ΕΡΓ ΑΣΙΑΣ" -> "ΕΡΓΑΣΙΑΣ", "ΠΡ ΑΞΙΣ" -> "ΠΡΑΞΙΣ". Greek words don't end in Γ or ΠΡ/ΓΡ, so this is safe;
# "ΥΠΕΡ ΑΥΤΩΝ" (vowel before Ρ) and a lone list letter "Γ ΑΡΜΟΔΙΟΤΗΤΕΣ" are left alone.
_SPLIT_CAPS = re.compile(r"(?<![^\W\d_])([Α-ΩΆ-Ώ]*(?:[Α-ΩΆ-Ώ]Γ|[ΓΠΤΚΒΦΧΘΔ]Ρ)) (?=Α[Α-ΩΆ-Ώ])")

# A number glued to a capitalised Greek word: "1991/508Ποσό" -> "1991/508 Ποσό", "-339Διεθνής" -> "-339 Διεθνής".
_GLUED_NUMBER = re.compile(r"(?<=\d)(?=[Α-ΩΆ-Ώ][α-ωά-ώ])")

_SPACES = re.compile(r"[ \t\r\n\f\v]+")


def _symbol_font(text, counts):
    def quote(m):
        before = text[m.start() - 1] if m.start() else " "
        after = text[m.end()] if m.end() < len(text) else " "
        return "«" if (before.isspace() or before in "([«") and not after.isspace() else "»"

    text, n = re.subn(SYMBOL_QUOTE, quote, text)
    counts["symbol_font_quotes"] += n

    def char(m):
        code = ord(m.group())
        if 0xF020 <= code <= 0xF0FF:
            mapped = _SYMBOL_FONT[code - 0xF020]
            counts["symbol_font_chars"] += 1
            return "" if mapped == "\0" else mapped
        counts["private_use_dropped"] += 1
        return ""

    return _PRIVATE_USE.sub(char, text)


def _lookalike(m, counts):
    word = m.group()
    if not (_GREEK.search(word) and _LATIN.search(word)):
        return word
    latin = {c for c in word if c.isascii()}
    greek = {c for c in word if _GREEK.match(c)}
    if latin <= _LATIN_TWINS:
        counts["lookalike_words_to_greek"] += 1
        return word.translate(_LATIN_TO_GREEK)
    if greek <= _GREEK_TWINS:
        counts["lookalike_words_to_latin"] += 1
        return word.translate(_GREEK_TO_LATIN)
    counts["mixed_words_left"] += 1
    return word


def normalize_with_counts(text):
    counts = collections.Counter()

    nfc = unicodedata.normalize("NFC", text)
    counts["nfc_changed"] += nfc != text
    text = nfc

    counts["micro_sign"] += text.count("µ")
    text = text.replace("µ", "μ")

    text = _symbol_font(text, counts)

    text, n = _INVISIBLE.subn("", text)
    counts["invisible_chars"] += n
    text, n = _NO_BREAK_SPACE.subn(" ", text)
    counts["no_break_spaces"] += n

    text, n = _SPACING_TONOS.subn(lambda m: m.group(1).translate(_ADD_TONOS), text)
    counts["spacing_tonos"] += n

    text = _LETTERS.sub(lambda m: _lookalike(m, counts), text)

    text, n = _SPLIT_CAPS.subn(r"\1", text)
    counts["split_caps_joined"] += n
    text, n = _GLUED_NUMBER.subn(" ", text)
    counts["glued_numbers_split"] += n

    text = _SPACES.sub(" ", text).strip()
    return text, counts


def normalize(text):
    return normalize_with_counts(text)[0]


def fold(text):
    """Lowercase without accents, single spaces: a comparison key ("Εργατικά  Ατυχήματα" == "εργατικα ατυχηματα")."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return _SPACES.sub(" ", text).strip()

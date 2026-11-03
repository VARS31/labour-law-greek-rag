"""Find article markers ("Άρθρ.1.-", "Άρθρο 5", "Άρθρον μόνον", ...) in normalised text.

Derived from the Phase 0 regex in scripts/explore_data.py. Changes: a letter suffix ("Άρθρο 7α") must be a
whole token, so "Άρθρο 3 της οδηγίας" is no longer read as a marker, and each match gets a clean label.
Damaged variants (spacing tonos, Latin "o") are kept in the pattern for unnormalised input.
"""

import re

_ORDINALS = {
    "μόνο": None, "πρώτο": 1, "δεύτερο": 2, "τρίτο": 3, "τέταρτο": 4, "πέμπτο": 5,
    "έκτο": 6, "έβδομο": 7, "όγδοο": 8, "ένατο": 9, "δέκατο": 10,
}
_ORDINAL_WORD = r"(?:μόνον?|πρώτον?|δεύτερον?|τρίτον?|τέταρτον?|πέμπτον?|έκτον?|έβδομον?|όγδοον?|ένατον?|δέκατον?)"
_ROMAN = r"[IVXΙΧ]{1,6}(?![^\W\d_])"
# Words after the number that make it a reference to another text, not a marker: "Άρθρ. 5 παρ. 2",
# "Άρθρο 3 της οδηγίας", "Άρθρ. 2 και 6 του Νόμ.", "Άρθρ.9 του".
_REFERENCE = (r"(?:παρ|της|του|των|τον|την|εδ|περ|και|έως|ως|μέχρι|ν\.|Ν\.|π\.δ|Π\.Δ|Ν\.Δ|Α\.Ν|Β\.Δ"
              r"|Κανονισμού|Οδηγίας|Συμβάσεως|Σύμβασης|ΚΠολΔ|ΑΚ|ΠΚ)")

ARTICLE = re.compile(
    r"(?<![\wά-ώ\(])(?<!\(\s)(?<!\b[Ττ]ο\s)(?<!\b[Ττ]ου\s)(?<!\b[Σσ]το\s)"  # not "(Άρθρ.", not "το/του/στο άρθρο"
    r"(?:΄\s?)?(?:Ά|Α|A)(?:ρθρ|ΡΘΡ)(?:ον|ο|o|ΟΝ|Ο)?\.?\s*"                   # Άρθρ. / Άρθρο / Άρθρον / ΑΡΘΡΟ / ΄Αρθρ / Άρθρo
    r"(?:(?P<num>\d+)(?!\d)(?P<letter>\s?[α-ω](?![^\W\d_]))?(?P<bis>\s?(?:δις|τρις)(?![^\W\d_]))?"
    r"(?:\s?[-–]\s?(?P<to>\d+))?"                                             # 12 / 7α / 5 δις / 13-19
    r"|(?P<word>" + _ORDINAL_WORD + r"(?![^\W\d_]))|(?P<roman>" + _ROMAN + r"))"
    r"(?:\s?\.?\s?[-–])?"                                                     # the ".-" after "Άρθρ.1"
    r"(?!\s?" + _REFERENCE + r"[\s\.])")
SINGLE_ARTICLE = re.compile(r"(?:Μόνον?|ΜΟΝΟΝ?)\s+(?:άρθρον?|ΑΡΘΡΟΝ?)")

_ROMAN_VALUES = {"I": 1, "Ι": 1, "V": 5, "X": 10, "Χ": 10}


def _roman_to_int(s):
    values = [_ROMAN_VALUES[c] for c in s]
    return sum(-v if i + 1 < len(values) and v < values[i + 1] else v for i, v in enumerate(values))


def find_markers(text):
    """All article markers in reading order, as regex matches."""
    found = list(ARTICLE.finditer(text)) + list(SINGLE_ARTICLE.finditer(text))
    return sorted(found, key=lambda m: m.start())


def describe(m):
    """(label, numbers) for a marker: ("Άρθρο 5", [5]), ("Άρθρα 13-19", [13..19]), ("Άρθρο μόνο", [])."""
    if m.re is SINGLE_ARTICLE:
        return "Άρθρο μόνο", []
    g = m.groupdict()
    if g["word"]:
        word = g["word"].lower().removesuffix("ν")
        number = _ORDINALS.get(word)
        return f"Άρθρο {word}", [number] if number else []
    if g["roman"]:
        return f"Άρθρο {g['roman']}", [_roman_to_int(g["roman"])]
    first = int(g["num"])
    suffix = (g["letter"] or "").strip() + (" " + g["bis"].strip() if g["bis"] else "")
    if g["to"] and int(g["to"]) > first:
        last = int(g["to"])
        return f"Άρθρα {first}-{last}", list(range(first, last + 1))[:100]
    return f"Άρθρο {first}{suffix}", [first]

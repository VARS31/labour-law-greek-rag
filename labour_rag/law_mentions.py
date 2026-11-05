"""Find mentions of laws and decrees in chunk text: Ν., Ν.Δ., Α.Ν., Π.Δ. and Β.Δ. with a number.

Handles the forms the texts use: "Νόμ. 435/1976", "Ν.Δ. 4020/59", "Νόμ. 2556/23-24 Δεκ. 1997",
"Ν. 1387 της 18/19 Αυγ. 1983", "νόμου 2943 του 1922", "υπ’ αριθ. 748/66 Β.Δ/τος" and "ν. 2112" (no year).

Old decrees often have only a date ("Β.Δ. 16/18 Ιουλ. 1920", "Π.Δ. της 27/6-4/7/32"). Those aren't counted: the
first number is a day, not a law number.
"""

import re
from collections import namedtuple

from .normalize import fold

Mention = namedtuple("Mention", "abbr number year start end")

_DIAT = r"(?:/τος|/τα|/τι|/γμα|\.)?"
_TYPES = {
    "ND": r"ν\.\s?δ" + _DIAT + r"|νομοθετ(?:ικον|ικου|ικο|\.)\s*διαταγμα(?:τος)?|νομ\.\s?διαταγμα(?:τος)?",
    "AN": r"α\.\s?ν\.?|α\.\s?νομ(?:ου|ος)|αναγκ(?:αστικου|αστικος|\.)\s*νομ(?:ου|ος|\.)",
    "PD": r"π\.\s?δ" + _DIAT + r"|προεδρικ(?:ον|ου|ο)\s*διαταγμα(?:τος)?",
    "BD": r"β\.\s?δ" + _DIAT + r"|βασιλικ(?:ον|ου|ο)\s*διαταγμα(?:τος)?",
    "N": r"νομ(?:ος|ου|ων|ο)?\.?|ν\.",
}
_ABBR = {"ND": "Ν.Δ.", "AN": "Α.Ν.", "PD": "Π.Δ.", "BD": "Β.Δ.", "N": "Ν."}
_ANY_TYPE = "|".join(f"(?P<{name}>{pattern})" for name, pattern in _TYPES.items())
_ARITH = r"(?:υπ.?\s*αρ(?:ιθ)?\.?.?\s*)?"
_MONTH = r"(?:ιαν|φεβ|μαρ|απρ|μαι|μαϊ|ιουν|ιουλ|αυγ|σεπ|οκτ|νοε|δεκ)[α-ωϊ]*\.?"
# 23-24 δεκ. 1997 | 28 απρ.-10 μαιου 1993 | 18/19 αυγ. 1983 | 26 ιαν./3 φεβρ. 1937
_DATE = (rf"(?P<day>\d{{1,2}})(?:\s*{_MONTH})?(?P<range>\s*[-–/]\s*\d{{1,2}})?\s*{_MONTH}"
         rf"(?:\s*[-–/]\s*\d{{1,2}}\s*{_MONTH})?\s*(?P<date_year>\d{{4}})")

_FORWARD = re.compile(
    rf"(?<![\w./])(?:{_ANY_TYPE})\s*{_ARITH}(?P<number>\d{{1,4}})(?![\d.,]\d)"
    rf"(?:\s*/\s*(?P<year>\d{{4}}|\d{{2}})(?![\d/]|\.\d|\s*[-–]\s*\d|\s*{_MONTH})"
    rf"|\s*/\s*{_DATE}"
    rf"|\s*/\s*\d{{1,2}}[-.]\d{{1,2}}[-.](?P<digits_year>\d{{4}}|\d{{2}})(?!\d)"
    rf"|\s+της\s+{_DATE.replace('day', 'day2').replace('range', 'range2').replace('date_year', 'date_year2')}"
    rf"|\s+του\s+(?P<of_year>\d{{4}})(?!\d))?")
_REVERSED = re.compile(
    rf"υπ.?\s*αρ(?:ιθ)?\.?.?\s*(?P<number>\d{{1,4}})\s*/\s*(?P<year>\d{{4}}|\d{{2}})(?!\d)\s+"
    rf"(?:του\s+)?(?:{_ANY_TYPE})(?![\w])")


_YEAR_FIRST = re.compile(r"\s*/\s*(\d{1,3})(?!\d)")


def full_year(text):
    """'76' -> 1976, '1976' -> 1976. Every law the chunks cite is from before 2000."""
    return int(text) + 1900 if len(text) == 2 else int(text)


def _kind(match):
    return next(name for name in _TYPES if match.group(name))


def find_mentions(text, any_year=False):
    """The numbered laws mentioned in a text, as Mention(abbr, number, year or None, start, end). The positions
    refer to fold(text). Years outside 1830-2005 are dropped as misreadings, unless any_year is set: chunks stop in
    1999, but a question may name a newer law."""
    folded = fold(text)
    found = []
    for m in _FORWARD.finditer(folded):
        number, year = str(int(m.group("number"))), None
        if number.startswith("19") and len(number) == 4 and not m.group("year"):
            swapped = _YEAR_FIRST.match(folded, m.end())       # "Προεδρικό Διάταγμα 1990/198"
            if swapped:
                number, year = swapped.group(1), int(number)
        if year:
            pass
        elif m.group("year"):
            year = full_year(m.group("year"))
        elif m.group("date_year"):
            # "16/18 ιουλ. 1920": a decree with a date and no number. "94/10-22 απρ. 1987": number 94.
            if int(number) <= 31 and not m.group("range"):
                continue
            year = int(m.group("date_year"))
        elif m.group("digits_year"):                 # "1073/16-9-81"; but "8/13.4.32" is only a date
            if int(number) <= 31:
                continue
            year = full_year(m.group("digits_year"))
        elif m.group("date_year2"):
            year = int(m.group("date_year2"))
        elif m.group("of_year"):
            year = int(m.group("of_year"))
        found.append(Mention(_ABBR[_kind(m)], number, year, m.start(), m.end()))
    for m in _REVERSED.finditer(folded):
        found.append(Mention(_ABBR[_kind(m)], m.group("number"), full_year(m.group("year")), m.start(), m.end()))
    return [f for f in found if any_year or f.year is None or 1830 <= f.year <= 2005]


_ARTICLE_NUMBER = re.compile(r"(?<!\w)αρθρ\w*\.?\s*\d+")


def names_a_law(question):
    """True if a question names a law or an article: "Ν. 1837/1989", "άρθρο 2"."""
    return bool(find_mentions(question, any_year=True) or _ARTICLE_NUMBER.search(fold(question)))


def resolve(mentions, documents, min_number_without_year=100):
    """Group mentions into laws. `mentions` is a list of (Mention, payload); `documents` a set of (abbr, number, year).

    Returns (found, missing), two dicts {(abbr, number, year): [payload, ...]}. A law counts as found if a document
    has its type and number and a year at most 1 away, because a law may be voted one year and published the next.
    A mention without a year takes the year of the document with that number, or else the only year other mentions
    give it. If none is known it stays with year None, unless its number is small, which is too often not a law."""
    by_number = {}
    for abbr, number, year in documents:
        by_number.setdefault((abbr, number), set()).add(year)
    dated = {}
    for mention, _ in mentions:
        if mention.year:
            dated.setdefault((mention.abbr, mention.number), set()).add(mention.year)

    found, missing = {}, {}
    for mention, payload in mentions:
        key = (mention.abbr, mention.number)
        if mention.abbr == "Ν.":                       # texts often write "Ν. 3789/57" for Ν.Δ. 3789/1957
            for other in ("Ν.Δ.", "Α.Ν."):
                years = by_number.get((other, mention.number), set())
                if key not in by_number and mention.year and any(y and abs(y - mention.year) <= 1 for y in years):
                    key = (other, mention.number)
                    break
        known = by_number.get(key, set())
        if mention.year:
            near = [y for y in known if y and abs(y - mention.year) <= 1]
            target = found if near else missing
            target.setdefault((*key, near[0] if near else mention.year), []).append(payload)
        elif known:
            found.setdefault((*key, min(known, key=lambda y: y or 0)), []).append(payload)
        elif len(dated.get(key, ())) == 1:
            missing.setdefault((*key, next(iter(dated[key]))), []).append(payload)
        elif int(mention.number) >= min_number_without_year:
            missing.setdefault((*key, None), []).append(payload)
    return found, _merge_near_years(missing)


def _merge_near_years(missing):
    """Join rows of one law whose years differ by 1 ("Ν. 2224/1993" is a misprint of Ν. 2224/1994), or whose type
    differs among Ν., Ν.Δ. and Α.Ν. ("Ν.Δ. 3239/55" for Ν. 3239/1955). The row with the most mentions gives the name."""
    family = lambda abbr: "law" if abbr in ("Ν.", "Ν.Δ.", "Α.Ν.") else abbr     # noqa: E731
    merged = {}
    for (abbr, number, year), payloads in sorted(missing.items(), key=lambda kv: -len(kv[1])):
        target = next((k for k in merged if family(k[0]) == family(abbr) and k[1] == number and year and k[2]
                       and abs(k[2] - year) <= 1), None)
        merged.setdefault(target or (abbr, number, year), []).extend(payloads)
    return merged


def label(abbr, number, year):
    return f"{abbr} {number}/{year}" if year else f"{abbr} {number} (year not given)"

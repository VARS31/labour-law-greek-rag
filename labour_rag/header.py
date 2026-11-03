"""Read act type, number, year, ΦΕΚ and title from a document header (normalised text).

Typical header: "14. ΝΟΜΟΣ υπ’ αριθ. 751 της 4/10 Αυγ. 1948 (ΦΕΚ Α΄ 57) Περί προστασίας … ."
Headerless variants: "Προεδρικό Διάταγμα 1991/508 Ποσό σύνταξης …", or just a title.
"""

import re

# (pattern on the act-type words, full name, abbreviation used in citations)
_ACT_TYPES = [
    (r"ΑΝΑΓΚ", "Αναγκαστικός νόμος", "Α.Ν."),
    (r"ΝΟΜΟΘ|ΝΟΜ\.\s?ΔΙΑΤ", "Νομοθετικό διάταγμα", "Ν.Δ."),
    (r"ΝΟΜΟΣ|ΝΟΜΟΙ", "Νόμος", "Ν."),
    (r"ΒΑΣΙΛ", "Βασιλικό διάταγμα", "Β.Δ."),
    (r"ΠΡΟΕΔΡ", "Προεδρικό διάταγμα", "Π.Δ."),
    (r"ΚΑΝΟΝΙΣΤ", "Κανονιστικό διάταγμα", "Κ.Δ."),
    (r"ΔΙΑΤΑΓΜΑ", "Διάταγμα", "Δ."),
    (r"(?:ΚΟΙΝΗ\s)?ΑΠΟΦ.*ΥΠΟΥΡΓΩΝ", "Κοινή υπουργική απόφαση", "Κ.Υ.Α."),
    (r"ΑΠΟΦ.*ΥΠΟΥΡΓΟΥ", "Υπουργική απόφαση", "Υ.Α."),
    (r"ΑΠΟΦ", "Απόφαση", "Απόφ."),
    (r"ΑΓΟΡΑΝ", "Αγορανομική διάταξη", "Αγορ.Δ."),
    (r"ΠΡΑΞ.*ΝΟΜΟΘ", "Πράξη νομοθετικού περιεχομένου", "Π.Ν.Π."),
    (r"ΠΡΑΞ.*ΥΠΟΥΡ", "Πράξη Υπουργικού Συμβουλίου", "Π.Υ.Σ."),
    (r"ΠΡΑΞ", "Πράξη", "Πράξη"),
    (r"ΕΓΚΥΚΛ", "Εγκύκλιος", "Εγκ."),
    (r"ΚΑΝΟΝΙΣΜ", "Κανονισμός", "Καν."),
    (r"ΣΥΜΒΑΣ", "Σύμβαση", "Σύμβ."),
    (r"ΕΓΓΡΑΦ", "Έγγραφο", "Έγγρ."),
]
_LEADING_NUMBER = re.compile(r"^\s*\(?\d+\s?[α-ω]?\s?[.)]\s*")       # "14. ", "23α. ", "(1) "
_TYPE_WORDS = re.compile(r"(?:[Α-ΩΆ-Ώ][Α-ΩΆ-Ώ.,]*(?=\s|$)\s*)+")     # "ΑΠΟΦΑΣΙΣ ΥΠΟΥΡΓΟΥ ΕΡΓΑΣΙΑΣ " (whole caps words)
_NUMBER = re.compile(r"^(?:υπ[’'΄]?\s*)?(?:αρ[ιί]θ|Αρ[ιί]θ|ΑΡ)\.?[’'΄]?\s*(?P<num>.{1,40}?)\s+(?=της\b|την\b|\()"
                     r"|^(?P<bare>\d+[α-ω]?(?:/\d+)?)\s+(?=της\b)")
_PD_SHORT = re.compile(r"^\s*(Προεδρικό Διάταγμα|Νόμος)\s+(\d{4})/(\d+[α-ω]?)\s*")
_MONTH = r"(?:Ιαν|Φεβ|Μαρ|Απρ|Μα[ΐϊιί]|Ιουν|Ιουλ|Αυγ|Σεπ|Οκτ|Νοε|Δεκ)[α-ωάέήίόύώϊΐ]*\.?"
_YEAR = r"(18[2-9]\d|19\d\d|20[0-2]\d)"
_DATE = re.compile(
    rf"(?:της|την)\s+\d{{1,2}}(?:\s*{_MONTH})?(?:\s*[/\-–]\s*\d{{1,2}})?\s*{_MONTH}\s*(?:{_YEAR}\s*)?"
    rf"(?:[/\-–]\s*\d{{1,2}}\s*{_MONTH}\s*)?\.?\s*{_YEAR}")
# "(ΦΕΚ Β΄ 16)", "(ΦΕΚ 101/Α/12.6.1990)", and unclosed "(ΦΕΚ Α΄ 110 Μέτρα για …"
_FEK = re.compile(r"\(\s*ΦΕΚ\s*(?P<body>[^)]{1,40}?)(?:\)|(?=\s[Α-ΩΆ-Ώ][α-ωά-ώ]))")
_NEAR = 80  # the date must start within this many characters after the act number
# End of the title: a full stop after a real word (5+ letters), a number or a closing bracket/quote, followed
# by a capital, the end, or a glued ".Ίδρυση"; or the start of the body ("Έχοντας υπόψη", "Εν όψει", …).
# A stop after a short word is an abbreviation ("των Υπουργών Εθν. Οικονομίας", "Υπ. Γεωργίας").
_TITLE_END = re.compile(
    r"(?:(?<=[^\W\d_]{5})|(?<=[\d)»\"]))\.(?=\s+(?:[-–]\s*)?[Α-ΩΆ-Ώ«(]|$|[Α-ΩΆ-Ώ][α-ωά-ώ])"
    r"|(?=\s(?:Άρθρ|Έχον|Εν όψει|Ψηφισάσης|Επί τη προτάσει|Προτάσει|Ακούσαντες|Λαβόντες|Αποφασίζ"
    r"|Ο ΠΡΟΕΔΡΟΣ|Ο ΒΑΣΙΛΕΥΣ)\b)")
_FEK_SERIES = re.compile(r"(?<![^\W\d_])([ΑΒΓΔαβγδ])(?![^\W\d_])")   # the series letter as its own token


def _act_type(words):
    words = words.replace("ΙΙ", "Π")                   # OCR: "ΙΙΡΟΕΔΡΙΚΟ", "ΑΙΙΟΦΑΣΗ"
    for pattern, name, abbr in _ACT_TYPES:
        if re.match(pattern, words):
            return name, abbr
    return None, None


def _fek(body):
    """"Β΄ 16", "Β' 562", "Α΄57", "101/Α/12.6.1990", "9 τ.Α΄" -> "Α΄ 57" style; None if unreadable."""
    series = _FEK_SERIES.search(body)
    number = re.search(r"\d+", body)
    if not (series and number):
        return None
    return f"{series.group(1).upper()}΄ {number.group()}"


def _title(text, start, max_words=60):
    """From `start` to the end of the first sentence (abbreviations like "Ν.Δ. 2500/1953" don't end it)."""
    rest = text[start:].lstrip(" .,")
    rest = re.sub(r"^\((?:Διόρθ|Διορθ)[^)]*\)\s*", "", rest)        # "(Διόρθ. Σφαλμ. στο ΦΕΚ …)"
    m = _TITLE_END.search(rest)
    title = rest[:m.start()] if m else rest
    words = title.split()
    return " ".join(words[:max_words]).strip(" ,;:-–") or None


def parse_header(text):
    """Metadata from the start of a document. Missing fields are None."""
    out = {"act_type": None, "act_abbr": None, "act_number": None, "year": None, "fek": None, "title": None}
    head = text[:600]

    short = _PD_SHORT.match(head)                      # "Προεδρικό Διάταγμα 1991/508 Ποσό σύνταξης …"
    if short:
        out["act_type"], out["act_abbr"] = ("Προεδρικό διάταγμα", "Π.Δ.") if short.group(1).startswith("Π") \
            else ("Νόμος", "Ν.")
        out["year"], out["act_number"] = int(short.group(2)), short.group(3)
        out["title"] = _title(text, short.end())
        return out

    lead = _LEADING_NUMBER.match(head)
    pos = lead.end() if lead else 0
    words = _TYPE_WORDS.match(head, pos)
    if lead and words:
        out["act_type"], out["act_abbr"] = _act_type(words.group())
    if not out["act_type"]:
        out["title"] = _title(text, pos)                # headerless: the first sentence is the title
        date = _DATE.search(head)
        out["year"] = int(date.group(2)) if date and date.start() < 200 else None
        return out

    pos = words.end()
    number = _NUMBER.match(head[pos:])
    if number:
        out["act_number"] = (number.group("num") or number.group("bare")).strip(" .,")
        pos += number.end()
    date = _DATE.search(head, pos)
    if date and date.start() - pos <= _NEAR:
        out["year"] = int(date.group(2))
        pos = date.end()
    else:                                              # damaged date: take a bare year close by, if any
        year = re.compile(rf"\b{_YEAR}\b").search(head, pos, pos + _NEAR)
        if year:
            out["year"] = int(year.group(1))
            pos = year.end()
    fek = _FEK.match(head, re.compile(r"\s*").match(head, pos).end())
    if fek:
        out["fek"] = _fek(fek.group("body"))
        pos = fek.end()
    out["title"] = _title(text, pos)
    return out


def citation(meta):
    """Short citation for the embed header: "Ν. 1264/1982", "Υ.Α. 98168/7185/1963", "Β.Δ. (1953)"."""
    abbr, number, year = meta.get("act_abbr"), meta.get("act_number"), meta.get("year")
    if abbr and number:
        return f"{abbr} {number}/{year}" if year and not str(number).endswith(str(year)) else f"{abbr} {number}"
    if abbr:
        return f"{abbr} ({year})" if year else abbr
    return None

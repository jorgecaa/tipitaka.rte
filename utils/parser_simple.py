#!/usr/bin/env python3
"""parser_simple.py — Strict homogeneity parser for the corrected corpus.

A deliberately simple, zero-tolerance parser: every line of every file
must fit one of five line types, every character must belong to the
expected inventory, and the structural markers must follow their
documented grammar (docs/DOC.md).  It never stops at the first error —
it censuses every violation, so the output answers one question:
where exactly is the corpus still not homogeneous?

Line grammar (strict):
  BLANK      empty (or whitespace-only) line
  PAGE       "page number: NNN"  (exactly 3 digits, preceded by a blank)
  SEPARATOR  a run of 3+ hyphens, nothing else
  FOOTNOTE   "footnote:" + apparatus content
  BODY       anything else — subject to character/marker checks

Checks per line type:
  * character whitelist (Pali romanization + structural ASCII + digits
    + documented punctuation); anything else is a violation
  * PAGE: 3-digit padding, blank line before, sequence +1 within file
  * BODY/FOOTNOTE: bracket forms ([N], [..], [?], [cha.], editorial
    Pali content), (pts. ...) shapes incl. the nested Patthana form,
    "#[N]" section anchors, paren/bracket balance per file (editorial
    parentheticals legitimately span page boundaries)
  * FOOTNOTE: empty apparatus

The expected residue on the current corpus is the irreducible set
cataloged in METHODOLOGY.md §8 (65 flags: damage lines, intentional
empty apparatus, lost-content markers).  Any flag OUTSIDE that catalog
means a regression was introduced.

Usage:  python3 utils/parser_simple.py [dir ...]   (default: Canonical
        and Non-Canonical at the repo root)

Exit status: 0 = fully homogeneous, 1 = violations found (censused).
"""

import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# ── character inventory ──────────────────────────────────────────────────────
PALI = "aāiīuūeo kgcjtdnpbmyrlvsh ṁṅñṭḍṇḷ"
ASCII_LETTERS = "abcdefghijklmnopqrstuvwxyz"     # structural words, pts refs
PUNCT = " .,;:()[]-*/\"'?!`"                     # documented punctuation
ALLOWED = set(PALI.replace(" ", "")) | set(ASCII_LETTERS) | set("0123456789") \
        | set(PUNCT) | {"–", "—", "M", "Ñ"}      # M from .M sigla; Ñ = uc ñ

PAGE_RE = re.compile(r'^page number: (\d+)$')
SEP_RE = re.compile(r'^-{3,}$')          # lengths vary freely (print artifact)
# bracket forms: [N], [N-M], [N-M-P], [..], [?], [cha.] (documented) plus
# editorial Pali content — verse speaker tags "[selāti bhagavā]" and
# expansion instructions "[evaṁ peyyālo]" (found by census 2026-07-16)
BRACKET_RE = re.compile(r'\[([^\]]*)\]')
# editorial content may embed calls "1-", pts refs and colons, but must
# contain at least one Pali letter — "[]" (lost content) keeps failing
BRACKET_OK = re.compile(
    r'^(\d+(-\d+){0,2}|\.\.|\?|cha\.'
    r"|(?=.*[a-zāīūṁṅñṭḍṇḷ])[a-zāīūṁṅñṭḍṇḷ0-9 .,:\-()']+)$")
# "(pts. work vol, page)" plus the nested Paṭṭhāna form
# "(pts. pat (dkp|tkp), page)" (417 occ, undocumented in DOC.md)
PTS_RE = re.compile(r'\(pts\. pat \((?:dkp|tkp)\), \d+\)|\(pts[^)]*\)?')
PTS_OK = re.compile(
    r'^(\(pts\. [a-z]+( [ivxl]+)?, \d+\)'
    r'|\(pts\. pat \((?:dkp|tkp)\), \d+\))$')
# "#" is a section anchor glued to "[N]" in six commentary files
ANCHOR_RE = re.compile(r'#(?=\[)')


def main() -> int:
    dirs = [Path(a) for a in sys.argv[1:]] or [REPO / "Canonical", REPO / "Non-Canonical"]
    viol = Counter()
    examples = defaultdict(list)

    def flag(kind, fp, lineno, detail):
        viol[kind] += 1
        if len(examples[kind]) < 5:
            examples[kind].append(f"{fp.name}:{lineno}: {detail[:70]}")

    files = pages = 0
    for d in dirs:
        for fp in sorted(d.glob("*.txt")):
            files += 1
            lines = fp.read_text(encoding="utf-8").split("\n")
            prev_blank = True
            last_page = None
            paren = 0                       # file-level balance: editorial
            bracket = 0                     # parens can span page boundaries
            for i, raw in enumerate(lines, 1):
                line = raw[1:] if i == 1 and raw.startswith("﻿") else raw
                s = line.strip()

                if not s:
                    prev_blank = True
                    continue

                pm = PAGE_RE.match(s)
                if pm:
                    pages += 1
                    if len(pm.group(1)) != 3:
                        flag("PAGE: padding != 3 dígitos", fp, i, s)
                    if not prev_blank:
                        flag("PAGE: sin línea en blanco antes", fp, i, s)
                    n = int(pm.group(1))
                    if last_page is not None and n != last_page + 1:
                        flag("PAGE: salto de secuencia", fp, i,
                             f"{last_page} -> {n}")
                    last_page = n
                    prev_blank = False
                    continue
                if s.lower().startswith("page number"):
                    flag("PAGE: forma no canónica", fp, i, s)
                    prev_blank = False
                    continue

                if SEP_RE.match(s):
                    prev_blank = False
                    continue
                if set(s) <= set("-–—") and len(s) >= 2:
                    flag("SEPARADOR: forma no canónica", fp, i, s)
                    prev_blank = False
                    continue

                is_fn = s.startswith("footnote:")
                if is_fn and not s[9:].strip():
                    flag("FOOTNOTE: aparato vacío", fp, i, s)

                # character whitelist (section anchors "#[" are legit)
                s_chk = ANCHOR_RE.sub("", s)
                for ch in set(s_chk):
                    if ch not in ALLOWED:
                        flag(f"CHAR fuera de inventario: U+{ord(ch):04X} {ch!r}",
                             fp, i, s_chk)

                # bracket forms
                for m in BRACKET_RE.finditer(s):
                    if not BRACKET_OK.match(m.group(1)):
                        flag("CORCHETE: forma no documentada", fp, i,
                             f"[{m.group(1)}]")

                # pts reference shape
                for m in PTS_RE.finditer(s):
                    if not PTS_OK.match(m.group(0)):
                        flag("PTS: forma no canónica", fp, i, m.group(0))

                paren += s.count("(") - s.count(")")
                bracket += s.count("[") - s.count("]")
                prev_blank = False
            if paren:
                flag("ARCHIVO: paréntesis desbalanceados", fp, len(lines),
                     f"saldo final {paren:+d}")
            if bracket:
                flag("ARCHIVO: corchetes desbalanceados", fp, len(lines),
                     f"saldo final {bracket:+d}")

    print(f"{files} archivos, {pages} páginas analizadas.")
    if not viol:
        print("PARSER OK — contenido homogéneo, ninguna violación.")
        return 0
    total = sum(viol.values())
    print(f"EL PARSER CAE: {total} violaciones en {len(viol)} categorías.\n")
    for kind, n in viol.most_common():
        print(f"  {n:6} × {kind}")
        for ex in examples[kind]:
            print(f"           {ex}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

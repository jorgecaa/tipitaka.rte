#!/usr/bin/env python3
"""verify_pali.py — Pali-integrity gate against the hand-corrected reference.

Cardinal rule of this repo: the Pali letter stream is inviolable.  This
script proves it after every pipeline change: the letters-only projection
of every output file must be byte-identical to that of the reference
corpus (the predecessor project's hand-corrected corpus).

Two documented, letter-bearing transformations are factored out before
projecting:
  * our side gains "footnote:" labels on rescued spilled lines (3c) —
    stripped from BOTH sides;
  * the reference still carries the transliterated HTML husk that stage
    2h removes — stripped from the reference side.

Rationale and the full transformation catalog: METHODOLOGY.md (§6–7).

Usage:  python3 utils/verify_pali.py [reference_dir]
Exit status: 0 = 115/115 identical, 1 = any file's Pali words differ.
"""

import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# Reference resolution: CLI argument, else $TIPITAKA_REFERENCE_DIR, else
# the predecessor project checked out alongside this repository.
DEFAULT_REF = Path(
    os.environ.get("TIPITAKA_REFERENCE_DIR")
    or REPO.parent / "budsir" / "budsir_c" / "tipitaka.rte" / "txt")

FN_LABEL = re.compile(r'^(\s*)footnote:', re.M)
HTML_HUSK = re.compile(
    r'%a name="\d+"@%/a@[ \t]*'
    r'|%span style="background-color:#0403cc; color:#f0f0ff"@\$')
LETTERS = re.compile(r'[^\W\d_]+')


def project(text: str, is_reference: bool) -> list:
    """Return the word sequence (maximal letter runs), husk and labels
    factored out.  Comparing word sequences — not just the flat letter
    stream — also catches word merges and splits: an edit that deleted a
    space between two Pali words would keep the letter stream intact but
    change the token sequence, and is detected here."""
    text = FN_LABEL.sub(r'\1', text)
    if is_reference:
        text = HTML_HUSK.sub('', text)
    return LETTERS.findall(text)


def main() -> int:
    ref_root = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_REF
    if not ref_root.is_dir():
        print(f"referencia no encontrada: {ref_root}", file=sys.stderr)
        return 2
    ok = total = 0
    bad = []
    for d in ("Canonical", "Non-Canonical"):
        for fp in sorted((REPO / d).glob("*.txt")):
            total += 1
            out = project(fp.read_text(encoding="utf-8"), False)
            ref = project((ref_root / d / fp.name).read_text(encoding="utf-8"),
                          True)
            if out == ref:
                ok += 1
            else:
                # first divergence point, for diagnosis
                n = next((k for k, (a, b) in enumerate(zip(out, ref))
                          if a != b), min(len(out), len(ref)))
                bad.append(f"{d}/{fp.name}: palabra {n}: "
                           f"{out[max(0, n-3):n+2]} != "
                           f"{ref[max(0, n-3):n+2]}")
    print(f"Secuencia de palabras pali idéntica a la referencia: {ok}/{total}")
    if bad:
        print("LETRAS PALI ALTERADAS EN:")
        for b in bad:
            print("  ", b)
        return 1
    print("INTEGRIDAD PALI VERIFICADA.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""verify_pali.py — dual-hash Pali-integrity gate.

Two cryptographically independent hashes (SHA-256 + BLAKE2b) of the
Pali word sequence of every output file, compared against the reference
corpus.  Both must match — orthogonal algorithms ensure no hash collision
can mask a corruption.

Same documented transforms factored out as the original:
  * footnote: labels on rescued spilled lines
  * HTML husk residue in the reference

Usage:  python3 utils/verify_pali.py [reference_dir]
Exit:   0 = 115/115 both hashes match, 1 = mismatch.
"""

import hashlib
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_REF = Path(
    os.environ.get("TIPITAKA_REFERENCE_DIR")
    or REPO.parent / "budsir" / "budsir_c" / "tipitaka.rte" / "txt")

FN_LABEL = re.compile(r'^(\s*)footnote:', re.M)
HTML_HUSK = re.compile(
    r'%a name="\d+"@%/a@[ \t]*'
    r'|%span style="background-color:#0403cc; color:#f0f0ff"@\$')
LETTERS = re.compile(r'[^\W\d_]+')


def project(text: str, is_reference: bool) -> list:
    """Return the ordered Pali word sequence, husk and labels factored out."""
    text = FN_LABEL.sub(r'\1', text)
    if is_reference:
        text = HTML_HUSK.sub('', text)
    return LETTERS.findall(text)


def dual_hash(words: list) -> tuple:
    """Return (sha256_hex, blake2b_hex) of the joined word sequence."""
    payload = ' '.join(words).encode('utf-8')
    return (hashlib.sha256(payload).hexdigest(),
            hashlib.blake2b(payload, digest_size=32).hexdigest())


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
            out_words = project(fp.read_text(encoding="utf-8"), False)
            ref_words = project(
                (ref_root / d / fp.name).read_text(encoding="utf-8"), True)

            sha_out, blake_out = dual_hash(out_words)
            sha_ref, blake_ref = dual_hash(ref_words)

            sha_ok = sha_out == sha_ref
            blake_ok = blake_out == blake_ref

            if sha_ok and blake_ok:
                ok += 1
            else:
                rel = f"{d}/{fp.name}"
                details = []
                if not sha_ok:
                    details.append(f"SHA-256 mismatch")
                if not blake_ok:
                    details.append(f"BLAKE2b mismatch")
                # Find first divergent word position
                n = next((k for k, (a, b) in enumerate(zip(out_words, ref_words))
                          if a != b), min(len(out_words), len(ref_words)))
                context_out = out_words[max(0, n-2):n+3]
                context_ref = ref_words[max(0, n-2):n+3]
                bad.append(
                    f"{rel}: {'; '.join(details)} | "
                    f"word {n}: {context_out} != {context_ref}")

    print(f"Secuencia de palabras pali idéntica a la referencia: {ok}/{total}")
    print(f"  (verificada con SHA-256 + BLAKE2b — hashes criptográficos independientes)")
    if bad:
        print("LETRAS PALI ALTERADAS EN:")
        for b in bad:
            print("  ", b)
        return 1
    print("INTEGRIDAD PALI VERIFICADA.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

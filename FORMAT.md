# FORMAT — file format of the corrected corpus and how to consume it

This document specifies the format of the generated files in
`Canonical/` and `Non-Canonical/` and gives concrete steps for parsing
them in another project. Provenance and correction history are in
`METHODOLOGY.md`; this file is only about *reading* the result.

The corpus is dedicated to the public domain (see `UNLICENSE`).

---

## 1. Inventory and encoding

- **115 plain-text files**: `Canonical/` (45 volumes of the Syāmaraṭṭha
  Tipiṭaka) and `Non-Canonical/` (70 volumes of commentaries and
  treatises).
- **File naming**: `NN-Name[-Vol].txt`, where `NN` is the volume number
  within its directory. Canonical mapping: 01–08 Vinaya, 09–33 Sutta
  (09–11 Dīgha, 12–14 Majjhima, 15–19 Saṁyutta, 20–24 Aṅguttara, 25–33
  Khuddaka), 34–45 Abhidhamma.
- **Encoding**: UTF-8. **Every file starts with a BOM (U+FEFF)** —
  open with an encoding that strips it (Python: `encoding="utf-8-sig"`)
  or strip the first code point yourself.
- **Line endings**: LF only. No tabs. Maximum line length: 187
  characters. Some lines carry trailing spaces (a print artifact —
  preserve or strip at your discretion; they carry no meaning).
- Pāli is romanized with standard diacritics
  (`ā ī ū ṁ ṅ ñ ṭ ḍ ṇ ḷ`). The full character inventory is in §7.

## 2. Line grammar

Every line is exactly one of five types (this grammar is enforced by
`utils/parser_simple.py`; the corpus parses cleanly except for the 19
inventoried damage lines, see §8):

| Type | Pattern | Notes |
|---|---|---|
| BLANK | `^\s*$` | separates blocks |
| PAGE | `^page number: (\d{3})$` | page boundary; **always** preceded by a blank line |
| SEPARATOR | `^-{3,}$` | decorative rule under headings |
| FOOTNOTE | `^footnote:( .*)?$` | one line of critical apparatus |
| BODY | anything else | text, headings, colophons |

Guarantees you can rely on:

- Every file's first non-blank line is `page number: 001`.
- Page numbers are zero-padded to 3 digits, unique within a file, and
  **strictly sequential (+1)** — no gaps, no duplicates, in all 115
  files. `(file, page)` is therefore a stable citation key equal to
  the printed volume/page of the Syāmaraṭṭha edition.
- `footnote:` is always lowercase, always followed by a space when
  non-empty (11 intentionally empty `footnote:` lines exist, inherited
  from the printed edition).

## 3. Page template

```
page number: 012
                          ← blank line
<body lines …>
<body lines …>

footnote: 1 ma. vuddhe. 2 gatātipi pāṭho.
```

A page is everything from its PAGE line to the next PAGE line.
Apparatus (`footnote:`) lines usually close the page, but **body text
after a footnote block occurs** (416 documented cases) — do not assume
`footnote:` terminates the page.

## 4. Body markers

| Marker | Pattern | Meaning |
|---|---|---|
| `[N]` | `\[\d+\]` | passage number. **Not** a sutta ID: it has duplicates (141) and gaps (1,772); its relation to text units depends on the volume (§9). |
| `N-` | `(?<=\s)\d+-` | footnote call → note `N` on the *same page*. Ranges occur: `1-2-` calls notes 1 and 2. Calls are uniformly bare digits+dash (the raw forms `[N]-` and `[N-]` were normalized away by the pipeline). |
| `(pts. work vol, page)` | `\(pts\. [a-z]+( [ivxl]+)?, \d+\)` | Pali Text Society cross-reference, e.g. `(pts. d i, 2)`. **Sub-format**: Paṭṭhāna volumes use a nested form `(pts. pat (dkp), 100)` / `(pts. pat (tkp), 100)` — Duka-/Tikapaṭṭhāna. A naive `\(pts\.[^)]*\)` breaks on it. The roman numeral `i` inside these refs must never be confused with the witness sigla `i.` (§5). |
| `[..]` | literal | historical damage / structural gap in the source edition. Immutable — treat as verbatim token. |
| `[?]` | literal | unknown marker (14 occurrences). |
| `[pali text]` | e.g. `[selāti bhagavā]`, `[evaṁ peyyālo]` | editorial bracket: verse speaker tags and expansion instructions; may embed calls and pts refs. |
| `#[N]` | `#(?=\[)` | section anchor glued to a passage number; six commentary files only (1,053 occurrences). Strip the `#` or treat as metadata. |
| `.pe.` | literal | elision ("peyyāla") — the text repeats a formula given earlier. Uniform after normalization (no spaced variants remain). |
| `..` | two dots | apparatus lacuna mark (`ma. ..ḍassāvine` = reading with elided prefix). Distinct from `...`/`....` ellipses. |
| `` ` `` | backtick | opening quote. The closing side is usually the quotative particle `ti` fused to the last word (`` `viḍūḍabhoti``), sometimes `'ti`; do not expect a closing quote character. `"…"` pairs normally. |
| `niṭṭhitaṁ`, `vaggo` + ordinal, etc. | words | section colophons ("concluded"); the reliable end-of-unit signals. |

Parentheses may legitimately span a page boundary (editorial
parentheticals); balance them per file, not per page.

## 5. Apparatus (`footnote:`) grammar

Each page's apparatus is the concatenation of its `footnote:` lines.
**Continuation lines repeat the `footnote:` prefix without a leading
note number** (3,000+ cases) — concatenate all of a page's footnote
content before splitting into notes.

Note structure: `<num>[-<num>[-<num>]] [<sigla>.]* <reading>.`

```
footnote: 1 sī. ujuvipaccanīkavādā. 2 anubaddhātipi pāṭho.
footnote: 3-4-5 yamidha …            ← one note covering calls 3,4,5
footnote: * mīkārkkhag …             ← star note (Burmese collation)
```

- Split notes at digit boundaries; expand ranges (`1-2`, `3-4-5`).
- In the commentaries, note numbers sometimes carry a dot (`1. ma. …`,
  ~17 % there, rare in the canon). Accept `^\d+(-\d+)*\.?\s`.
- Body-call ↔ note linkage is per page. Expect imperfection inherited
  from the printed edition: 235 orphan calls are individually
  whitelisted in `utils/process_corpus.py` (`KNOWN_ERRORS`), and ghost
  notes (note without call) exist.

**Witness siglas** (abbreviations naming the source of a variant):

| Sigla | Witness |
|---|---|
| `ma.` | Maramma (Burmese MSS); also printed as `.M`/`Ma.` via the apparatus sign |
| `cha.` | Chaṭṭhasaṅgīti (Burmese Sixth Council); `[cha.]` = same witness |
| `yu.` | Yuropa — European romanized edition (PTS) |
| `i.` | **PTS English edition** — commentaries only (7,272 occ) |
| `ka.` | Kambūjā (Cambodian MSS) |
| `po.` | Porāṇa (old palm-leaf MSS) |
| `rā.` | Rāmañña (Mon MSS) |
| `sī.` | Sīhaḷa (Sinhalese MSS) |
| `syā.` | Syāmaraṭṭha — the base edition itself (rarely cited) |

Witness lists join with dots and commas: `sī.,cha.Ma.` = Sīhaḷa +
Chaṭṭha/Maramma. A sigla followed by numbers is a **cross-reference,
not a witness**: `di. mahā. 10/182` cites volume/section/page of a
*foreign* (denser, Mahāmakut) edition — coordinates run up to volume
57 and must not be resolved against this corpus's 45 volumes.

## 6. Structure above the line level

There is **no universal sutta-level parser**: the meaning of `[N]` and
the location of titles/colophons vary by volume. Summary (full routing
table in the predecessor project's DOC.md):

- Dīgha/Majjhima (09–14): sutta = heading + `niṭṭhitaṁ` colophon;
  `[N]` is an internal passage.
- Saṁyutta (15–19): heterogeneous; vols. 17 and 19 have **no body
  markers at all** (boundaries only derivable from the uddāna verse
  index per vagga — not algorithmically).
- Aṅguttara (20–24): a standalone digit after `[N]` (and after any pts
  ref) is the sutta number, resetting per nipāta; vol. 20's Ekanipāta
  is opaque (1,000 suttas, 246 `[N]`).
- Jātaka (27–28): title + number come **before** `[N]`, not after.
- Abhidhamma (34–45) and Vinaya (01–08): organized by section/rule,
  not sutta.
- Verse is **not marked up** anywhere; prose/verse boundaries need
  metrical analysis or prior knowledge.

## 7. Character inventory

Body and apparatus text use exactly:

- lowercase Pāli letters `a ā b c d ḍ e g h i ī j k l ḷ m ṁ n ñ ṅ ṇ o
  p r s t ṭ u ū v y` (+ plain ASCII letters in structural words and
  pts refs), uppercase `M` (apparatus sign) and `Ñ` (capital ñ —
  legitimate, case-fold it);
- digits; punctuation `. , ; : ( ) [ ] - * / " ' ? !` and `` ` ``,
  en/em dashes `– —`; space and LF.

Anything else (PUA code points, `ß`, `=`, `@`, a C1 control…) occurs
**only** on the 19 damage/lost-content lines inventoried in
METHODOLOGY.md §8 — skip or preserve them, never "fix" them.

## 8. Minimal parser (reference implementation)

```python
import re
from pathlib import Path

PAGE = re.compile(r'^page number: (\d{3})$')

def pages(path):
    """Yield (page_number, body_lines, footnote_texts) per page."""
    num, body, notes = None, [], []
    for raw in Path(path).read_text(encoding="utf-8-sig").split("\n"):
        s = raw.strip()
        m = PAGE.match(s)
        if m:
            if num is not None:
                yield num, body, notes
            num, body, notes = int(m.group(1)), [], []
        elif num is not None and s.startswith("footnote:"):
            notes.append(s[9:].strip())
        elif num is not None and s and not re.fullmatch(r'-{3,}', s):
            body.append(s)
    if num is not None:
        yield num, body, notes

def calls(body_lines):
    """Footnote calls in reading order, ranges expanded."""
    out = []
    for line in body_lines:
        for m in re.finditer(r'(?:^|\s)(\d+(?:-\d+)*)-(?!\d)', line):
            parts = [int(x) for x in m.group(1).split("-")]
            out.extend(range(parts[0], parts[-1] + 1))
    return out
```

Validation targets: 115 files; 49,357 pages total, 21,926 of them
canonical; page sequences strictly `001..N`. This exact implementation
extracts 27,980 distinct canonical body calls per page; the pipeline's
stage-4 validator, whose boundary rules differ slightly, counts 27,977
— adopt one rule set and apply it consistently.

## 9. Using the corpus in another project — checklist

1. **Take the generated dirs, not `txt/`** — `txt/` is the frozen raw
   rip with all its corruption; `Canonical/` and `Non-Canonical/` are
   the corrected corpus.
2. **Verify what you got** (both gates ship in `utils/`):
   `python3 utils/process_corpus.py && git diff --stat Canonical/ Non-Canonical/`
   must be empty (deterministic regeneration), and
   `python3 utils/parser_simple.py` must report exactly the
   METHODOLOGY.md §8 residue.
3. **Strip the BOM**; decide a policy for trailing spaces.
4. **Cite by `(volume file, page number)`** — it equals the printed
   Syāmaraṭṭha volume/page. Use the embedded `(pts. …)` refs to map to
   PTS editions; never resolve `N/N/N` apparatus coordinates locally.
5. **Branch your logic by volume** (§6) before extracting text units;
   treat `[N]` as a locator, never as a primary key.
6. **Never alter Pāli letters** in derived corrections; if you find a
   defect, report it against the pipeline so it lands as a cataloged,
   verifiable rule (see METHODOLOGY.md §5–7).

# METHODOLOGY — provenance, corrections, and integrity guarantees

**Audience.** Engineers and philologists who need to decide whether this
corpus can be trusted before building on it. Every claim in this document
is quantified, every transformation is cataloged with its trigger evidence,
and §10 gives the exact commands to verify or falsify each claim
independently. Nothing here asks to be taken on faith.

**The one-sentence guarantee.** Relative to the hand-corrected reference
corpus (§2), this pipeline has not added, deleted, reordered, merged,
split, or altered a single Pāli word — a property proven mechanically for
all 115 files on every run (§7), not asserted.

---

## 1. What this repository is

The Pāli Tipiṭaka in the **Syāmaraṭṭha (Royal Siamese) edition**,
1925–1928, 45 canonical volumes plus 70 volumes of commentaries
(Aṭṭhakathā/Ṭīkā), as digitized by **BUDSIR** (Buddhist Scriptures
Information Retrieval, Mahidol University) and extracted from its binary
format. 115 UTF-8 text files, 49,357 printed pages, ~63.9 million
characters.

- `txt/` — the raw extraction, **immutable**, preserved verbatim in git.
- `Canonical/`, `Non-Canonical/` — the corrected corpus, **generated**
  (never hand-edited) by the pipeline from a pinned git commit.
- `utils/` — the pipeline (two independent implementations) and two
  verification gates.

## 2. Provenance and chain of custody

1. **BUDSIR binaries** — Pāli stored in the *Fulbright Roman* encoding
   (ASCII + overstrike modifier bytes `0x8A` macron, `0x8B` tilde,
   `0x8C` upper dot, `0xE5` lower dot), a scheme confirmed independently
   from the BUDSIR executables themselves (`FB_NGN.EXE`, "FB" =
   Fulbright; encoding table derived from `Bsrbname.dat`).
2. **The rip** — an extraction tool decoded those bytes to Unicode. Its
   byte→Unicode table covered the *medial* glyph bank (99.87 % of all
   text) but missed the *word-initial precomposed forms* bank and the
   Burmese apparatus-abbreviation glyph. This — not the encoding, and
   not any editorial decision — is the sole source of corruption (§3).
3. **Commit `07c937d`** ("ripped from BUDSIR") — the raw rip enters git
   history, byte-frozen. The pipeline always regenerates output from
   this commit, never from the working tree, so the input cannot drift.
4. **The predecessor project** (`budsir_c`) diagnosed the corruption,
   fixed it across seven audited git commits, and verified every fixed
   word against two external witnesses: a facsimile of the printed
   **Royal Thai edition** and the independent transcription at
   **84000.org**. Its hand-corrected corpus is this project's
   *reference*.
5. **This pipeline** re-derives the reference mechanically and
   reproducibly from the frozen rip, then applies a small set of
   additional, fully cataloged normalizations (§5), under a proven
   no-Pāli-touched guarantee (§6–7).

## 3. The corruption: diagnosis, not conjecture

The rip's missing table slots produced three artifact classes, all
mechanical and all identifiable by byte pattern:

| Class | Appears as | Cause |
|---|---|---|
| Latin-1 passthrough | `ß` (0xDF), `é`, `á`, `ö` emitted as-is | high byte had no table entry |
| PUA fallback | U+F812, U+F83C, U+F844… | byte emitted as U+F800+byte |
| Wrong table entry | `Ō` (U+014C), `⏓` (U+23D3) | partial/incorrect cmap slot |

**Evidence this is decoder damage and not textual variance:** in genuine
Pāli text, 100 % of the letter artifacts (`ṭh`, `ī`, `ū`, and `ḍ`
outside garbled annotation lines) occur at *word-initial* position —
exactly where the Fulbright font switches to its initial-form glyph
bank, the bank the ripper's table lacked. The apparatus-sign artifact
(`ßēé`/`ßēá` → `.M`/`.m`) is word-medial because that glyph attaches
after a witness sigla (`sīßēéa.` → `sī.Ma.`), which matches the second
missing category. The predecessor's census put the damage at 75,054
characters (0.132 % of its 56.6 M-character payload count); every
repaired reading was confirmed against the printed edition or 84000.org
by the predecessor project.

## 4. Correction taxonomy and protocols

Inherited from the predecessor project and enforced here:

- **T1** simple isolated fix · **T2** propagated mechanical fix (script)
  · **T3** fix requiring contextual judgment — **mandatory human
  approval, never automated** · **T4** structural/notation normalization
  (script + verification).
- **Protocol:** never alter Pāli body text; only format and notation are
  modifiable. Catalog before correcting. Same fix applied uniformly to
  all affected files. Unrecoverable content is preserved verbatim, never
  deleted or reconstructed by guesswork (§8).

## 5. The complete transformation catalog

Every change the pipeline makes, with its observed count (deterministic;
any deviation on a rerun means the input or code changed):

**T2 — reversal of decoder artifacts** (letter-level, each class
confirmed against external witnesses by the predecessor project):

| Stage | Transformation | Count |
|---|---|---|
| 2a | `ß ē U+F83C h` → `ṭh` (retroflex, word-initial) | 842 |
| 2b | `Ō`(+U+F844) → `ī` | 121 |
| 2c | `⏓`(+U+F844) → `ū` | 128 |
| 2d | `ß U+F812 ö` → `ḍ` | 106 |
| 2f | `ßēé` → `.M`, `ßēá` → `.m` (apparatus sign) | 22,025 + 1,530 |
| 2g | four residual incomplete sequences (`ß U+F812 ñ`→`ñ`, `ßē U+F83C a`→`a`, `ßē U+F83C ī`→`ī`, `ßēâ`→∅) | 20+3+1+2 |
| 2h | transliterated HTML husk stripped (`<`→`%`, `>`→`@`): `%a name="N"@%/a@` and `%span style="…"@$` removed, Pāli payload kept; 153 lines in 3 commentary files | 286 tags |

**T4 — notation/markup normalization** (zero letter impact; every
whitespace removal is adjacent to punctuation, so no two Pāli words can
ever be merged):

| Stage | Transformation | Count |
|---|---|---|
| 3a | footnote calls `[N]-` → `N-` | 2,517 |
| 3a-bis | footnote calls `[N-]` → `N-` (each verified against its page's notes) | 4 |
| 3b | apparatus punctuation: `sigla,`→`sigla.`, `sigla .`→`sigla.`, `. pe .`→`.pe.` | 41 files |
| 3c | restore missing `footnote:` prefix on spilled apparatus lines (heuristics: witness sigla incl. `i.` = PTS English ed., note numbers incl. ranges `N-N`) | 1,373 lines |
| 3d | unambiguous punctuation-only fixes from a full-corpus census: `. pe.`/`.pe,.`→`.pe.`, `ā :`→`ā:`, `" ,`→`",`, `N- ,`→`N-,`, `( x`/`x )`→`(x`/`x)` | 30 |
| 3e | **T3, human-approved**: one closing paren added to the extra-canonical citation parenthetical `(khu.ṇetti…, khu.milinda… (cha.Ma.)` in `33-Paramatthadipani-6.txt:6599` (Netti and Milindapañha are outside the Siamese canon; the parenthetical marks citations per the Burmese editions). Idempotent rule. | 1 |

All regexes use `[ \t]`, never `\s`, so no match can cross a line break
(a `\s` variant once merged two body lines; it is documented and
regression-guarded).

## 6. The cardinal rule: Pāli is inviolable

> The Pāli word sequence must be byte-identical to the reference. Only
> punctuation and notation may change, and only when unambiguous.
> Ambiguous candidates are documented, never auto-fixed.

Two — and only two — transformations carry non-Pāli *letters* and are
factored out before comparison, both fully mechanical:

1. the literal label `footnote:` restored by 3c on 11 rescued lines
   (structural markup, present on 39,900+ other lines);
2. the HTML husk removed by 2h (markup characters, `<a name…>`,
   `<span style…>` transliterated — no Pāli inside the removed bytes).

## 7. Verification gates (how the guarantee is proven, not asserted)

- **`utils/verify_pali.py`** — projects every file to its sequence of
  words (maximal Unicode-letter runs), factors out the two §6
  transforms, and compares against the reference corpus. Result on the
  current output: **115/115 identical**. Because entire *words* are
  compared, this also catches merges and splits, not just letter edits.
- **`utils/parser_simple.py`** — a zero-tolerance line-grammar parser:
  every line must be blank / `page number: NNN` / separator /
  `footnote:` / body; strict character whitelist; page sequence must
  increase by exactly 1; bracket, PTS-reference and anchor forms must
  match the documented grammar; parens/brackets must balance per file.
  Current residue: **65 flags, all in the cataloged irreducible set**
  (§8). Anything new = regression.
- **Structural validation** (`process_corpus.py --stage 4`) — every
  footnote call `N-` must have its note on the same page; page numbers
  unique, blank-line-preceded. 21,926 canonical pages, zero errors
  (235 transcription errors of the printed edition itself are
  whitelisted as `KNOWN_ERRORS`, listed individually in the script).
- **Two independent implementations** — `process_corpus.py` (Python)
  and `process_corpus.pl` (Perl) are maintained in parallel and their
  outputs are byte-identical, 115/115 (`cmp`). A bug would have to be
  implemented twice, identically, in two languages.
- **Determinism** — input pinned to commit `07c937d`; all counts in §5
  reproduce exactly on every run.

## 8. The irreducible residue (what we refuse to fix)

These survive in the output *on purpose*: their content was destroyed
before this project existed, and any repair would be conjecture — i.e.
fabricating scripture. The strict parser flags them permanently. The
complete inventory (regenerable at any time with
`python3 utils/parser_simple.py`):

**Lines carrying non-inventory characters — 13 lines, 3 groups:**

| Lines | Content |
|---|---|
| 01-Mahavibhanga-1:5957, 21-Anguttara-2:3580, 38-Yamaka-1:16920, 25-Khp-Dhp-Ud-Iti-Sn:10365 | `* neßēä(×áō)aṅacākalekhakh…` — garbled star-annotations (Latin-1 debris) |
| 01-Mahavibhanga-1:5961, 21-Anguttara-2:3582, 38-Yamaka-1:16924, 17-Samyutta-3:7398, 25-Khp-Dhp-Ud-Iti-Sn:8868, 25-Khp-Dhp-Ud-Iti-Sn:10369 | `nacha–…asayāmar…` / `śṁṁachaṛǣ…` — garbled segments with surviving PUA (U+F812, U+F814, U+F818, U+F81A, U+F830), stray diacritics, one C1 control (U+0090); preserved verbatim |
| 17-Paramatthajotika-1:1197 + 1199 | damaged apparatus zone: gloss `[dhamani=senalohita…]` with `=`, and residual `ßēä` debris |

**Other lost-content markers:**

| Item | Location |
|---|---|
| `[]` — note 5's bracket, content lost upstream | 15-Manorathapurani-2:6950 |
| word truncated at `@` (`…kusalākusal@`) | 54-Sammohavinodani:2340 |

**Intentional features of the printed edition:**

| Item | Locations |
|---|---|
| 11 empty `footnote:` blocks | 15-Samyutta-1:5934, 6239 · 17-Samyutta-3:2904, 6263, 8386 · 22-Anguttara-3:5628 · 26-Vv-Pv-Th-Thi:4317, 4697, 6415 · 37-Puggalakatha:5685, 8119 |

Additionally, ~139 star-annotation lines (`* mīkārkkhag …`, and e.g.
05-Mahavagga-2:329, 13-Majjhima-2:16995) are garbled beyond recovery
but consist of plain inventory letters, so the parser does not flag
them; they are cataloged in the predecessor's DOC.md §6.2 and likewise
left untouched.

Recovery of any of these would be legitimate **T3 work against the
printed facsimile** — human, sourced, one commit per fix — and stage 3e
exists as the place to encode each such approved repair.

## 9. What we deliberately did NOT normalize

Restraint is part of the method. Candidates found by census and left
alone, with reasons:

- **`footnote: N.` note-number style** (50 canonical, 4,112 commentary
  occurrences): the dot can collide with citation coordinates
  (`1. saṁ. nidāna. 35.`) — auto-removal risks corrupting references.
- **`N- :-` sequences** (183): plausibly lemma-separator notation, not
  established to be error.
- **Opening quote `` ` `` with morphological closure `…ti`** (2,213):
  edition typography, meaning-bearing.
- **`..` two-dot lacuna marks, `...`/`....` ellipses, dot leaders**:
  apparatus conventions.
- **Trailing whitespace** (2,630 lines): zero semantic value, and
  stripping it would touch the immutable damage lines.
- **Witness-list `sī., ma.` comma style** (~7,000): systematic edition
  convention.
- **`i` must never enter the 3b comma rule**: it would match the roman
  numeral in 1,956 PTS references (`(pts. vin i, 1)`). Documented as a
  hard warning in both implementations.

## 10. Audit it yourself

Everything above is falsifiable from a clean checkout:

```sh
# 1. Rebuild the corpus from the frozen rip (deterministic):
python3 utils/process_corpus.py            # or: perl utils/process_corpus.pl

# 2. Cross-check the two implementations (expect: no output = identical):
python3 utils/process_corpus.py --stage 1 && python3 utils/process_corpus.py --stage 2 \
  && python3 utils/process_corpus.py --stage 3 && sha256sum Canonical/*.txt Non-Canonical/*.txt > /tmp/py.sha
perl utils/process_corpus.pl && sha256sum Canonical/*.txt Non-Canonical/*.txt | diff /tmp/py.sha -

# 3. Prove the Pāli word sequence matches the hand-corrected reference:
python3 utils/verify_pali.py [path-to-reference-txt]   # expect 115/115

# 4. Census every remaining deviation from the strict grammar:
python3 utils/parser_simple.py             # expect exactly the §8 residue

# 5. Validate the apparatus structure of the canon:
python3 utils/process_corpus.py --stage 4  # expect zero errors

# 6. Inspect every character the pipeline ever changed:
python3 utils/process_corpus.py --stage 1  # pristine rip in Canonical/…
diff -r Canonical/ <your regenerated output>   # each hunk maps to §5
```

The transformation counts in §5 must reproduce exactly. If any command
disagrees with this document, the document is wrong — file the
discrepancy.

## 11. References

- Predecessor project (diagnosis, external verification, extended corpus
  reference): the `budsir_c` corpus project, kept locally alongside this
  repository — see its `DOC.md` (corpus grammar, witness siglas, parser
  routing by Nikāya) and `DOCUMENTATION.md`; a copy of both is kept
  untracked under `docs/`.
- Witness siglas: `ma.` Maramma, `cha.` Chaṭṭhasaṅgīti, `yu.` Yuropa
  (PTS), `ka.` Kambūjā, `po.` Porāṇa, `rā.` Rāmañña, `sī.` Sīhaḷa,
  `syā.` Syāmaraṭṭha (base edition), `i.` PTS English edition
  (commentaries only).
- External witnesses used for confirmation: Royal Thai edition facsimile;
  84000.org transcription.

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

A Pāli Tipiṭaka text corpus extracted ("ripped") from BUDSIR (Buddhist Scriptures Information Retrieval), plus a reproducible correction pipeline. The text is the **Royal Thai edition** (Syāmaraṭṭha, 45 volumes) — not the Burmese Chaṭṭhasaṅgīti. There is no application code here; the deliverable is the corrected corpus itself.

**`METHODOLOGY.md` is the authoritative statement** of provenance, the complete transformation catalog with counts, the integrity guarantees and the audit procedure. Keep it in sync with any pipeline change — a stale count there undermines the philological credibility the document exists to provide. **`FORMAT.md`** is the consumer-facing companion: the exact output line grammar, markers, apparatus/sigla conventions, and a minimal reference parser — keep it in sync too if the output format changes.

- `txt/Canonical/` (45 files) and `txt/Non-Canonical/` (70 files) — the raw extracted text, committed in git. The pristine source of truth is commit `07c937d` ("ripped from BUDSIR"); treat `txt/` as immutable input.
- `Canonical/` and `Non-Canonical/` at the repo root — **generated output** of the pipeline, committed in git (commit `103d43e` and successors). Never hand-edit these; regenerate with the pipeline and commit the regenerated result.
- `utils/process_corpus.py` and `utils/process_corpus.pl` — two equivalent implementations of the pipeline (same output).
- `docs/` (gitignored, local only) — reference documentation copied from the predecessor project (`~/Code/budsir/budsir_c/tipitaka.rte`): `DOC.md` (corpus catalog, corruption taxonomy, parser routing, correction protocols), `DOCUMENTATION.md` (original Spanish version), `known_errors.txt`. Read `docs/DOC.md` before making any claim about the corpus.

## Commands

```bash
python3 utils/process_corpus.py               # full pipeline (stages 1–5)
python3 utils/process_corpus.py --stage 2     # one stage only (1–5)
python3 utils/process_corpus.py --canonical   # canonical texts only (also: --non-canonical)
perl utils/process_corpus.pl                  # Perl equivalent (stages 1–3)

python3 utils/verify_pali.py [ref_dir]        # Pali-integrity gate — must print 115/115
                                              # ref: arg, $TIPITAKA_REFERENCE_DIR, or ../budsir/budsir_c/tipitaka.rte/txt
python3 utils/parser_simple.py [dir ...]      # homogeneity gate (default: both output dirs)
```

No build system, linter, or test suite — validation is pipeline stage 4 plus the two gates above.

## Pipeline architecture

Five stages, defined in `process_corpus.py`:

1. **Extract** — checks out `txt/` from commit `07c937d` into root `Canonical/` and `Non-Canonical/` (deletes and recreates those two dirs only).
2. **T2 encoding corrections** — fixes artifacts from the extraction tool, whose byte→Unicode table only covered BUDSIR's medial glyph bank and missed word-initial precomposed forms (ī, ū, ṭh, ḍ) and the apparatus abbreviation sign (.M/.m). Artifacts appear as Latin-1 passthrough (ß, é), PUA fallback (U+F8xx), or wrong cmap entries (Ō); all occur at word-initial position. See the header comment of `process_corpus.pl` for the full encoding story.
3. **T4 structural normalizations** — critical apparatus format: `[N]-` footnote calls → `N-`, sigla punctuation (`ma. cha. ka. po. rā. syā. sī. yu.`), and restoring missing `footnote:` prefixes on spilled apparatus lines.
4. **Structural validation** ("atleta_anciano") — zero-tolerance parser that checks every page: each body footnote call `N-` must have a matching note in that page's `footnote:` lines, page numbers unique and preceded by a blank line. `KNOWN_ERRORS` in the script whitelists 235 transcription errors present in the source edition itself; any *new* error is fatal (exit 1).
5. **Reference verification** ("conan") — optional; compares changed words against a scanned Royal Thai reference edition at `$BUDSIR_REF_DIR`; skipped when the variable is unset or the directory is absent.

## Corpus text format

Each `.txt` file is one printed volume, structured as repeating blocks:

```
page number: NNN
<body lines; footnote calls appear as "N-"; PTS refs as "(pts. d i, 2)">
footnote: <critical apparatus: note number, variant readings with sigla>
```

Pāli is romanized UTF-8 with diacritics (ṁ ā ī ū ṭ ḍ ṅ ñ ḷ …). If both scripts are modified, keep them behavior-identical (diff their outputs). Comparing the two pipelines against each other proves equivalence, not correctness — the authoritative reference for corrections is the hand-corrected corpus of the predecessor project (`~/Code/budsir/budsir_c/tipitaka.rte/txt/` at HEAD). The output equals that reference except for 195 lines in 17 files (2026-07-16): the stage-3d punctuation normalizations (30 fixes, 26 lines), 11 spilled apparatus lines rescued by extending the 3c heuristics (`i.` sigla and ranged note numbers `N-N`), 4 bracketed footnote calls `[N-]` → `N-` (3a-bis), 153 lines freed of transliterated HTML markup (stage 2h: `%a name="N"@%/a@` + `%span style="…"@$` husk removed, Pali payload kept; the lone damage `@` at `54-Sammohavinodani.txt:2340` is wontfix and must survive), and one T3 point correction approved by Jorge (stage 3e: closing paren added to the extra-canonical citation parenthetical in `33-Paramatthadipani-6.txt:6599`).

Two gates ship in `utils/`: `verify_pali.py` proves the cardinal rule (word-sequence projection vs the reference, factoring out the documented label/husk transforms — must print 115/115), and `parser_simple.py` is the homogeneity gate: a strict line-grammar parser that censuses every deviation. Its current residue (65 flags) is exactly the irreducible set inventoried in METHODOLOGY.md §8 — 13 lines with non-inventory characters (garbled star-annotations, PUA/control debris, one damaged gloss zone), one `[]` with lost content, one word truncated at `@`, and 11 intentionally empty `footnote:` blocks. If a pipeline change makes the parser report anything NOT in that inventory, the change introduced an inhomogeneity.

**Cardinal rule — Pali integrity**: the Pali word sequence is inviolable; only punctuation/notation may be normalized, and only when unambiguous. After any pipeline change, run `python3 utils/verify_pali.py` — the word sequence of every output file must equal the reference's (115/115); the script factors out the two documented letter-bearing transforms (restored `footnote:` labels, removed HTML husk). Ambiguous candidates (e.g. `footnote: N.` note numbers, which can collide with citations like `nidāna. 35.`) are documented, never auto-fixed.

Other invariants: leftover PUA code points on the garbled wontfix annotation lines are kept verbatim (no blanket orphan-PUA sweep); T4 regexes use `[ \t]`, never `\s`, so a match cannot cross a line break; trailing whitespace is left as-is (stripping it would touch wontfix lines). Undocumented-but-legitimate conventions found by census (do not "fix"): `` ` `` opens quotes closed morphologically by `…ti`; `..` is an apparatus lacuna mark; `#[N]` is a section anchor in six commentary files; `i.` is the PTS English edition sigla ("Inglish"), commentaries only — it is in the 3c/validator sigla regexes but must NEVER enter the 3b comma rule, where it would corrupt the roman numeral in PTS refs like `(pts. vin i, 1)` (1,956 hits). When verifying the letters-only projection, strip `^\s*footnote:` labels first (the 11 rescued lines legitimately add that word).

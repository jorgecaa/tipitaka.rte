# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

A Pāli Tipiṭaka text corpus extracted ("ripped") from BUDSIR (Buddhist Scriptures Information Retrieval), plus two layers of reproducible tooling built on top of it. The text is the **Royal Thai edition** (Syāmaraṭṭha / "Se", 45 canonical + 70 commentary volumes) — not the Burmese Chaṭṭhasaṅgīti.

The work falls into **two layers**, with different deliverables, different git treatment, and different rules. Knowing which layer a task belongs to is the first thing to establish:

| | **Layer 1 — correction** | **Layer 2 — indexing** |
|---|---|---|
| Delivers | the corrected corpus (`Canonical/`, `Non-Canonical/`) | a canonical-id index: `sutta-labels-reviewed.csv`, `commentary-index.csv` |
| Question it answers | "what did the edition say, cleaned of decoder damage?" | "which sutta is which — `SN 12.1`, `DN 1`… — across the Se↔CST editions?" |
| In git? | **yes** — corpus + the 4 pipeline scripts are pushed | **no** — git-excluded; tracked in a separate local repo `.git-analysis/` |
| Cardinal rule | Pali word sequence is inviolable | never touch Pali; only metadata may change |

**`METHODOLOGY.md`** is the authoritative statement of layer-1 provenance, the complete transformation catalog with counts, the integrity guarantees and the audit procedure — keep it in sync with any layer-1 pipeline change (a stale count there undermines the philological credibility it exists to provide). **`FORMAT.md`** is the consumer-facing companion: exact output line grammar, markers, apparatus/sigla conventions, and a minimal reference parser — keep it in sync if the output format changes. **`STRUCTURE.md`** (layer 2, local) is the per-volume unit-demarcation taxonomy that `extract_units.py` materializes.

## Repository layout

**Tracked in git** (the public corpus + layer-1 tooling):
- `txt/Canonical/` (45) and `txt/Non-Canonical/` (70) — the raw extracted text. The pristine source of truth is commit `07c937d` ("ripped from BUDSIR"); treat `txt/` as immutable input.
- `Canonical/` and `Non-Canonical/` at the repo root — **generated output** of the layer-1 pipeline (commit `103d43e` and successors). Never hand-edit; regenerate and commit.
- `utils/process_corpus.py` and `utils/process_corpus.pl` — the two equivalent layer-1 implementations (byte-identical output).
- `utils/verify_pali.py`, `utils/parser_simple.py` — the two integrity gates.
- `METHODOLOGY.md`, `FORMAT.md`, `README.md`, `UNLICENSE`, `.gitignore`.

**Git-excluded, tracked in the local `.git-analysis/` repo** (layer 2 — never push): all of `utils/` except the four above (~24 scripts), the data files at the repo root (`sutta-labels-reviewed.csv`, `sutta-labels.csv`, `commentary-index.csv`, `sutta-index*.csv`, `sandhi-*.json`, `sutta-fingerprints.json`, `helmer-*.csv`, `*-cache.json`, `rematch-results.csv`, etc.), the `read` CLI, `STRUCTURE.md`, the `*-README.md` files, `.claude/skills/`. `.git/info/exclude` enumerates them. Confirm with `git status` before any commit on this repo: layer-2 files must never appear staged here.

**Local-only, not in any git** (`docs/`, gitignored): reference documentation copied from the predecessor project (`~/Code/budsir/budsir_c/tipitaka.rte`): `DOC.md` (corpus catalog, corruption taxonomy, parser routing, correction protocols), `DOCUMENTATION.md` (Spanish original), `known_errors.txt`. Read `docs/DOC.md` before making any claim about the corpus.

## Commands

Layer 1 (correction pipeline):
```bash
python3 utils/process_corpus.py               # full pipeline (stages 1–5)
python3 utils/process_corpus.py --stage 2     # one stage only (1–5)
python3 utils/process_corpus.py --canonical   # canonical texts only (also: --non-canonical)
perl utils/process_corpus.pl                  # Perl equivalent (stages 1–3)

python3 utils/verify_pali.py [ref_dir]        # Pali-integrity gate — must print 115/115
                                              # ref: arg, $TIPITAKA_REFERENCE_DIR, or ../budsir/budsir_c/tipitaka.rte/txt
python3 utils/parser_simple.py [dir ...]      # homogeneity gate (default: both output dirs)
```

Layer 2 (indexing — see `.claude/skills/sutta-labels/SKILL.md` for the full pipeline order):
```bash
python3 utils/extract_units.py                # census of structural units in all 115 files
python3 utils/sutta_index.py                  # → sutta-index.csv (Sutta Piṭaka positions)
python3 utils/build_sandhi.py                 # one-shot: resolve DPD-unknown sandhi → sandhi-resolved.json
python3 utils/build_labels.py                 # → sutta-labels.csv (CST name + canonical id candidates)
python3 utils/helmer_review.py                # adjudicate flagged rows → sutta-labels-reviewed.csv
python3 utils/rematch.py                      # 2nd pass over Helmer-REJECTs (difflib re-rank + verify)
python3 utils/commentary_index.py --apply     # → commentary-index.csv (aṭṭhakathā ↔ canonical sutta)
python3 utils/audit_khuddaka.py [--apply]     # structural self-consistency check on reliability grades
python3 utils/validate_suttacentral.py        # independent ground-truth audit vs SuttaCentral
```

Reader (the consumer-facing entry point):
```bash
./read 'MN 14' | 'SN 12.1' | 'DN 1'           # by canonical id
./read 'S IV 304' | '(Se) M I 179'            # by Se citation
./read paṭiccasamuppāda                       # by name substring
./read -w 'MN 1'                              # -w = single-column stack instead of two
./read --ai 'MN 14'                           # Deepseek (Helmer Smith) compares the two editions
./read --random 10 --samyutta                 # 10 random from a nikāya (combine filters, add --ai)
```

No build system, linter, or test suite — validation is layer-1 stage 4 plus the two gates, and layer-2's three independent audits (below).

## Layer 1 — correction pipeline

Five stages, defined in `process_corpus.py`:

1. **Extract** — checks out `txt/` from commit `07c937d` into root `Canonical/` and `Non-Canonical/` (deletes and recreates those two dirs only).
2. **T2 encoding corrections** — fixes artifacts from the extraction tool, whose byte→Unicode table only covered BUDSIR's medial glyph bank and missed word-initial precomposed forms (ī, ū, ṭh, ḍ) and the apparatus abbreviation sign (.M/.m). Artifacts appear as Latin-1 passthrough (ß, é), PUA fallback (U+F8xx), or wrong cmap entries (Ō); all occur at word-initial position. See the header comment of `process_corpus.pl` for the full encoding story.
3. **T4 structural normalizations** — critical apparatus format: `[N]-` footnote calls → `N-`, sigla punctuation (`ma. cha. ka. po. rā. syā. sī. yu.`), and restoring missing `footnote:` prefixes on spilled apparatus lines.
4. **Structural validation** ("atleta_anciano") — zero-tolerance parser that checks every page of both corpora: each body footnote call `N-` must have a matching note in that page's `footnote:` lines, page numbers unique and preceded by a blank line. Note extraction accepts both numbering styles: bare (`1 ma. vuddhe.`) and dotted (`1. vi. cul. 7/379.`, ranges `1-2.`), the commentaries' standard; `N-` followed by digits+dot (Patimokkha dual rule numbering `11-1.`) is not a call. `KNOWN_ERRORS` in the script whitelists 566 orphan calls present in the source edition itself (142 Canonical, 424 Non-Canonical); any *new* error is fatal (exit 1).
5. **Reference verification** ("conan") — optional; compares changed words against a scanned Royal Thai reference edition at `$BUDSIR_REF_DIR`; skipped when the variable is unset or the directory is absent.

### Corpus text format

Each `.txt` file is one printed volume, structured as repeating blocks:

```
page number: NNN
<body lines; footnote calls appear as "N-"; PTS refs as "(pts. d i, 2)">
footnote: <critical apparatus: note number, variant readings with sigla>
```

Pāli is romanized UTF-8 with diacritics (ṁ ā ī ū ṭ ḍ ṅ ñ ḷ …). If both layer-1 scripts are modified, keep them behavior-identical (diff their outputs). Comparing the two pipelines against each other proves equivalence, not correctness — the authoritative reference for corrections is the hand-corrected corpus of the predecessor project (`~/Code/budsir/budsir_c/tipitaka.rte/txt/` at HEAD). The output equals that reference except for 195 lines in 17 files (2026-07-16): the stage-3d punctuation normalizations (30 fixes, 26 lines), 11 spilled apparatus lines rescued by extending the 3c heuristics (`i.` sigla and ranged note numbers `N-N`), 4 bracketed footnote calls `[N-]` → `N-` (3a-bis), 153 lines freed of transliterated HTML markup (stage 2h: `%a name="N"@%/a@` + `%span style="…"@$` husk removed, Pali payload kept; the lone damage `@` at `54-Sammohavinodani.txt:2340` is wontfix and must survive), and one T3 point correction approved by Jorge (stage 3e: closing paren added to the extra-canonical citation parenthetical in `33-Paramatthadipani-6.txt:6599`).

### Cardinal rule — Pali integrity (layer 1)

The Pali word sequence is inviolable; only punctuation/notation may be normalized, and only when unambiguous. After any pipeline change, run `python3 utils/verify_pali.py` — the word sequence of every output file must equal the reference's (115/115); the script factors out the two documented letter-bearing transforms (restored `footnote:` labels, removed HTML husk). Ambiguous candidates (e.g. `footnote: N.` note numbers, which can collide with citations like `nidāna. 35.`) are documented, never auto-fixed.

Other layer-1 invariants: leftover PUA code points on the garbled wontfix annotation lines are kept verbatim (no blanket orphan-PUA sweep); T4 regexes use `[ \t]`, never `\s`, so a match cannot cross a line break; trailing whitespace is left as-is (stripping it would touch wontfix lines). Undocumented-but-legitimate conventions found by census (do not "fix"): `` ` `` opens quotes closed morphologically by `…ti`; `..` is an apparatus lacuna mark; `#[N]` is a section anchor in six commentary files; `i.` is the PTS English edition sigla ("Inglish"), commentaries only — it is in the 3c/validator sigla regexes but must NEVER enter the 3b comma rule, where it would corrupt the roman numeral in PTS refs like `(pts. vin i, 1)` (1,956 hits). When verifying the letters-only projection, strip `^\s*footnote:` labels first (the 11 rescued lines legitimately add that word).

Two gates ship in `utils/`: `verify_pali.py` proves the cardinal rule (word-sequence projection vs the reference — must print 115/115), and `parser_simple.py` is the homogeneity gate: a strict line-grammar parser that censuses every deviation. Its current residue (65 flags) is exactly the irreducible set inventoried in METHODOLOGY.md §8 — 13 lines with non-inventory characters (garbled star-annotations, PUA/control debris, one damaged gloss zone), one `[]` with lost content, one word truncated at `@`, and 11 intentionally empty `footnote:` blocks. If a pipeline change makes the parser report anything NOT in that inventory, the change introduced an inhomogeneity.

## Layer 2 — cross-edition indexing

The Se edition leaves whole zones of the Sutta Piṭaka **unnamed** (bare ordinals in SN 2/4, no markers at all in SN 3/5 and the Aṅguttara Ekaka). Layer 2 gives each such unit its **CST suggested name** (the Burmese Chaṭṭhasaṅgāyana / DPR title) and **canonical id** (`SN 12.1`, `DN 1`, `Ja 290`…), and links each commentary (aṭṭhakathā) unit to the canonical sutta it explains. The Pali text is never touched — only metadata. Full pipeline order and per-stage detail live in `.claude/skills/sutta-labels/SKILL.md`; read it before extending the index.

**Deliverables** (all at repo root, git-excluded):
- `sutta-labels-reviewed.csv` — 6,383 Sutta Piṭaka units, each with Se cite/title, Se location (`se_file`/`se_lines`), CST suggested name, `canonical_id`, two confidences, a `review` disposition (`ok` / `grouped` / `REJECT` / `check` / `no-cst`), a `reliability` grade, and Helmer verdict. Effective coverage 6,243/6,383 (97.8%); the rest is honestly marked as editorial/structural divergence, never invented. Column reference in `sutta-labels-README.md`.
- `commentary-index.csv` — 2,736/2,959 (92.5%) commentary units linked to their canonical sutta via a monotonic name-subsequence match (the commentary comments a subset, so it is a subsequence, not 1:1). Column reference in `commentary-index-README.md`.

**External data sources** (all local on this machine — layer 2 cannot run on a fresh clone):
- **CST/Burmese text**: DPR XML at `~/Code/digitalpalireader/tipitaka/my/` (carries the aṭṭhakathā — the reason DPR beats SuttaCentral as the working comparison).
- **DPD (Digital Pāli Dictionary)**: `/dev/shm/dpd.db` (SQLite, read-only) — lemmatization + the `variant` field used to classify Se↔CST differences.
- **SuttaCentral**: `~/Code/Software/suttacentral/server/sc-data/.../name/sutta/{coll}-name_root-misc-site.json` — canonical-id ground truth, *independent* of the Burmese anchors.
- **tipitaka.critical** (Zigmond, CC0, 5-witness incl. Thai + CST): `~/Code/tipitaka.critical/` — expert ground truth for the untitled zones.
- **Deepseek**: `DEEPSEEK_API_KEY` env var; models `deepseek-v4-pro` (adjudication), `deepseek-v4-flash` (bulk). System role = "Helmer Smith, Pāli philologist" — the expert persona measurably improves output. The reasoning trace may wrap the JSON; extract with a regex, don't `json.loads` the whole response.

**Anti-bias validation framework.** Accuracy is measured by three *independent* signals, each more independent than the last: Burmese page anchors (~96%), Helmer+CollateX+DPD audit (`audit_helmer.py`, ~98%), SuttaCentral names (`validate_suttacentral.py`, 99.8% on titled volumes). Each more-independent check scored *higher* → the working metric under-counted. `reliability` grades encode how an individual id is pinned: `high` (long fragment + unique name), `verse` (gāthā confirmed by meter), `position` (pinned by order, as the uddāna records), `series` (best candidate, not certified), `grouped` (many-to-one member), `suspect` (breaks order / duplicates an id). Rule of thumb: trust `high` outright; trust the *series* in `series`, verify the exact number; investigate `suspect`. Peyyāla twins and Vinaya rule-numbering are genuinely irreducible — flag, do not force.

**Robustness contract for every LLM pass** (learned from real crashes; do not omit): per-call `timeout=180` + `max_retries`; a resumable JSON cache flushed every ~20 rows; a progress bar with ETA and running verdict tallies; a stall detector; DPD connection thread-local (SQLite is not concurrency-safe); CollateX guarded against an empty witness (ClusterShell `AssertionError`); one bad row degrades rather than kills the pass.

## Cardinal rule — Pali integrity (both layers)

Across both layers the same principle holds: **the Pali word sequence is inviolable.** Layer 1 may normalize punctuation/notation only when unambiguous; layer 2 changes metadata only. The `verify_pali.py` 115/115 gate is the single check that covers both — run it after any change to either layer that could conceivably touch corpus text.

tipitaka.rte
============

The Pāli Tipiṭaka in the **Syāmaraṭṭha (Royal Siamese) edition**
(1925–1928, 45 canonical volumes + 70 commentaries), digitized by BUDSIR
and extracted to plain UTF-8. 115 files, 49,357 pages, ~63.9 M characters.

- `txt/` — the raw rip, immutable (frozen at commit `07c937d`).
- `Canonical/`, `Non-Canonical/` — the corrected corpus, generated
  (never hand-edited) by a reproducible pipeline:
  `python3 utils/process_corpus.py` or `perl utils/process_corpus.pl`
  (two independent implementations, byte-identical output).

**Integrity guarantee:** the pipeline repairs mechanical decoder damage
and normalizes apparatus notation only — it has provably never added,
deleted, merged, split or altered a Pāli word. See **METHODOLOGY.md**
for the full provenance chain, the catalog of every transformation with
counts, the verification gates (`utils/verify_pali.py`,
`utils/parser_simple.py`), and the commands to audit every claim
yourself.

**Consuming the corpus:** see **FORMAT.md** — the exact file format
(line grammar, markers, apparatus and sigla), a minimal reference
parser, and a checklist for using the corpus in another project.

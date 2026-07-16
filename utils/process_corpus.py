#!/usr/bin/env python3
"""
process_corpus.py — Reproducible BUDSIR corpus processing pipeline.
====================================================================

Applies all documented corrections to the Tipitaka corpus extracted
from BUDSIR (Buddhist Scriptures Information Retrieval) and validates
the structural integrity of the result.  Full rationale, provenance
chain, transformation catalog and audit instructions: METHODOLOGY.md.

CARDINAL RULE: the Pali word sequence is inviolable.  Every stage
repairs mechanical decoder damage or normalizes notation/markup only;
utils/verify_pali.py proves word-sequence identity against the
hand-corrected reference corpus (115/115) after every change.

What it does:
  1. Extracts the original corpus from git (commit "ripped from BUDSIR")
  2. Applies T2 encoding corrections (decoder artifacts, stages 2a-2g)
     and strips transliterated HTML markup (2h)
  3. Applies T4 structural normalizations (critical apparatus format,
     3a/3a-bis/3b/3c), census-derived punctuation fixes (3d) and
     human-approved T3 point corrections (3e)
  4. Validates with zero-tolerance structural parser (atleta_anciano)
  5. Verifies against reference edition with conan (optional)

Output lands in Canonical/ and Non-Canonical/ at the repo root.
The Perl twin (process_corpus.pl) must stay byte-identical in output.

Usage:
    python3 utils/process_corpus.py               # full pipeline
    python3 utils/process_corpus.py --stage 2     # T2 corrections only
    python3 utils/process_corpus.py --stage 4     # structural validation only
    python3 utils/process_corpus.py --canonical   # canonical texts only
    python3 utils/process_corpus.py --help        # this help

Requirements: Python 3.9+, git, repo access.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════════

ORIGINAL_COMMIT = "07c937d"                    # commit "ripped from BUDSIR"
REPO_ROOT = Path(__file__).resolve().parent.parent  # repo root
CORPUS_SRC = "txt"                             # corpus source in git
CANON_DIR = REPO_ROOT / "Canonical"            # output: corrected Canonical
NONCANON_DIR = REPO_ROOT / "Non-Canonical"     # output: corrected Non-Canonical

# Royal Thai reference edition (optional, for stage 5)
# Set the BUDSIR_REF_DIR environment variable to the local path of the
# scanned Royal Thai reference edition; stage 5 is skipped when unset.
BUDSIR_REF_DIR = os.environ.get("BUDSIR_REF_DIR", "")

# Fulbright decoder code point removed alongside the O-macron and U+23D3
# fixes.  Any other PUA code point not consumed by a complete-sequence fix
# (U+F812, U+F814, U+F818, U+F81A, U+F830) sits on the unrecoverable
# garbled annotation lines (wontfix) and must be preserved — the
# hand-corrected reference corpus keeps them.
F844 = "\uf844"   # U+F844 — accompanies O-macron->i-macron and U+23D3->u-macron


# ═══════════════════════════════════════════════════════════════════════════════
# Known errors — orphan footnote calls in the original corpus
# ═══════════════════════════════════════════════════════════════════════════════
# Transcription errors in the source edition (566: 142 Canonical,
# 424 Non-Canonical). The structural validator (stage 4) will skip
# these entries to avoid false positives. Regenerate by running the
# validator with an empty whitelist and collecting the orphan calls.

KNOWN_ERRORS: set[str] = {
    # ── Canonical (45 vols) ──
    "01-Mahavibhanga-1.txt page 129: orphan call 3-",
    "01-Mahavibhanga-1.txt page 211: orphan call 6-",
    "01-Mahavibhanga-1.txt page 241: orphan call 341-",
    "02-Mahavibhanga-2.txt page 44: orphan call 2-",
    "02-Mahavibhanga-2.txt page 58: orphan call 2-",
    "02-Mahavibhanga-2.txt page 58: orphan call 3-",
    "02-Mahavibhanga-2.txt page 6: orphan call 4-",
    "04-Mahavagga-1.txt page 153: orphan call 3-",
    "04-Mahavagga-1.txt page 174: orphan call 2-",
    "04-Mahavagga-1.txt page 18: orphan call 3-",
    "04-Mahavagga-1.txt page 19: orphan call 1-",
    "04-Mahavagga-1.txt page 19: orphan call 2-",
    "04-Mahavagga-1.txt page 215: orphan call 3-",
    "04-Mahavagga-1.txt page 29: orphan call 9-",
    "04-Mahavagga-1.txt page 335: orphan call 1-",
    "05-Mahavagga-2.txt page 110: orphan call 2-",
    "05-Mahavagga-2.txt page 251: orphan call 6-",
    "06-Cullavagga-1.txt page 108: orphan call 5-",
    "06-Cullavagga-1.txt page 174: orphan call 2-",
    "06-Cullavagga-1.txt page 196: orphan call 1-",
    "06-Cullavagga-1.txt page 310: orphan call 5-",
    "06-Cullavagga-1.txt page 312: orphan call 3-",
    "06-Cullavagga-1.txt page 70: orphan call 2-",
    "07-Cullavagga-2.txt page 235: orphan call 6-",
    "07-Cullavagga-2.txt page 236: orphan call 3-",
    "07-Cullavagga-2.txt page 31: orphan call 2-",
    "08-Parivara.txt page 441: orphan call 2-",
    "09-Digha-1.txt page 60: orphan call 1-",
    "10-Digha-2.txt page 192: orphan call 2-",
    "10-Digha-2.txt page 34: orphan call 7-",
    "11-Digha-3.txt page 149: orphan call 4-",
    "11-Digha-3.txt page 149: orphan call 5-",
    "11-Digha-3.txt page 156: orphan call 4-",
    "11-Digha-3.txt page 243: orphan call 1-",
    "11-Digha-3.txt page 31: orphan call 1-",
    "12-Majjhima-1.txt page 333: orphan call 2-",
    "12-Majjhima-1.txt page 580: orphan call 1-",
    "13-Majjhima-2.txt page 239: orphan call 6-",
    "13-Majjhima-2.txt page 287: orphan call 7-",
    "13-Majjhima-2.txt page 312: orphan call 10-",
    "13-Majjhima-2.txt page 640: orphan call 1-",
    "13-Majjhima-2.txt page 689: orphan call 1-",
    "15-Samyutta-1.txt page 113: orphan call 1-",
    "15-Samyutta-1.txt page 140: orphan call 2-",
    "15-Samyutta-1.txt page 197: orphan call 5-",
    "15-Samyutta-1.txt page 226: orphan call 1-",
    "15-Samyutta-1.txt page 238: orphan call 1-",
    "15-Samyutta-1.txt page 256: orphan call 1-",
    "17-Samyutta-3.txt page 114: orphan call 1-",
    "17-Samyutta-3.txt page 153: orphan call 3-",
    "17-Samyutta-3.txt page 220: orphan call 1-",
    "17-Samyutta-3.txt page 243: orphan call 1-",
    "17-Samyutta-3.txt page 327: orphan call 2-",
    "17-Samyutta-3.txt page 328: orphan call 1-",
    "18-Samyutta-4.txt page 222: orphan call 6-",
    "18-Samyutta-4.txt page 70: orphan call 7-",
    "19-Samyutta-5.txt page 300: orphan call 1-",
    "19-Samyutta-5.txt page 384: orphan call 2-",
    "19-Samyutta-5.txt page 428: orphan call 10-",
    "19-Samyutta-5.txt page 428: orphan call 7-",
    "19-Samyutta-5.txt page 428: orphan call 8-",
    "19-Samyutta-5.txt page 428: orphan call 9-",
    "19-Samyutta-5.txt page 500: orphan call 3-",
    "19-Samyutta-5.txt page 529: orphan call 5-",
    "19-Samyutta-5.txt page 86: orphan call 1-",
    "20-Anguttara-1.txt page 257: orphan call 4-",
    "20-Anguttara-1.txt page 257: orphan call 5-",
    "20-Anguttara-1.txt page 257: orphan call 6-",
    "20-Anguttara-1.txt page 336: orphan call 4-",
    "20-Anguttara-1.txt page 336: orphan call 5-",
    "20-Anguttara-1.txt page 336: orphan call 6-",
    "20-Anguttara-1.txt page 42: orphan call 1-",
    "20-Anguttara-1.txt page 42: orphan call 2-",
    "20-Anguttara-1.txt page 84: orphan call 5-",
    "20-Anguttara-1.txt page 84: orphan call 6-",
    "20-Anguttara-1.txt page 84: orphan call 7-",
    "21-Anguttara-2.txt page 180: orphan call 1-",
    "21-Anguttara-2.txt page 190: orphan call 4-",
    "22-Anguttara-3.txt page 100: orphan call 2-",
    "22-Anguttara-3.txt page 222: orphan call 1-",
    "22-Anguttara-3.txt page 245: orphan call 3-",
    "22-Anguttara-3.txt page 300: orphan call 1-",
    "22-Anguttara-3.txt page 316: orphan call 1-",
    "22-Anguttara-3.txt page 344: orphan call 21-",
    "22-Anguttara-3.txt page 59: orphan call 3-",
    "23-Anguttara-4.txt page 146: orphan call 4-",
    "23-Anguttara-4.txt page 88: orphan call 2-",
    "24-Anguttara-5.txt page 150: orphan call 3-",
    "24-Anguttara-5.txt page 1: orphan call 5-",
    "24-Anguttara-5.txt page 2: orphan call 4-",
    "24-Anguttara-5.txt page 2: orphan call 5-",
    "25-Khp-Dhp-Ud-Iti-Sn.txt page 405: orphan call 334-",
    "25-Khp-Dhp-Ud-Iti-Sn.txt page 538: orphan call 4-",
    "25-Khp-Dhp-Ud-Iti-Sn.txt page 65: orphan call 3-",
    "26-Vv-Pv-Th-Thi.txt page 175: orphan call 5-",
    "26-Vv-Pv-Th-Thi.txt page 190: orphan call 8-",
    "26-Vv-Pv-Th-Thi.txt page 215: orphan call 2-",
    "26-Vv-Pv-Th-Thi.txt page 228: orphan call 3-",
    "26-Vv-Pv-Th-Thi.txt page 257: orphan call 4-",
    "26-Vv-Pv-Th-Thi.txt page 259: orphan call 5-",
    "26-Vv-Pv-Th-Thi.txt page 259: orphan call 7-",
    "26-Vv-Pv-Th-Thi.txt page 407: orphan call 2-",
    "26-Vv-Pv-Th-Thi.txt page 454: orphan call 2-",
    "26-Vv-Pv-Th-Thi.txt page 473: orphan call 2-",
    "27-Jataka-1.txt page 372: orphan call 5-",
    "28-Jataka-2.txt page 106: orphan call 4-",
    "28-Jataka-2.txt page 143: orphan call 2-",
    "28-Jataka-2.txt page 349: orphan call 4-",
    "28-Jataka-2.txt page 448: orphan call 2-",
    "30-Culaniddesa.txt page 130: orphan call 2-",
    "30-Culaniddesa.txt page 131: orphan call 6-",
    "30-Culaniddesa.txt page 209: orphan call 2-",
    "31-Patisambhidamagga.txt page 117: orphan call 5-",
    "31-Patisambhidamagga.txt page 117: orphan call 7-",
    "31-Patisambhidamagga.txt page 127: orphan call 4-",
    "31-Patisambhidamagga.txt page 127: orphan call 5-",
    "31-Patisambhidamagga.txt page 240: orphan call 4-",
    "32-Apadana-1.txt page 157: orphan call 5-",
    "32-Apadana-1.txt page 163: orphan call 64-",
    "32-Apadana-1.txt page 164: orphan call 65-",
    "32-Apadana-1.txt page 372: orphan call 2-",
    "32-Apadana-1.txt page 380: orphan call 1-",
    "32-Apadana-1.txt page 380: orphan call 2-",
    "33-Apadana-2.txt page 119: orphan call 5-",
    "33-Apadana-2.txt page 275: orphan call 4-",
    "33-Apadana-2.txt page 298: orphan call 3-",
    "33-Apadana-2.txt page 571: orphan call 7-",
    "35-Vibhanga.txt page 106: orphan call 1-",
    "35-Vibhanga.txt page 162: orphan call 1-",
    "35-Vibhanga.txt page 85: orphan call 1-",
    "35-Vibhanga.txt page 86: orphan call 1-",
    "37-Puggalakatha.txt page 170: orphan call 3-",
    "37-Puggalakatha.txt page 170: orphan call 6-",
    "37-Puggalakatha.txt page 220: orphan call 1-",
    "37-Puggalakatha.txt page 234: orphan call 2-",
    "37-Puggalakatha.txt page 240: orphan call 2-",
    "37-Puggalakatha.txt page 265: orphan call 2-",
    "37-Puggalakatha.txt page 310: orphan call 1-",
    "37-Puggalakatha.txt page 310: orphan call 2-",
    "37-Puggalakatha.txt page 509: orphan call 1-",
    "38-Yamaka-1.txt page 20: orphan call 2-",
    "38-Yamaka-1.txt page 674: orphan call 1485-",
    # ── Non-Canonical (70 vols) ──
    "01-Samanatapasadika-1.txt page 462: orphan call 2-",
    "01-Samanatapasadika-1.txt page 75: orphan call 2-",
    "02-Samanatapasadika-2.txt page 103: orphan call 4-",
    "02-Samanatapasadika-2.txt page 123: orphan call 4-",
    "02-Samanatapasadika-2.txt page 123: orphan call 5-",
    "02-Samanatapasadika-2.txt page 161: orphan call 4-",
    "02-Samanatapasadika-2.txt page 161: orphan call 5-",
    "02-Samanatapasadika-2.txt page 162: orphan call 4-",
    "02-Samanatapasadika-2.txt page 162: orphan call 5-",
    "02-Samanatapasadika-2.txt page 162: orphan call 9-",
    "02-Samanatapasadika-2.txt page 305: orphan call 3-",
    "02-Samanatapasadika-2.txt page 416: orphan call 1-",
    "02-Samanatapasadika-2.txt page 416: orphan call 2-",
    "02-Samanatapasadika-2.txt page 551: orphan call 1-",
    "02-Samanatapasadika-2.txt page 95: orphan call 1-",
    "03-Samanatapasadika-3.txt page 382: orphan call 1-",
    "04-Sumangalavilasini-1.txt page 248: orphan call 4-",
    "04-Sumangalavilasini-1.txt page 35: orphan call 5-",
    "04-Sumangalavilasini-1.txt page 96: orphan call 8-",
    "05-Sumangalavilasini-2.txt page 300: orphan call 1-",
    "05-Sumangalavilasini-2.txt page 310: orphan call 1-",
    "05-Sumangalavilasini-2.txt page 321: orphan call 1-",
    "05-Sumangalavilasini-2.txt page 358: orphan call 5-",
    "05-Sumangalavilasini-2.txt page 40: orphan call 3-",
    "05-Sumangalavilasini-2.txt page 40: orphan call 4-",
    "05-Sumangalavilasini-2.txt page 40: orphan call 5-",
    "06-Sumangalavilasini-3.txt page 110: orphan call 1-",
    "06-Sumangalavilasini-3.txt page 122: orphan call 2-",
    "06-Sumangalavilasini-3.txt page 152: orphan call 6-",
    "06-Sumangalavilasini-3.txt page 171: orphan call 6-",
    "06-Sumangalavilasini-3.txt page 184: orphan call 2-",
    "06-Sumangalavilasini-3.txt page 184: orphan call 3-",
    "06-Sumangalavilasini-3.txt page 184: orphan call 4-",
    "06-Sumangalavilasini-3.txt page 184: orphan call 5-",
    "06-Sumangalavilasini-3.txt page 184: orphan call 6-",
    "06-Sumangalavilasini-3.txt page 184: orphan call 7-",
    "06-Sumangalavilasini-3.txt page 184: orphan call 8-",
    "06-Sumangalavilasini-3.txt page 234: orphan call 2-",
    "07-Papancasudani-1.txt page 101: orphan call 6-",
    "07-Papancasudani-1.txt page 103: orphan call 2-",
    "07-Papancasudani-1.txt page 115: orphan call 3-",
    "07-Papancasudani-1.txt page 12: orphan call 8-",
    "07-Papancasudani-1.txt page 166: orphan call 1-",
    "07-Papancasudani-1.txt page 166: orphan call 2-",
    "07-Papancasudani-1.txt page 186: orphan call 2-",
    "07-Papancasudani-1.txt page 246: orphan call 2-",
    "07-Papancasudani-1.txt page 299: orphan call 3-",
    "07-Papancasudani-1.txt page 33: orphan call 2-",
    "07-Papancasudani-1.txt page 342: orphan call 8-",
    "07-Papancasudani-1.txt page 348: orphan call 11-",
    "07-Papancasudani-1.txt page 364: orphan call 6-",
    "07-Papancasudani-1.txt page 364: orphan call 7-",
    "07-Papancasudani-1.txt page 365: orphan call 6-",
    "07-Papancasudani-1.txt page 378: orphan call 12-",
    "07-Papancasudani-1.txt page 418: orphan call 2-",
    "07-Papancasudani-1.txt page 418: orphan call 3-",
    "07-Papancasudani-1.txt page 44: orphan call 2-",
    "07-Papancasudani-1.txt page 68: orphan call 7-",
    "07-Papancasudani-1.txt page 78: orphan call 1-",
    "07-Papancasudani-1.txt page 82: orphan call 5-",
    "08-Papancasudani-2.txt page 1: orphan call 6-",
    "08-Papancasudani-2.txt page 247: orphan call 4-",
    "08-Papancasudani-2.txt page 249: orphan call 1-",
    "08-Papancasudani-2.txt page 34: orphan call 2-",
    "09-Papancasudani-3.txt page 110: orphan call 1-",
    "09-Papancasudani-3.txt page 173: orphan call 3-",
    "09-Papancasudani-3.txt page 242: orphan call 4-",
    "09-Papancasudani-3.txt page 2: orphan call 10-",
    "09-Papancasudani-3.txt page 321: orphan call 3-",
    "09-Papancasudani-3.txt page 36: orphan call 2-",
    "09-Papancasudani-3.txt page 77: orphan call 2-",
    "09-Papancasudani-3.txt page 94: orphan call 10-",
    "10-Papancasudani-4.txt page 254: orphan call 4-",
    "10-Papancasudani-4.txt page 256: orphan call 1-",
    "11-Saratthappakasini-1.txt page 102: orphan call 7-",
    "11-Saratthappakasini-1.txt page 111: orphan call 6-",
    "11-Saratthappakasini-1.txt page 137: orphan call 1-",
    "11-Saratthappakasini-1.txt page 142: orphan call 12-",
    "11-Saratthappakasini-1.txt page 239: orphan call 2-",
    "11-Saratthappakasini-1.txt page 26: orphan call 1-",
    "11-Saratthappakasini-1.txt page 304: orphan call 4-",
    "11-Saratthappakasini-1.txt page 30: orphan call 4-",
    "11-Saratthappakasini-1.txt page 312: orphan call 9-",
    "11-Saratthappakasini-1.txt page 317: orphan call 7-",
    "11-Saratthappakasini-1.txt page 68: orphan call 6-",
    "11-Saratthappakasini-1.txt page 78: orphan call 6-",
    "11-Saratthappakasini-1.txt page 93: orphan call 3-",
    "12-Saratthappakasini-2.txt page 136: orphan call 6-",
    "12-Saratthappakasini-2.txt page 139: orphan call 5-",
    "12-Saratthappakasini-2.txt page 156: orphan call 3-",
    "12-Saratthappakasini-2.txt page 160: orphan call 2-",
    "12-Saratthappakasini-2.txt page 24: orphan call 5-",
    "12-Saratthappakasini-2.txt page 318: orphan call 5-",
    "12-Saratthappakasini-2.txt page 352: orphan call 1-",
    "12-Saratthappakasini-2.txt page 39: orphan call 2-",
    "12-Saratthappakasini-2.txt page 40: orphan call 1-",
    "12-Saratthappakasini-2.txt page 66: orphan call 7-",
    "12-Saratthappakasini-2.txt page 88: orphan call 5-",
    "12-Saratthappakasini-2.txt page 94: orphan call 4-",
    "13-Saratthappakasini-3.txt page 105: orphan call 1-",
    "13-Saratthappakasini-3.txt page 126: orphan call 3-",
    "13-Saratthappakasini-3.txt page 177: orphan call 1-",
    "13-Saratthappakasini-3.txt page 29: orphan call 3-",
    "13-Saratthappakasini-3.txt page 300: orphan call 4-",
    "13-Saratthappakasini-3.txt page 301: orphan call 2-",
    "13-Saratthappakasini-3.txt page 301: orphan call 3-",
    "14-Manorathapurani-1.txt page 200: orphan call 2-",
    "14-Manorathapurani-1.txt page 240: orphan call 3-",
    "14-Manorathapurani-1.txt page 420: orphan call 10-",
    "14-Manorathapurani-1.txt page 420: orphan call 11-",
    "14-Manorathapurani-1.txt page 420: orphan call 9-",
    "14-Manorathapurani-1.txt page 473: orphan call 8-",
    "15-Manorathapurani-2.txt page 120: orphan call 6-",
    "15-Manorathapurani-2.txt page 147: orphan call 6-",
    "15-Manorathapurani-2.txt page 183: orphan call 4-",
    "15-Manorathapurani-2.txt page 183: orphan call 5-",
    "15-Manorathapurani-2.txt page 200: orphan call 1-",
    "15-Manorathapurani-2.txt page 267: orphan call 5-",
    "15-Manorathapurani-2.txt page 268: orphan call 14-",
    "15-Manorathapurani-2.txt page 269: orphan call 5-",
    "15-Manorathapurani-2.txt page 342: orphan call 3-",
    "15-Manorathapurani-2.txt page 434: orphan call 1-",
    "15-Manorathapurani-2.txt page 434: orphan call 2-",
    "15-Manorathapurani-2.txt page 434: orphan call 3-",
    "15-Manorathapurani-2.txt page 53: orphan call 4-",
    "16-Manorathapurani-3.txt page 234: orphan call 2-",
    "16-Manorathapurani-3.txt page 234: orphan call 3-",
    "16-Manorathapurani-3.txt page 234: orphan call 4-",
    "16-Manorathapurani-3.txt page 234: orphan call 5-",
    "16-Manorathapurani-3.txt page 367: orphan call 2-",
    "16-Manorathapurani-3.txt page 91: orphan call 1-",
    "17-Paramatthajotika-1.txt page 101: orphan call 6-",
    "17-Paramatthajotika-1.txt page 106: orphan call 4-",
    "17-Paramatthajotika-1.txt page 114: orphan call 6-",
    "17-Paramatthajotika-1.txt page 120: orphan call 4-",
    "17-Paramatthajotika-1.txt page 190: orphan call 6-",
    "17-Paramatthajotika-1.txt page 200: orphan call 5-",
    "17-Paramatthajotika-1.txt page 200: orphan call 6-",
    "17-Paramatthajotika-1.txt page 200: orphan call 7-",
    "17-Paramatthajotika-1.txt page 48: orphan call 5-",
    "18-Dhammapadatthakatha-1.txt page 106: orphan call 3-",
    "18-Dhammapadatthakatha-1.txt page 135: orphan call 7-",
    "19-Dhammapadatthakatha-2.txt page 12: orphan call 2-",
    "19-Dhammapadatthakatha-2.txt page 3: orphan call 2-",
    "21-Dhammapadatthakatha-4.txt page 37: orphan call 1-",
    "21-Dhammapadatthakatha-4.txt page 60: orphan call 1-",
    "23-Dhammapadatthakatha-6.txt page 116: orphan call 5-",
    "24-Dhammapadatthakatha-7.txt page 150: orphan call 5-",
    "24-Dhammapadatthakatha-7.txt page 151: orphan call 2-",
    "24-Dhammapadatthakatha-7.txt page 158: orphan call 3-",
    "24-Dhammapadatthakatha-7.txt page 46: orphan call 2-",
    "24-Dhammapadatthakatha-7.txt page 90: orphan call 1-",
    "26-Paramatthadipani-1.txt page 12: orphan call 6-",
    "26-Paramatthadipani-1.txt page 284: orphan call 1-",
    "26-Paramatthadipani-1.txt page 301: orphan call 3-",
    "26-Paramatthadipani-1.txt page 33: orphan call 2-",
    "27-Paramatthadipani-2.txt page 161: orphan call 2-",
    "27-Paramatthadipani-2.txt page 233: orphan call 1-",
    "27-Paramatthadipani-2.txt page 93: orphan call 1-",
    "28-Paramatthajotika-2.txt page 146: orphan call 4-",
    "28-Paramatthajotika-2.txt page 151: orphan call 3-",
    "28-Paramatthajotika-2.txt page 168: orphan call 8-",
    "28-Paramatthajotika-2.txt page 206: orphan call 5-",
    "28-Paramatthajotika-2.txt page 211: orphan call 7-",
    "28-Paramatthajotika-2.txt page 288: orphan call 5-",
    "29-Paramatthajotika-3.txt page 21: orphan call 1-",
    "29-Paramatthajotika-3.txt page 420: orphan call 2-",
    "29-Paramatthajotika-3.txt page 420: orphan call 3-",
    "30-Paramatthadipani-3.txt page 11: orphan call 6-",
    "30-Paramatthadipani-3.txt page 132: orphan call 3-",
    "30-Paramatthadipani-3.txt page 162: orphan call 3-",
    "30-Paramatthadipani-3.txt page 17: orphan call 4-",
    "30-Paramatthadipani-3.txt page 361: orphan call 2-",
    "30-Paramatthadipani-3.txt page 42: orphan call 3-",
    "30-Paramatthadipani-3.txt page 71: orphan call 2-",
    "31-Paramatthadipani-4.txt page 120: orphan call 1-",
    "31-Paramatthadipani-4.txt page 120: orphan call 2-",
    "31-Paramatthadipani-4.txt page 180: orphan call 1-",
    "31-Paramatthadipani-4.txt page 180: orphan call 2-",
    "31-Paramatthadipani-4.txt page 200: orphan call 4-",
    "31-Paramatthadipani-4.txt page 200: orphan call 5-",
    "31-Paramatthadipani-4.txt page 200: orphan call 6-",
    "31-Paramatthadipani-4.txt page 22: orphan call 3-",
    "31-Paramatthadipani-4.txt page 276: orphan call 2-",
    "31-Paramatthadipani-4.txt page 310: orphan call 1-",
    "32-Paramatthadipani-5.txt page 102: orphan call 11-",
    "32-Paramatthadipani-5.txt page 37: orphan call 7-",
    "32-Paramatthadipani-5.txt page 482: orphan call 5-",
    "32-Paramatthadipani-5.txt page 50: orphan call 9-",
    "32-Paramatthadipani-5.txt page 571: orphan call 4-",
    "32-Paramatthadipani-5.txt page 581: orphan call 4-",
    "33-Paramatthadipani-6.txt page 204: orphan call 1-",
    "33-Paramatthadipani-6.txt page 272: orphan call 1-",
    "34-Paramatthadipani-7.txt page 340: orphan call 1-",
    "34-Paramatthadipani-7.txt page 340: orphan call 2-",
    "34-Paramatthadipani-7.txt page 340: orphan call 3-",
    "34-Paramatthadipani-7.txt page 340: orphan call 4-",
    "34-Paramatthadipani-7.txt page 340: orphan call 5-",
    "34-Paramatthadipani-7.txt page 60: orphan call 4-",
    "34-Paramatthadipani-7.txt page 75: orphan call 3-",
    "35-Jatakatthakatha-1.txt page 46: orphan call 1-",
    "37-Jatakatthakatha-3.txt page 300: orphan call 1-",
    "37-Jatakatthakatha-3.txt page 340: orphan call 3-",
    "39-Jatakatthakatha-5.txt page 19: orphan call 1-",
    "43-Jatakatthakatha-9.txt page 79: orphan call 1-",
    "44-Jatakatthakatha-10.txt page 286: orphan call 1-",
    "45-Mahaniddesatthakatha.txt page 16: orphan call 5-",
    "45-Mahaniddesatthakatha.txt page 288: orphan call 7-",
    "45-Mahaniddesatthakatha.txt page 288: orphan call 8-",
    "45-Mahaniddesatthakatha.txt page 31: orphan call 1-",
    "45-Mahaniddesatthakatha.txt page 3: orphan call 11-",
    "45-Mahaniddesatthakatha.txt page 3: orphan call 7-",
    "45-Mahaniddesatthakatha.txt page 3: orphan call 8-",
    "45-Mahaniddesatthakatha.txt page 60: orphan call 9-",
    "45-Mahaniddesatthakatha.txt page 6: orphan call 13-",
    "45-Mahaniddesatthakatha.txt page 6: orphan call 14-",
    "45-Mahaniddesatthakatha.txt page 6: orphan call 15-",
    "45-Mahaniddesatthakatha.txt page 83: orphan call 4-",
    "46-Culaniddesatthakatha.txt page 133: orphan call 2-",
    "46-Culaniddesatthakatha.txt page 53: orphan call 2-",
    "47-Saddhammappakasini-1.txt page 321: orphan call 25-",
    "48-Saddhammappakasini-2.txt page 269: orphan call 2-",
    "48-Saddhammappakasini-2.txt page 271: orphan call 1-",
    "48-Saddhammappakasini-2.txt page 271: orphan call 4-",
    "48-Saddhammappakasini-2.txt page 323: orphan call 6-",
    "48-Saddhammappakasini-2.txt page 96: orphan call 1-",
    "48-Saddhammappakasini-2.txt page 96: orphan call 2-",
    "49-Appadanatthakatha-1.txt page 212: orphan call 2-",
    "50-Appadanatthakatha-2.txt page 196: orphan call 2-",
    "50-Appadanatthakatha-2.txt page 269: orphan call 3-",
    "50-Appadanatthakatha-2.txt page 324: orphan call 2-",
    "50-Appadanatthakatha-2.txt page 9: orphan call 3-",
    "51-Madhuratthavilasini.txt page 103: orphan call 6-",
    "51-Madhuratthavilasini.txt page 199: orphan call 2-",
    "51-Madhuratthavilasini.txt page 201: orphan call 5-",
    "51-Madhuratthavilasini.txt page 212: orphan call 5-",
    "51-Madhuratthavilasini.txt page 274: orphan call 2-",
    "51-Madhuratthavilasini.txt page 28: orphan call 1-",
    "51-Madhuratthavilasini.txt page 330: orphan call 2-",
    "51-Madhuratthavilasini.txt page 56: orphan call 2-",
    "51-Madhuratthavilasini.txt page 73: orphan call 4-",
    "52-Cariyapitakatthakatha.txt page 10: orphan call 1-",
    "52-Cariyapitakatthakatha.txt page 12: orphan call 10-",
    "52-Cariyapitakatthakatha.txt page 12: orphan call 11-",
    "52-Cariyapitakatthakatha.txt page 12: orphan call 12-",
    "52-Cariyapitakatthakatha.txt page 12: orphan call 7-",
    "52-Cariyapitakatthakatha.txt page 12: orphan call 8-",
    "52-Cariyapitakatthakatha.txt page 12: orphan call 9-",
    "52-Cariyapitakatthakatha.txt page 213: orphan call 1-",
    "52-Cariyapitakatthakatha.txt page 25: orphan call 1-",
    "52-Cariyapitakatthakatha.txt page 319: orphan call 7-",
    "52-Cariyapitakatthakatha.txt page 319: orphan call 8-",
    "52-Cariyapitakatthakatha.txt page 320: orphan call 14-",
    "52-Cariyapitakatthakatha.txt page 344: orphan call 7-",
    "52-Cariyapitakatthakatha.txt page 34: orphan call 2-",
    "52-Cariyapitakatthakatha.txt page 40: orphan call 4-",
    "52-Cariyapitakatthakatha.txt page 40: orphan call 5-",
    "52-Cariyapitakatthakatha.txt page 40: orphan call 6-",
    "53-Atthasalini.txt page 225: orphan call 9-",
    "53-Atthasalini.txt page 228: orphan call 3-",
    "53-Atthasalini.txt page 463: orphan call 5-",
    "54-Sammohavinodani.txt page 209: orphan call 1-",
    "54-Sammohavinodani.txt page 300: orphan call 1-",
    "54-Sammohavinodani.txt page 309: orphan call 2-",
    "54-Sammohavinodani.txt page 317: orphan call 3-",
    "54-Sammohavinodani.txt page 377: orphan call 4-",
    "55-Pancappakarana.txt page 391: orphan call 2-",
    "55-Pancappakarana.txt page 572: orphan call 19-",
    "55-Pancappakarana.txt page 5: orphan call 2-",
    "55-Pancappakarana.txt page 6: orphan call 3-",
    "57-Visuddhimagga-1.txt page 145: orphan call 2-",
    "58-Visuddhimagga-2.txt page 103: orphan call 3-",
    "58-Visuddhimagga-2.txt page 110: orphan call 3-",
    "58-Visuddhimagga-2.txt page 161: orphan call 1-",
    "58-Visuddhimagga-2.txt page 167: orphan call 1-",
    "58-Visuddhimagga-2.txt page 175: orphan call 2-",
    "58-Visuddhimagga-2.txt page 36: orphan call 1-",
    "58-Visuddhimagga-2.txt page 50: orphan call 2-",
    "58-Visuddhimagga-2.txt page 94: orphan call 1-",
    "59-Visuddhimagga-3.txt page 181: orphan call 1-",
    "59-Visuddhimagga-3.txt page 289: orphan call 1-",
    "59-Visuddhimagga-3.txt page 349: orphan call 2-",
    "59-Visuddhimagga-3.txt page 354: orphan call 3-",
    "59-Visuddhimagga-3.txt page 359: orphan call 3-",
    "59-Visuddhimagga-3.txt page 377: orphan call 2-",
    "60-Abhidhammatthasangaha.txt page 198: orphan call 1-",
    "61-Paramatthamanjusa-1.txt page 15: orphan call 2-",
    "61-Paramatthamanjusa-1.txt page 202: orphan call 1-",
    "61-Paramatthamanjusa-1.txt page 213: orphan call 1-",
    "61-Paramatthamanjusa-1.txt page 267: orphan call 1-",
    "61-Paramatthamanjusa-1.txt page 267: orphan call 2-",
    "61-Paramatthamanjusa-1.txt page 280: orphan call 2-",
    "61-Paramatthamanjusa-1.txt page 313: orphan call 1-",
    "61-Paramatthamanjusa-1.txt page 327: orphan call 1-",
    "61-Paramatthamanjusa-1.txt page 327: orphan call 2-",
    "61-Paramatthamanjusa-1.txt page 362: orphan call 2-",
    "61-Paramatthamanjusa-1.txt page 376: orphan call 2-",
    "61-Paramatthamanjusa-1.txt page 389: orphan call 3-",
    "61-Paramatthamanjusa-1.txt page 64: orphan call 2-",
    "63-Paramatthamanjusa-3.txt page 186: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 186: orphan call 2-",
    "63-Paramatthamanjusa-3.txt page 364: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 401: orphan call 2-",
    "63-Paramatthamanjusa-3.txt page 421: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 575: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 575: orphan call 2-",
    "63-Paramatthamanjusa-3.txt page 576: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 576: orphan call 2-",
    "63-Paramatthamanjusa-3.txt page 577: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 577: orphan call 2-",
    "63-Paramatthamanjusa-3.txt page 579: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 579: orphan call 2-",
    "63-Paramatthamanjusa-3.txt page 579: orphan call 3-",
    "63-Paramatthamanjusa-3.txt page 579: orphan call 4-",
    "63-Paramatthamanjusa-3.txt page 581: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 581: orphan call 2-",
    "63-Paramatthamanjusa-3.txt page 582: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 582: orphan call 2-",
    "63-Paramatthamanjusa-3.txt page 583: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 583: orphan call 2-",
    "63-Paramatthamanjusa-3.txt page 583: orphan call 3-",
    "63-Paramatthamanjusa-3.txt page 584: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 584: orphan call 2-",
    "63-Paramatthamanjusa-3.txt page 584: orphan call 3-",
    "63-Paramatthamanjusa-3.txt page 585: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 585: orphan call 2-",
    "63-Paramatthamanjusa-3.txt page 585: orphan call 3-",
    "63-Paramatthamanjusa-3.txt page 586: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 586: orphan call 2-",
    "63-Paramatthamanjusa-3.txt page 586: orphan call 3-",
    "63-Paramatthamanjusa-3.txt page 587: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 588: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 588: orphan call 2-",
    "63-Paramatthamanjusa-3.txt page 588: orphan call 3-",
    "63-Paramatthamanjusa-3.txt page 588: orphan call 4-",
    "63-Paramatthamanjusa-3.txt page 589: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 589: orphan call 2-",
    "63-Paramatthamanjusa-3.txt page 590: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 591: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 592: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 595: orphan call 2-",
    "63-Paramatthamanjusa-3.txt page 596: orphan call 2-",
    "63-Paramatthamanjusa-3.txt page 597: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 597: orphan call 2-",
    "63-Paramatthamanjusa-3.txt page 598: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 598: orphan call 2-",
    "63-Paramatthamanjusa-3.txt page 599: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 600: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 602: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 604: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 605: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 605: orphan call 2-",
    "63-Paramatthamanjusa-3.txt page 605: orphan call 3-",
    "63-Paramatthamanjusa-3.txt page 605: orphan call 4-",
    "63-Paramatthamanjusa-3.txt page 609: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 611: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 611: orphan call 2-",
    "63-Paramatthamanjusa-3.txt page 611: orphan call 3-",
    "63-Paramatthamanjusa-3.txt page 614: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 615: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 617: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 617: orphan call 2-",
    "63-Paramatthamanjusa-3.txt page 617: orphan call 3-",
    "63-Paramatthamanjusa-3.txt page 622: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 624: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 625: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 626: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 626: orphan call 2-",
    "63-Paramatthamanjusa-3.txt page 627: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 628: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 629: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 629: orphan call 2-",
    "63-Paramatthamanjusa-3.txt page 633: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 633: orphan call 2-",
    "63-Paramatthamanjusa-3.txt page 637: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 638: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 639: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 642: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 642: orphan call 2-",
    "63-Paramatthamanjusa-3.txt page 643: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 656: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 656: orphan call 2-",
    "63-Paramatthamanjusa-3.txt page 656: orphan call 3-",
    "63-Paramatthamanjusa-3.txt page 658: orphan call 1-",
    "63-Paramatthamanjusa-3.txt page 658: orphan call 2-",
    "63-Paramatthamanjusa-3.txt page 658: orphan call 3-",
    "63-Paramatthamanjusa-3.txt page 658: orphan call 4-",
    "63-Paramatthamanjusa-3.txt page 658: orphan call 5-",
    "64-Saratthadipani-1.txt page 179: orphan call 1-",
    "64-Saratthadipani-1.txt page 504: orphan call 1-",
    "65-Saratthadipani-2.txt page 80: orphan call 1-",
    "67-Saratthadipani-4.txt page 256: orphan call 1-",
    "67-Saratthadipani-4.txt page 292: orphan call 1-",
    "67-Saratthadipani-4.txt page 293: orphan call 1-",
    "67-Saratthadipani-4.txt page 319: orphan call 2-",
    "67-Saratthadipani-4.txt page 406: orphan call 2-",
    "67-Saratthadipani-4.txt page 40: orphan call 2-",
    "67-Saratthadipani-4.txt page 40: orphan call 3-",
    "67-Saratthadipani-4.txt page 493: orphan call 1-",
    "67-Saratthadipani-4.txt page 81: orphan call 1-",
    "68-Mangalatthadipani-1.txt page 15: orphan call 3-",
    "68-Mangalatthadipani-1.txt page 289: orphan call 1-",
    "68-Mangalatthadipani-1.txt page 356: orphan call 1-",
    "69-Mangalatthadipani-2.txt page 223: orphan call 3-",
    "69-Mangalatthadipani-2.txt page 236: orphan call 2-",
    "69-Mangalatthadipani-2.txt page 295: orphan call 2-",
    "69-Mangalatthadipani-2.txt page 367: orphan call 3-",
    "69-Mangalatthadipani-2.txt page 413: orphan call 1-",
    "69-Mangalatthadipani-2.txt page 413: orphan call 2-",
    "69-Mangalatthadipani-2.txt page 470: orphan call 3-",
    "69-Mangalatthadipani-2.txt page 470: orphan call 4-",
    "69-Mangalatthadipani-2.txt page 51: orphan call 4-",
    "69-Mangalatthadipani-2.txt page 51: orphan call 5-",
    "69-Mangalatthadipani-2.txt page 51: orphan call 6-",
    "70-Patimokkhapali.txt page 18: orphan call 14-",
    "70-Patimokkhapali.txt page 20: orphan call 22-",
    "70-Patimokkhapali.txt page 21: orphan call 28-",
    "70-Patimokkhapali.txt page 23: orphan call 11-",
    "70-Patimokkhapali.txt page 25: orphan call 22-",
    "70-Patimokkhapali.txt page 25: orphan call 24-",
    "70-Patimokkhapali.txt page 26: orphan call 26-",
    "70-Patimokkhapali.txt page 31: orphan call 59-",
    "70-Patimokkhapali.txt page 31: orphan call 63-",
    "70-Patimokkhapali.txt page 32: orphan call 68-",
}


# ═══════════════════════════════════════════════════════════════════════════════
# Utilities
# ═══════════════════════════════════════════════════════════════════════════════

def log(msg: str = "", prefix: str = "  ") -> None:
    """Print timestamped message."""
    ts = datetime.now().strftime("%H:%M:%S")
    if msg:
        print(f"{prefix}[{ts}] {msg}")
    else:
        print()


def die(msg: str) -> None:
    """Exit with fatal error."""
    print(f"\nFATAL: {msg}", file=sys.stderr)
    sys.exit(1)


def step_header(num: int, title: str) -> None:
    """Print pipeline stage header."""
    print()
    print(f"{'='*60}")
    print(f" [{num}/5] {title}")
    print(f"{'='*60}")


def git(*args: str) -> str:
    """Run git command and return stdout."""
    r = subprocess.run(
        ["git", *args],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    if r.returncode != 0:
        die(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


# ═══════════════════════════════════════════════════════════════════════════════
# Stage 1 — Extract original corpus from git
# ═══════════════════════════════════════════════════════════════════════════════

def stage1_extract() -> tuple[int, int]:
    """Extract original .txt files from base commit into Canonical/ and
    Non-Canonical/ at the repo root.

    Only deletes Canonical/ and Non-Canonical/ — never the repo itself.

    Returns:
        (total_files, size_kb)
    """
    step_header(1, "Extracting original corpus from git")

    # Clean only the output directories, never the repo root
    for d in (CANON_DIR, NONCANON_DIR):
        if d.exists():
            shutil.rmtree(d)
    CANON_DIR.mkdir(parents=True)
    NONCANON_DIR.mkdir(parents=True)

    tree = git("ls-tree", "-r", "--name-only", ORIGINAL_COMMIT, f"{CORPUS_SRC}/")
    files = [f.strip() for f in tree.splitlines() if f.strip().endswith(".txt")]

    for f in files:
        rel = f.removeprefix(f"{CORPUS_SRC}/")  # Canonical/01-...txt
        out = REPO_ROOT / rel
        content = git("show", f"{ORIGINAL_COMMIT}:{f}")
        out.write_text(content, encoding="utf-8")

    total = len(files)
    size_kb = sum(
        (REPO_ROOT / f.removeprefix(f"{CORPUS_SRC}/")).stat().st_size
        for f in files
    ) // 1024

    log(f"Extracted {total} files ({size_kb} KB)")
    log(f"  Canonical: {len(list(CANON_DIR.glob('*.txt')))}")
    log(f"  Non-Canonical: {len(list(NONCANON_DIR.glob('*.txt')))}")
    return total, size_kb


# ═══════════════════════════════════════════════════════════════════════════════
# Stage 2 — T2 encoding corrections (Fulbright decoder artifacts)
# ═══════════════════════════════════════════════════════════════════════════════

def _all_output_files() -> list[Path]:
    """Return all .txt files in Canonical/ and Non-Canonical/."""
    result = list(CANON_DIR.rglob("*.txt"))
    result.extend(NONCANON_DIR.rglob("*.txt"))
    return result


def stage2_t2_corrections() -> dict:
    """Apply all 6 T2 encoding corrections to every .txt in the output dirs.

    Returns:
        dict with counters per correction type.
    """
    step_header(2, "T2 encoding corrections (Fulbright decoder)")

    stats: dict[str, int] = {}
    files = _all_output_files()
    total_files = len(files)

    def _read(path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def _write(path: Path, text: str) -> None:
        path.write_text(text, encoding="utf-8")

    # ── 2a. Retroflex th: U+00DF U+0113 U+F83C h -> t-underdot+h  (842 occ) ──
    label = "Retroflex th (ss+ee+U+F83C+h -> t-underdot+h)"
    log(label + " ...")
    pattern = "\u00df\u0113\uf83ch"
    replacement = "\u1e6dh"
    count = 0
    examples: list[tuple[str, str]] = []
    for fp in files:
        t = _read(fp)
        if pattern not in t:
            continue
        if len(examples) < 3:
            for m in re.finditer(
                r'[^\s\[\](),.;:\-]*' + re.escape(pattern) + r'[^\s\[\](),.;:\-]*', t
            ):
                ow = m.group(0)
                cw = ow.replace(pattern, replacement)
                if ow != cw and (ow, cw) not in examples:
                    examples.append((ow, cw))
                if len(examples) >= 3:
                    break
        c = t.count(pattern)
        count += c
        _write(fp, t.replace(pattern, replacement))
    for ow, cw in examples[:3]:
        log(f"  ex: {ow} -> {cw}")
    log(f"  -> {count} occurrences")
    stats[label] = count
    log()

    # ── 2b. Long vowel ii: O-macron -> i-macron  (121 occ) ──
    # Also removes orphan U+F844 that accompanies O-macron.
    label = "Long vowel ii (O-macron -> i-macron)"
    log(label + " ...")
    pattern_ii = "\u014c"
    replacement_ii = "\u012b"
    count = 0
    examples = []
    for fp in files:
        t = _read(fp)
        if pattern_ii not in t:
            continue
        if len(examples) < 3:
            for m in re.finditer(
                r'[^\s\[\](),.;:\-]*' + re.escape(pattern_ii) + r'[^\s\[\](),.;:\-]*', t
            ):
                ow = m.group(0)
                cw = ow.replace(pattern_ii, replacement_ii).replace(F844, "")
                if ow != cw and (ow, cw) not in examples:
                    examples.append((ow, cw))
                if len(examples) >= 3:
                    break
        c = t.count(pattern_ii)
        count += c
        _write(fp, t.replace(pattern_ii, replacement_ii).replace(F844, ""))
    for ow, cw in examples[:3]:
        log(f"  ex: {ow} -> {cw}")
    log(f"  -> {count} occurrences")
    stats[label] = count
    log()

    # ── 2c. Long vowel uu: U+23D3 -> u-macron  (128 occ) ──
    # Also removes orphan U+F844 that accompanies U+23D3.
    label = "Long vowel uu (U+23D3 -> u-macron)"
    log(label + " ...")
    pattern_uu = "\u23d3"
    replacement_uu = "\u016b"
    count = 0
    examples = []
    for fp in files:
        t = _read(fp)
        if pattern_uu not in t:
            continue
        if len(examples) < 3:
            for m in re.finditer(
                r'[^\s\[\](),.;:\-]*' + re.escape(pattern_uu) + r'[^\s\[\](),.;:\-]*', t
            ):
                ow = m.group(0)
                cw = ow.replace(pattern_uu, replacement_uu).replace(F844, "")
                if ow != cw and (ow, cw) not in examples:
                    examples.append((ow, cw))
                if len(examples) >= 3:
                    break
        c = t.count(pattern_uu)
        count += c
        _write(fp, t.replace(pattern_uu, replacement_uu).replace(F844, ""))
    for ow, cw in examples[:3]:
        log(f"  ex: {ow} -> {cw}")
    log(f"  -> {count} occurrences")
    stats[label] = count
    log()

    # ── 2d. Retroflex d: ss+U+F812+o-umlaut -> d-underdot  (106 occ) ──
    label = "Retroflex d (ss+U+F812+o-umlaut -> d-underdot)"
    log(label + " ...")
    pattern_d = "\u00df\uf812\u00f6"
    replacement_d = "\u1e0d"
    count = 0
    examples = []
    for fp in files:
        t = _read(fp)
        if pattern_d not in t:
            continue
        if len(examples) < 3:
            for m in re.finditer(
                r'[^\s\[\](),.;:\-]*' + re.escape(pattern_d) + r'[^\s\[\](),.;:\-]*', t
            ):
                ow = m.group(0)
                cw = ow.replace(pattern_d, replacement_d)
                if ow != cw and (ow, cw) not in examples:
                    examples.append((ow, cw))
                if len(examples) >= 3:
                    break
        c = t.count(pattern_d)
        count += c
        _write(fp, t.replace(pattern_d, replacement_d))
    for ow, cw in examples[:3]:
        log(f"  ex: {ow} -> {cw}")
    log(f"  -> {count} occurrences")
    stats[label] = count
    log()

    # ── 2f. Apparatus abbreviations: ss+ee+e-acute -> .M / ss+ee+a-acute -> .m ──
    label = "Apparatus abbreviations (ss+ee+e-acute -> .M, ss+ee+a-acute -> .m)"
    log(label + " ...")
    seq_M = "\u00df\u0113\u00e9"
    seq_m = "\u00df\u0113\u00e1"
    count_M = 0
    count_m = 0
    examples = []
    for fp in files:
        t = _read(fp)
        c1 = t.count(seq_M)
        c2 = t.count(seq_m)
        if not (c1 or c2):
            continue
        if len(examples) < 4:
            for m in re.finditer(
                r'[^\s\[\](),.;:\-]*' + re.escape(seq_M) + r'[^\s\[\](),.;:\-]*', t
            ):
                ow = m.group(0)
                cw = ow.replace(seq_M, ".M")
                if ow != cw and (ow, cw) not in examples:
                    examples.append((ow, cw))
                if len(examples) >= 4:
                    break
        if len(examples) < 4:
            for m in re.finditer(
                r'[^\s\[\](),.;:\-]*' + re.escape(seq_m) + r'[^\s\[\](),.;:\-]*', t
            ):
                ow = m.group(0)
                cw = ow.replace(seq_m, ".m")
                if ow != cw and (ow, cw) not in examples:
                    examples.append((ow, cw))
                if len(examples) >= 4:
                    break
        count_M += c1
        count_m += c2
        t = t.replace(seq_M, ".M").replace(seq_m, ".m")
        _write(fp, t)
    for ow, cw in examples:
        log(f"  ex: {ow} -> {cw}")
    log(f"  -> {count_M + count_m} occurrences ({count_M} .M + {count_m} .m)")
    stats[label] = count_M + count_m
    log()

    # ── 2g. Residual edge cases (~25 occ) ──
    label = "Residual edge cases"
    log(label + " ...")
    edge_fixes = [
        ("\u00df\uf812\u00f1", "\u00f1", "ss+U+F812+n-tilde -> n-tilde"),
        ("\u00df\u0113\uf83ca", "a", "ss+ee+U+F83C+a -> a"),
        ("\u00df\u0113\uf83c\u012b", "\u012b", "ss+ee+U+F83C+i-macron -> i-macron"),
        ("\u00df\u0113\u00e2", "", "ss+ee+a-circumflex -> (remove)"),
    ]
    total_edge = 0
    for pat, repl, desc in edge_fixes:
        subcount = 0
        for fp in files:
            t = _read(fp)
            c = t.count(pat)
            if c:
                subcount += c
                _write(fp, t.replace(pat, repl))
        if subcount:
            log(f"  {desc}: {subcount}")
        total_edge += subcount
    log(f"  -> {total_edge} residual cases")
    stats[label] = total_edge
    log()

    # ── 2h. Transliterated HTML husk stripping (added 2026-07-16) ──
    # 153 lines in three commentary files carry HTML markup from the rip,
    # transliterated as "<" -> "%" and ">" -> "@":
    #   [%a name="N"@%/a@ ]%span style="background-color:#0403cc;
    #    color:#f0f0ff"@$  followed by a normal Pali body line "[N] ..."
    # The husk (anchor pair, span tag, "$") is removed; the Pali payload
    # is untouched.  Only these exact byte patterns are removed — the
    # lone damage "@" in 54-Sammohavinodani.txt:2340 (truncated word,
    # lost content) is wontfix and must survive.
    label = "HTML husk stripping"
    log(label + " ...")
    html_rules = [
        (re.compile(r'%a name="\d+"@%/a@[ \t]*'), "anchor pair"),
        (re.compile(r'%span style="background-color:#0403cc; '
                    r'color:#f0f0ff"@\$'), "span tag + $"),
    ]
    total_html = 0
    for rx, desc in html_rules:
        subcount = 0
        for fp in files:
            t = _read(fp)
            new, c = rx.subn('', t)
            if c:
                subcount += c
                _write(fp, new)
        if subcount:
            log(f"  {desc}: {subcount}")
        total_html += subcount
    log(f"  -> {total_html} tags removed")
    stats[label] = total_html
    log()

    # ── (no orphan-PUA sweep) ──
    # Any PUA code point not consumed by the fixes above lives on the
    # unrecoverable garbled annotation lines (wontfix) and is deliberately
    # preserved, matching the hand-corrected reference corpus.

    log(f"T2 complete: {total_files} files processed")
    return stats


# ═══════════════════════════════════════════════════════════════════════════════
# Stage 3 — T4 structural normalizations (critical apparatus format)
# ═══════════════════════════════════════════════════════════════════════════════

def stage3_t4_normalizations() -> dict:
    """Apply all 4 T4 structural normalizations."""
    step_header(3, "T4 structural normalizations (critical apparatus)")

    stats: dict[str, int] = {}
    files = _all_output_files()

    def _read(path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def _write(path: Path, text: str) -> None:
        path.write_text(text, encoding="utf-8")

    # ── 3a. Normalize footnote calls: [N]- -> N-  (2,517 occ) ──
    label = "Footnote calls ([N]- -> N-)"
    log(label + " ...")
    # [ \t] and not \s: a match must never cross a line break
    call_re = re.compile(r'\[(\d+)\][ \t]*-')
    total_calls = 0
    files_hit = 0
    examples: list[tuple[str, str]] = []
    for fp in files:
        t = _read(fp)
        matches = list(call_re.finditer(t))
        if not matches:
            continue
        c = len(matches)
        if len(examples) < 4:
            for m in matches:
                ow = m.group(0).strip()
                cw = m.group(1) + "-"
                if ow != cw and (ow, cw) not in examples:
                    examples.append((ow, cw))
                if len(examples) >= 4:
                    break
        _write(fp, call_re.sub(r'\1-', t))
        total_calls += c
        files_hit += 1
    for ow, cw in examples:
        log(f"  ex: {ow} -> {cw}")
    log(f"  -> {total_calls} calls normalized in {files_hit} files")
    stats[label] = total_calls
    log()
    # ── 3a-bis. Bracketed footnote calls: [N-] -> N-  (4 occ) ──
    # Same family as 3a but with the dash inside the bracket; found by
    # the strict parser in 63-Paramatthamanjusa-3 (all 4 verified to
    # have their matching note on the same page).
    label = "Bracketed calls ([N-] -> N-)"
    call_br_re = re.compile(r'\[(\d+)-\]')
    n_bis = 0
    for fp in files:
        t = _read(fp)
        new, c = call_br_re.subn(r'\1-', t)
        if c:
            n_bis += c
            _write(fp, new)
    log(f"  [N-] -> N-: {n_bis}")
    stats[label] = n_bis
    log()

    # ── 3b. Critical apparatus punctuation ──
    label = "Apparatus punctuation"
    log(label + " ...")
    # [ \t] and not \s: \s matches newlines, and a match crossing a line
    # break would merge two lines (the numeral "cha" at end of line in
    # 43-Patthana-4 must not pair with the dot of ".pe." on the next line)
    sigla_comma_re = re.compile(r'\b(ma|cha|ka|po|rā|syā|sī|yu)[ \t]*,')
    sigla_space_dot_re = re.compile(r'\b(ma|cha|ka|po|rā|syā|sī|yu)[ \t]+\.')
    pe_re = re.compile(r'\.[ \t]+pe[ \t]+\.')
    punct_files = 0
    examples = []
    for fp in files:
        t = _read(fp)
        new = sigla_comma_re.sub(r'\1.', t)
        new = sigla_space_dot_re.sub(r'\1.', new)
        new = pe_re.sub('.pe.', new)
        if new == t:
            continue
        if not examples:
            for m in sigla_comma_re.finditer(t):
                examples.append((m.group(0).strip(), m.group(1) + "."))
                break
            for m in pe_re.finditer(t):
                examples.append((m.group(0).strip(), ".pe."))
                break
        _write(fp, new)
        punct_files += 1
    for ow, cw in examples:
        log(f"  ex: <{ow}> -> <{cw}>")
    log(f"  -> {punct_files} files corrected")
    stats[label] = punct_files
    log()
    # ── 3d. Additional punctuation normalizations (added 2026-07-16) ──
    # Unambiguous punctuation-only fixes beyond the original catalog,
    # derived from a full-corpus census.  None touches a Pali letter
    # (verified: the letters-only projection of every file is identical
    # before and after).  Horizontal whitespace only, never \s.
    label = "Additional punctuation (3d)"
    log(label + " ...")
    d_rules = [
        (re.compile(r'\.[ \t]+pe\.'), '.pe.', '". pe." -> ".pe."'),
        (re.compile(r'\.pe,\.'), '.pe.', '".pe,." -> ".pe."'),
        (re.compile(r'\u0101[ \t]+([;:])'), '\u0101\\1', 'letter + space + ;/:'),
        (re.compile(r'"[ \t]+,'), '",', 'quote + space + comma'),
        (re.compile(r'(\d-)[ \t]+,'), '\\1,', 'call N- + space + comma'),
        (re.compile(r'\([ \t]+'), '(', 'space after ('),
        (re.compile(r'[ \t]+\)'), ')', 'space before )'),
    ]
    total_d = 0
    for rx, repl, desc in d_rules:
        subcount = 0
        for fp in files:
            t = _read(fp)
            new, c = rx.subn(repl, t)
            if c:
                subcount += c
                _write(fp, new)
        if subcount:
            log(f"  {desc}: {subcount}")
        total_d += subcount
    log(f"  -> {total_d} punctuation fixes")
    stats[label] = total_d
    log()
    # ── 3e. T3 point corrections (human-approved, 2026-07-16) ──
    # Unclosed parenthetical in cross-reference note 2 of
    # 33-Paramatthadipani-6 p.244 (line 6599): "(khu.ṇetti. 10/197,
    # khu.milinda. 11/33 (cha.Ma." wraps two extra-canonical citations
    # (Netti and Milindapañha are absent from the Siamese 45-vol canon;
    # coordinates are per the Burmese editions, hence "(cha.Ma.)") and
    # lacks its closing paren.  Closing it at end of note approved by
    # the maintainer.  The $ anchor makes the rule idempotent.
    label = "T3 point corrections"
    log(label + " ...")
    t3_re = re.compile(
        r'(khuṇetti\. 10/197, khu\.milinda\. 11/33 \(cha\.Ma\.\))$',
        re.M)
    total_t3 = 0
    for fp in files:
        t = _read(fp)
        new, c = t3_re.subn(r'\1)', t)
        if c:
            total_t3 += c
            _write(fp, new)
    log(f"  close cross-ref parenthetical (33-Paramatthadipani-6): {total_t3}")
    stats[label] = total_t3
    log()

    # ── 3c. Restore missing footnote: prefix on spilled lines (1,362 lines) ──
    label = "Missing footnote: prefixes"
    log(label + " ...")
    total_spilled = 0
    files_hit = 0
    examples = []
    for fp in files:
        lines = _read(fp).splitlines()
        in_fn = False
        changed = False
        file_spilled = 0
        for i in range(len(lines)):
            s = lines[i].strip()
            if re.match(r'page number:\s*\d+', s, re.IGNORECASE):
                in_fn = False
                continue
            if s.startswith("footnote:"):
                in_fn = True
                continue
            if in_fn and s:
                # "i." = PTS English edition sigla (commentaries only).
                # Never add "i" to the 3b comma rule: it would match the
                # roman numeral in PTS refs like "(pts. vin i, 1)".
                is_app = bool(re.search(r'\b(ma|cha|ka|po|rā|syā|sī|yu|i)\.', s))
                is_note = bool(
                    re.match(r'^\d+(-\d+)*\s', s)
                    and not re.match(r'^\d+\s*/\s*\d', s)
                )
                if is_app or is_note:
                    leading = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
                    lines[i] = leading + "footnote: " + s
                    if len(examples) < 4:
                        examples.append((s[:60], "footnote: " + s[:60]))
                    file_spilled += 1
                    total_spilled += 1
                    changed = True
        if changed:
            _write(fp, "\n".join(lines) + "\n")
            files_hit += 1
    for ow, cw in examples:
        log(f"  ex: <{ow}> -> <{cw}>")
    log(f"  -> {total_spilled} lines prefixed in {files_hit} files")
    stats[label] = total_spilled
    log()

    log("T4 complete.")
    return stats


# ═══════════════════════════════════════════════════════════════════════════════
# Stage 4 — Structural validation (atleta_anciano)
# ═══════════════════════════════════════════════════════════════════════════════

class Page:
    """Represents a corpus page with its body text and footnotes."""

    def __init__(self, file_name: str, page_num: int, start_line: int):
        self.file = file_name
        self.num = page_num
        self.start_line = start_line
        self.body_calls: set[int] = set()
        self.footnote_notes: set[int] = set()

    def add_body_line(self, line: str, lineno: int) -> None:
        """Record a body line, detecting N- footnote calls.

        "N-" is not a call when the hyphen is followed by digits+dot:
        that is the Patimokkha dual rule numbering ("[30] 11-1. yo
        pana ..." in 70-Patimokkhapali).  Ranged calls ("1-2-") end in
        a hyphen, so the lookahead keeps them."""
        for m in re.finditer(r'(?:^|\s)(\d+)\s*-\s*(?!\d+\.)', line):
            self.body_calls.add(int(m.group(1)))
        for m in re.finditer(r'\[(\d+)\]\s*-\s*', line):
            print(
                f"  WARNING: {self.file}:{lineno} pg {self.num}: "
                f"residual [N]- call: [{m.group(1)}]-",
                file=sys.stderr,
            )

    def add_footnote_line(self, content: str) -> None:
        """Record an apparatus line, extracting note numbers.

        Two note-number styles coexist in the edition: bare ("1 ma.
        vuddhe."), dominant in Canonical, and dotted ("1. vi. cul.
        7/379.", "1-2. ma. ..."), the standard in the commentaries'
        apparatus.  Dotted numbers are capped at 2 digits so citation
        numerals ("384.") are not mistaken for notes."""
        if not content:
            return
        for m in re.finditer(r'(?:^|\s)(\d+)\s(?!\d*/\d)', content):
            pos = m.start()
            before = content[pos - 1:pos] if pos > 0 else ' '
            after = content[m.end():m.end() + 1] if m.end() < len(content) else ' '
            if before != '-' and after != '-':
                self.footnote_notes.add(int(m.group(1)))
        for m in re.finditer(r'(?:^|\s)(\d+)\s*-\s*(\d+)\s', content):
            for n in range(int(m.group(1)), int(m.group(2)) + 1):
                self.footnote_notes.add(n)
        for m in re.finditer(r'(?:^|\s)(\d+)\s*-\s*(\d+)\s*-\s*(\d+)', content):
            for n in range(int(m.group(1)), int(m.group(3)) + 1):
                self.footnote_notes.add(n)
        for m in re.finditer(r'(?:^|(?<=\s))(\d{1,2})\.(?=\s|$)', content):
            self.footnote_notes.add(int(m.group(1)))
        for m in re.finditer(
                r'(?:^|(?<=\s))(\d{1,2})-(\d{1,2})(?:-(\d{1,2}))?\.(?=\s|$)',
                content):
            last = m.group(3) or m.group(2)
            for n in range(int(m.group(1)), int(last) + 1):
                self.footnote_notes.add(n)

    def validate(self, known_errors: set[str]) -> list[str]:
        """Validate structural invariants. Returns list of errors."""
        errors: list[str] = []
        for call in sorted(self.body_calls):
            if call not in self.footnote_notes:
                key = f"{self.file} page {self.num}: orphan call {call}-"
                if key not in known_errors:
                    errors.append(key)
        if self.num <= 0:
            errors.append(
                f"{self.file}:{self.start_line}: invalid page number {self.num}"
            )
        return errors


def parse_file(filepath: Path, known_errors: set[str]) -> list[Page]:
    """Parse a .txt file into pages. Reports errors if any."""
    text = filepath.read_text(encoding="utf-8")
    lines = text.splitlines()
    pages: list[Page] = []
    current_page: Page | None = None
    in_footnote = False
    seen_page_numbers: set[int] = set()
    errors: list[str] = []

    for i, line in enumerate(lines):
        lineno = i + 1
        s = line.strip()

        if s.startswith('\ufeff'):
            s = s[1:].strip()
            if not s:
                continue

        pm = re.match(r'^page number:\s*(\d+)$', s, re.IGNORECASE)
        if pm:
            page_num = int(pm.group(1))
            if current_page is not None:
                errs = current_page.validate(known_errors)
                if errs:
                    errors.extend(errs)
                pages.append(current_page)
            if page_num in seen_page_numbers:
                errors.append(
                    f"{filepath.name}:{lineno}: duplicate page number {page_num}"
                )
            seen_page_numbers.add(page_num)
            prev_blank = (i == 0) or (
                lines[i - 1].strip().replace('\ufeff', '') == ''
            )
            if not prev_blank:
                errors.append(
                    f"{filepath.name}:{lineno}: page {page_num} "
                    f"not preceded by blank line"
                )
            current_page = Page(filepath.name, page_num, lineno)
            in_footnote = False
            continue

        if current_page is None:
            continue

        if s.startswith("footnote:"):
            in_footnote = True
            current_page.add_footnote_line(s[9:].strip())
            continue

        if in_footnote and s:
            has_sigla = bool(re.search(r'\b(ma|cha|ka|po|rā|syā|sī|yu|i)\.', s))
            has_note_digit = bool(
                re.match(r'^\d+(-\d+)*\s', s)
                and not re.match(r'^\d+\s*/\s*\d', s)
            )
            if has_sigla or has_note_digit:
                errors.append(
                    f"{filepath.name}:{lineno} pg {current_page.num}: "
                    f"apparatus content without footnote: prefix — "
                    f"<{s[:80]}>"
                )
            in_footnote = False
            current_page.add_body_line(s, lineno)
            continue

        in_footnote = False
        current_page.add_body_line(s, lineno)

    if current_page is not None:
        errs = current_page.validate(known_errors)
        if errs:
            errors.extend(errs)
        pages.append(current_page)

    if errors:
        for e in errors:
            print(f"  ERROR: {e}", file=sys.stderr)
        die(f"{len(errors)} structural error(s) in {filepath.name}")

    return pages


def stage4_validate(
    canonical_only: bool = False, non_canonical_only: bool = False
) -> int:
    """Validate the structure of processed files. Both corpora by default."""
    step_header(4, "Structural validation (atleta_anciano)")

    log("Zero-tolerance parser active.")
    log(f"Known errors loaded: {len(KNOWN_ERRORS)} (will be skipped).")
    log()

    total_pages = 0
    for section, dir_path in [
        ("Canonical", CANON_DIR),
        ("Non-Canonical", NONCANON_DIR),
    ]:
        if canonical_only and section != "Canonical":
            continue
        if non_canonical_only and section != "Non-Canonical":
            continue
        txt_files = sorted(dir_path.glob("*.txt"))
        if not txt_files:
            log(f"{section}: no .txt files — skipped.")
            continue
        section_pages = 0
        total_calls = 0
        total_notes = 0
        total_orphans = 0
        for fp in txt_files:
            pages = parse_file(fp, KNOWN_ERRORS)
            section_pages += len(pages)
            for page in pages:
                total_calls += len(page.body_calls)
                total_notes += len(page.footnote_notes)
                for note in sorted(page.footnote_notes):
                    if note not in page.body_calls:
                        key = f"{page.file} page {page.num}: orphan call {note}-"
                        if key not in KNOWN_ERRORS:
                            total_orphans += 1
        log(f"{section}: {len(txt_files)} files, {section_pages} pages")
        log(f"  Body calls:         {total_calls}")
        log(f"  Footnote notes:     {total_notes}")
        log(f"  Orphans:            0 (all caught)")
        log(f"  Ghosts:             {total_orphans} (notes without calls)")
        total_pages += section_pages

    log()
    log(f"Total pages validated: {total_pages}")
    log("STRUCTURAL VALIDATION COMPLETE — no errors.")
    return total_pages


# ═══════════════════════════════════════════════════════════════════════════════
# Stage 5 — Reference edition verification (conan)
# ═══════════════════════════════════════════════════════════════════════════════

def stage5_verify() -> bool:
    """Compare processed corpus against Royal Thai reference edition."""
    step_header(5, "Reference verification (conan)")

    ref_dir = Path(BUDSIR_REF_DIR)
    if not ref_dir.is_dir():
        log(f"Reference edition not found: {ref_dir}")
        log("Set BUDSIR_REF_DIR or install the Thai edition to verify.")
        log("Skipping verification.")
        return False

    log(f"Reference: {ref_dir}")
    log()

    changed = git(
        "diff", "--name-only", ORIGINAL_COMMIT, "HEAD", "--",
        f"{CORPUS_SRC}/Canonical/",
    )
    changed_files = [f.strip() for f in changed.splitlines() if f.strip()]
    if not changed_files:
        log("No changes in canonical files — nothing to verify.")
        return True

    stats = {"files": 0, "lines": 0, "words": 0, "verified": 0, "unverified": 0}
    for fp in sorted(changed_files):
        vm = re.match(r'txt/Canonical/(\d+)', fp)
        if not vm:
            continue
        vol = int(vm.group(1))
        ref_path = ref_dir / f"Book {vol}.txt"
        if not ref_path.exists():
            continue
        ref_text = ref_path.read_text(encoding="utf-8", errors="replace")
        orig_lines = git("show", f"{ORIGINAL_COMMIT}:{fp}").splitlines()
        curr_path = CANON_DIR / Path(fp).name
        curr_lines = curr_path.read_text(encoding="utf-8").splitlines()
        file_changed = False
        for i in range(max(len(orig_lines), len(curr_lines))):
            ol = orig_lines[i] if i < len(orig_lines) else ""
            cl = curr_lines[i] if i < len(curr_lines) else ""
            if ol == cl:
                continue
            file_changed = True
            stats["lines"] += 1
            for ow, cw in zip(
                ol.split(), cl.split()
            ):
                if ow == cw:
                    continue
                oc = re.sub(r'[\[\]().,;:\-]', '', ow)
                cc = re.sub(r'[\[\]().,;:\-]', '', cw)
                if oc == cc:
                    continue
                stats["words"] += 1
                clean = cw.strip('[]().,;:').rstrip('.')
                if len(clean) < 2:
                    continue
                if clean in ref_text:
                    stats["verified"] += 1
                else:
                    stats["unverified"] += 1
        if file_changed:
            stats["files"] += 1

    log(f"Files: {stats['files']}  Lines: {stats['lines']}  Words: {stats['words']}")
    log(f"Verified: {stats['verified']}  Unverified: {stats['unverified']}")
    total = stats["verified"] + stats["unverified"]
    rate = stats["verified"] / total * 100 if total > 0 else 100
    log(f"Convergence: {rate:.1f}%")
    return stats["unverified"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reproducible BUDSIR corpus processing pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 utils/process_corpus.py               # full pipeline
  python3 utils/process_corpus.py --stage 2     # T2 corrections only
  python3 utils/process_corpus.py --canonical   # canonical texts only
        """,
    )
    parser.add_argument(
        "--stage", type=int, choices=[1, 2, 3, 4, 5],
        help="Run only a specific stage (1-5).",
    )
    parser.add_argument(
        "--canonical", action="store_true",
        help="Process canonical texts only.",
    )
    parser.add_argument(
        "--non-canonical", action="store_true",
        help="Process non-canonical texts only.",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  BUDSIR Corpus — Reproducible Processing Pipeline")
    print(f"  Repo:      {REPO_ROOT}")
    print(f"  Base commit: {ORIGINAL_COMMIT}")
    print("=" * 60)

    single_stage = args.stage is not None

    if not single_stage or args.stage == 1:
        stage1_extract()
    elif not CANON_DIR.exists() and not NONCANON_DIR.exists():
        die("Output directories not found. Run stage 1 first.")

    if not single_stage or args.stage == 2:
        t2_stats = stage2_t2_corrections()
    else:
        t2_stats: dict[str, int] = {}

    if not single_stage or args.stage == 3:
        t4_stats = stage3_t4_normalizations()
    else:
        t4_stats: dict[str, int] = {}

    if not single_stage or args.stage == 4:
        total_pages = stage4_validate(
            canonical_only=args.canonical,
            non_canonical_only=args.non_canonical,
        )
    else:
        total_pages = 0

    if not single_stage or args.stage == 5:
        stage5_verify()

    print()
    print("=" * 60)
    print(f"  Pipeline complete  [{datetime.now().strftime('%H:%M:%S')}]")
    print("=" * 60)
    print(f"  Source commit:   {ORIGINAL_COMMIT}")
    if t2_stats:
        print(f"  T2 corrections:  {sum(t2_stats.values())} total occurrences")
    if t4_stats:
        print(f"  T4 normaliz.:    {sum(t4_stats.values())} total changes")
    if total_pages:
        print(f"  Pages validated: {total_pages}")
    print()


if __name__ == "__main__":
    main()

#!/usr/bin/env perl
#
# process_corpus.pl — BUDSIR corpus processing pipeline
# ======================================================
#
# Reproducible correction pipeline for the BUDSIR Tipitaka corpus.
#
# BUDSIR stores Pali text in the Fulbright romanised encoding (ASCII +
# modifier bytes 0x8A/0x8B/0x8C/0xE5 for overstrike diacritics, plus a
# second glyph bank for word-initial precomposed forms).  The encoding
# itself is correct; the corruption was introduced by the extraction
# tool ("ripper") whose byte→Unicode table covered only the medial
# glyph bank (99.87 % of text) and missed two categories:
#   - Word-initial precomposed forms (ī, ū, ṭh, ḍ at word start)
#   - Apparatus abbreviation sign (.M / .m)
#
# The missing slots produced three classes of corruption artifact:
#   1. Latin-1 passthrough — high bytes emitted as-is (ß=0xDF, é=0xE9)
#   2. PUA fallback        — bytes emitted as U+F800+byte
#   3. Partial table        — bytes with a wrong cmap entry (Ō=0x014C)
#
# Evidence: in genuine Pali text, every letter artefact (ṭh, ḍ, ī, ū)
# appears at word-initial position, matching the missing initial-form
# bank.  The apparatus sign .M/.m is word-medial by nature (it attaches
# after a witness sigla: sīßēé → sī.M), and the only medial letter
# artefacts occur inside the garbled "* mīkārkkhag …" annotation lines,
# which are unrecoverable (wontfix).
#
# What this script does:
#   Stage 1 — Extracts txt/ from git commit 07c937d ("ripped from
#             BUDSIR") → Canonical/ and Non-Canonical/
#   Stage 2 — T2 encoding corrections (ripper table artefacts, 2a-2g)
#             + transliterated-HTML husk stripping (2h)
#   Stage 3 — T4 structural normalizations (3a/3a-bis/3b/3c), census-
#             derived punctuation fixes (3d), human-approved T3 point
#             corrections (3e)
#
# CARDINAL RULE: the Pali word sequence is inviolable — only decoder
# damage and notation/markup are corrected.  utils/verify_pali.py
# proves word-sequence identity against the hand-corrected reference
# (115/115) after every change.  Full rationale, provenance chain and
# audit instructions: METHODOLOGY.md.  This script and its Python twin
# (process_corpus.py) must stay byte-identical in output.
#
# Each file is read ONCE, all corrections are applied, then written
# ONCE.  The pipeline processes raw UTF-8 bytes via Encode::decode /
# Encode::encode so that \x{…} escapes match codepoints directly.
#
# Usage:   perl utils/process_corpus.pl
#
# Reference documentation: docs/DOC.md and docs/DOCUMENTATION.md
# (local copies from the budsir_c project, not tracked in git) —
# corpus catalog, corruption taxonomy, and correction protocols.
# The authoritative reference for verifying corrections is the
# hand-corrected corpus of that project, not a hash comparison
# between pipeline implementations.
#

use strict;
use warnings;
use utf8;                                    # source is UTF-8 (Pali diacritics)
use FindBin         qw($RealBin);            # locate repo root from script path
use File::Path      qw(make_path remove_tree);
use File::Glob      qw(bsd_glob);            # BSD-style glob (deterministic)
use Encode          qw(encode decode);       # explicit UTF-8 round-trip
use List::Util      qw(sum);

binmode STDOUT, ':utf8';                     # print Pali characters correctly
binmode STDERR, ':utf8';

# ============================================================================
# Configuration
# ============================================================================

# Run from the repo root regardless of the caller's cwd (matches the
# Python reference, which resolves REPO_ROOT from its own path).
chdir "$RealBin/.." or die "chdir $RealBin/..: $!";

my $ORIGINAL_COMMIT = "07c937d";              # commit "ripped from BUDSIR"
my $CORPUS_SRC   = "txt";                     # corpus source in git
my $OUT_CANON    = "Canonical";               # output: corrected canonical
my $OUT_NONCANON = "Non-Canonical";           # output: corrected commentaries

# ============================================================================
# Helpers
# ============================================================================

# Return current time as HH:MM:SS (no Time::Piece dependency).
sub now {
    my @t = localtime;
    sprintf "%02d:%02d:%02d", $t[2], $t[1], $t[0];
}

# Emit a timestamped log line.  Pass undef for a blank line.
sub log_msg {
    my ($msg) = @_;
    print "  [" . now() . "] $msg\n" if defined $msg;
    print "\n" unless defined $msg;
}

# Print a pipeline stage header.
sub step {
    my ($num, $title) = @_;
    print "\n" . "=" x 60 . "\n";
    print " [$num/3] $title\n";
    print "=" x 60 . "\n";
}

# --- file I/O (raw bytes + explicit UTF-8 decode/encode) ---------------------
#
# We read and write raw bytes because the corpus contains PUA codepoints
# (U+F812, U+F83C, U+F844) that are valid UTF-8 but must be matched as
# byte sequences, not as Unicode characters with any Perl-imposed semantics.
# The decode/encode layer cleanly separates the byte level from the
# codepoint level, allowing \x{…} patterns to work correctly.

# Read a file as raw bytes, return a decoded Unicode string.
sub read_file {
    my ($path) = @_;
    open my $fh, '<:raw', $path or die "open $path: $!";
    local $/;                                # slurp entire file
    my $bytes = <$fh>;
    close $fh;
    return decode('UTF-8', $bytes);
}

# Encode a Unicode string as UTF-8 and write it as raw bytes.
sub write_file {
    my ($path, $text) = @_;
    open my $fh, '>:raw', $path or die "write $path: $!";
    print $fh encode('UTF-8', $text);
    close $fh;
}

# Run a git command and return its raw stdout bytes.  Dies on failure.
sub git_bytes {
    my (@args) = @_;
    open my $fh, '-|:raw', 'git', @args or die "git @args: $!";
    local $/;                                # slurp entire output
    my $out = <$fh>;
    close $fh;
    die "git @args: exit status $?" if $?;
    return defined $out ? $out : '';
}

# ============================================================================
# T2 Ripper-Table Corrections — pattern constants
# ============================================================================
#
# The ripper's incomplete byte→Unicode table produced artefacts following
# a consistent pattern:  0xDF (ß, a bank-escape byte in the Fulbright
# font) + corrupted vowel + PUA codepoint + …
#
# Each pattern below is expressed as a Perl \x{…} string so it matches
# the corresponding Unicode codepoint in the decoded text.

# U+F844 — accompanies Ō (U+014C) and ⏓ (U+23D3); removed in the same
# pass as the parent correction.  Any other PUA code point not consumed
# by a complete-sequence fix (U+F812, U+F814, U+F818, U+F81A, U+F830)
# sits on the unrecoverable garbled annotation lines (wontfix) and must
# be preserved — the hand-corrected reference corpus keeps them.
my $F844 = "\x{f844}";

# 2a — Retroflex th:  ß + ē + U+F83C + h  →  ṭh    (842 occurrences)
my $P_2a = "\x{00df}\x{0113}\x{f83c}h";     # corrupt: U+00DF U+0113 U+F83C h
my $R_2a = "\x{1e6d}h";                      # correct: U+1E6D h

# 2b — Long vowel ii:  Ō  →  ī                     (121 occurrences)
# The source also has a trailing U+F844 removed in the same pass.
my $P_2b = "\x{014c}";                       # corrupt: U+014C (O-macron)
my $R_2b = "\x{012b}";                       # correct: U+012B (i-macron)

# 2c — Long vowel uu:  ⏓  →  ū                     (128 occurrences)
# The source also has a trailing U+F844 removed in the same pass.
my $P_2c = "\x{23d3}";                       # corrupt: U+23D3 (meteorology symbol)
my $R_2c = "\x{016b}";                       # correct: U+016B (u-macron)

# 2d — Retroflex d:  ß + U+F812 + ö  →  ḍ          (106 occurrences)
my $P_2d = "\x{00df}\x{f812}\x{00f6}";       # corrupt: U+00DF U+F812 U+00F6
my $R_2d = "\x{1e0d}";                       # correct: U+1E0D (d-underdot)

# 2f — Apparatus abbreviations                        (23,555 occurrences)
# ß + ē + é → .M (Maramma manuscript sigla)
# ß + ē + á → .m (variant reading marker)
my $P_2f_M = "\x{00df}\x{0113}\x{00e9}";     # U+00DF U+0113 U+00E9 → .M
my $P_2f_m = "\x{00df}\x{0113}\x{00e1}";     # U+00DF U+0113 U+00E1 → .m

# 2g — Residual edge cases (~26 occurrences)
# These are incomplete corruption sequences left after the main patterns.
# The a / i-macron variants carry the same intra-sequence U+F83C as 2a.
my @T2_EDGES = (
    # U+00DF U+F812 U+00F1 → U+00F1   (ss + PUA + n-tilde → n-tilde)
    ["\x{00df}\x{f812}\x{00f1}", "\x{00f1}"],
    # U+00DF U+0113 U+F83C a → a      (ss + ee + PUA + a, in aṅkitamañca)
    ["\x{00df}\x{0113}\x{f83c}a", "a"],
    # U+00DF U+0113 U+F83C U+012B → U+012B  (ss + ee + PUA + i-macron)
    ["\x{00df}\x{0113}\x{f83c}\x{012b}", "\x{012b}"],
    # U+00DF U+0113 U+00E2 → ""      (ss + ee + a-circumflex → remove)
    ["\x{00df}\x{0113}\x{00e2}",  ""],
);

# ============================================================================
# Stage 1 — Extract original corpus from git
# ============================================================================
#
# Clears Canonical/ and Non-Canonical/, then extracts every .txt under
# txt/ as it exists in the pinned base commit ("ripped from BUDSIR").
# Extracting from git — not from the working tree — guarantees the
# pipeline is reproducible even if txt/ is later modified.

sub stage1_extract {
    step(1, "Extracting original corpus from git ($ORIGINAL_COMMIT)");

    # Clean output directories (abort on failure: stale files would
    # otherwise survive into the corrected output unnoticed)
    for my $dir ($OUT_CANON, $OUT_NONCANON) {
        remove_tree($dir, { keep_root => 0, error => \my $err });
        if ($err && @$err) {
            my ($file, $msg) = %{ $err->[0] };
            die "remove_tree $dir: $file: $msg";
        }
    }
    make_path($OUT_CANON, $OUT_NONCANON);

    # List the corpus files recorded in the base commit
    my $tree = decode('UTF-8',
        git_bytes('ls-tree', '-r', '--name-only',
                  $ORIGINAL_COMMIT, "$CORPUS_SRC/"));
    my @files = grep { /\.txt$/ } split /\n/, $tree;
    die "no .txt files under $CORPUS_SRC/ in $ORIGINAL_COMMIT" unless @files;

    # Extract each blob byte-for-byte into Canonical/ and Non-Canonical/
    my ($cfiles, $nfiles) = (0, 0);
    for my $f (sort @files) {
        (my $rel = $f) =~ s{^\Q$CORPUS_SRC\E/}{};   # Canonical/01-...txt
        my $bytes = git_bytes('show', "$ORIGINAL_COMMIT:$f");
        open my $out, '>:raw', $rel or die "write $rel: $!";
        print $out $bytes;
        close $out;
        $rel =~ m{^\Q$OUT_CANON\E/} ? $cfiles++ : $nfiles++;
    }

    log_msg("Extracted $cfiles canonical + $nfiles non-canonical files");
    log_msg();
    return ($cfiles, $nfiles);
}

# ============================================================================
# Stage 2 + 3 — Single-pass correction loop
# ============================================================================
#
# For each file, the T2 corrections are applied in strict order:
#   2a → 2b → 2c → 2d → 2f → 2g
#
# There is no orphan-PUA sweep: every PUA code point is either consumed
# by a complete-sequence fix or belongs to the unrecoverable garbled
# annotation lines (wontfix), which are deliberately preserved.
#
# After T2, T4 structural normalizations are applied on the same
# in-memory copy:
#   3a → 3b → 3c
#
# The file is written to disk only once, after all corrections.

sub process_corpus {
    step(2, "T2 ripper-table corrections + T4 structural normalizations");

    # Collect all output files
    my @canon_files = bsd_glob("$OUT_CANON/*.txt");
    my @noncan_files = bsd_glob("$OUT_NONCANON/*.txt");
    my @files = (@canon_files, @noncan_files);
    my $total_files = scalar(@files);

    # ---- per-correction counters (all initialized to 0) ----

    # T2: main fixes
    my ($c_2a, $c_2b, $c_2c, $c_2d)               = (0, 0, 0, 0);
    # T2: apparatus abbreviations
    my ($c_2f_M, $c_2f_m)                          = (0, 0);
    # T2: residual edge cases (per sub-pattern for auditability)
    my ($c_2g_fn, $c_2g_a, $c_2g_ii, $c_2g_acirc) = (0, 0, 0, 0);
    # T2: HTML husk removal
    my $c_2h = 0;
    # T4: normalizations
    my ($c_3a, $c_3b, $c_3c_lines, $c_3c_files)   = (0, 0, 0, 0);
    my ($c_3d, $c_3e) = (0, 0);

    # ---- main loop: one file at a time, all corrections in memory ----

    for my $f (@files) {
        my $t = read_file($f);               # decoded Unicode

        # -- T2: 2a — retroflex th --
        # Replace the 4-codepoint corruption with canonical t-underdot + h.
        my $n = () = $t =~ /\Q$P_2a\E/g;    # count occurrences (goatse operator)
        if ($n) { $c_2a += $n; $t =~ s/\Q$P_2a\E/$R_2a/g }

        # -- T2: 2b — long vowel ii --
        # O-macron → i-macron.  Also strips orphan U+F844 in the same pass
        # because the corruption sequence is always Ō + U+F844 in the source.
        $n = () = $t =~ /\Q$P_2b\E/g;
        if ($n) { $c_2b += $n; $t =~ s/\Q$P_2b\E/$R_2b/g; $t =~ s/\Q$F844\E//g }

        # -- T2: 2c — long vowel uu --
        # U+23D3 → u-macron.  Same orphan-F844 story as 2b.
        $n = () = $t =~ /\Q$P_2c\E/g;
        if ($n) { $c_2c += $n; $t =~ s/\Q$P_2c\E/$R_2c/g; $t =~ s/\Q$F844\E//g }

        # -- T2: 2d — retroflex d --
        $n = () = $t =~ /\Q$P_2d\E/g;
        if ($n) { $c_2d += $n; $t =~ s/\Q$P_2d\E/$R_2d/g }

        # -- T2: 2f — apparatus abbreviations --
        # The two sequences differ in their final codepoint (é U+00E9 vs
        # á U+00E1), so they never overlap and order is immaterial; .M is
        # applied first to mirror the Python reference implementation.
        my $nm = () = $t =~ /\Q$P_2f_M\E/g;
        if ($nm) { $c_2f_M += $nm; $t =~ s/\Q$P_2f_M\E/.M/g }
        my $nmm = () = $t =~ /\Q$P_2f_m\E/g;
        if ($nmm) { $c_2f_m += $nmm; $t =~ s/\Q$P_2f_m\E/.m/g }

        # -- T2: 2g — residual edge cases --
        # Each pattern is checked independently; multiple may match the
        # same file (they affect different positions in the text).
        for my $e (@T2_EDGES) {
            my ($pat, $repl) = @$e;
            my $sc = () = $t =~ /\Q$pat\E/g;
            if ($sc) {
                $t =~ s/\Q$pat\E/$repl/g;
                # Per-sub-pattern tracking for audit:
                if    ($pat eq "\x{00df}\x{f812}\x{00f1}")         { $c_2g_fn    += $sc }
                elsif ($pat eq "\x{00df}\x{0113}\x{f83c}a")        { $c_2g_a     += $sc }
                elsif ($pat eq "\x{00df}\x{0113}\x{f83c}\x{012b}") { $c_2g_ii    += $sc }
                elsif ($pat eq "\x{00df}\x{0113}\x{00e2}")         { $c_2g_acirc += $sc }
            }
        }

        # -- T2: 2h — transliterated HTML husk stripping (2026-07-16) --
        # "<" -> "%", ">" -> "@": [%a name="N"@%/a@ ]%span style="..."@$
        # precedes a normal Pali body line in 153 lines of three
        # commentary files.  Only these exact patterns are removed; the
        # lone damage "@" (54-Sammohavinodani.txt:2340) must survive.
        $c_2h += ($t =~ s/%a name="\d+"\@%\/a\@[ \t]*//g) || 0;
        $c_2h += ($t =~ s/%span style="background-color:#0403cc; color:#f0f0ff"\@\$//g) || 0;

        # (no orphan-PUA sweep: leftover PUA code points belong to the
        # garbled wontfix annotation lines and are preserved verbatim)

        # -- T4: 3a — footnote call markers --
        # Normalize "[N]-" → "N-" in body text.  The regex requires a
        # trailing dash; plain "[N]" passage markers (58,926 of them)
        # are deliberately excluded.  [ \t] and not \s: a match must
        # never cross a line break.
        my @matches_3a = $t =~ /\[(\d+)\][ \t]*-/g;
        if (@matches_3a) {
            my $sc = scalar(@matches_3a);
            $c_3a += $sc;
            $t =~ s/\[(\d+)\][ \t]*-/$1-/g;
        }
        # 3a-bis: dash inside the bracket ([N-] -> N-); 4 occ verified
        # against their pages' notes in 63-Paramatthamanjusa-3.
        $c_3a += ($t =~ s/\[(\d+)-\]/$1-/g) || 0;

        # -- T4: 3b — apparatus punctuation --
        # Three rules applied to footnote apparatus lines:
        #   sigla,  → sigla.   (comma → dot after witness abbreviation)
        #   sigla . → sigla.   (remove space before dot)
        #   . pe .  → .pe.     (spaced elision → standard form)
        # The \b word-boundary prevents false matches inside words (e.g.
        # "kata," should not match "ka,").  [ \t] and not \s: \s matches
        # newlines, and a match crossing a line break would merge two
        # lines (the numeral "cha" at end of line in 43-Patthana-4 must
        # not pair with the dot of ".pe." on the next line).
        my $before_3b = $t;
        $t =~ s/\b(ma|cha|ka|po|rā|syā|sī|yu)[ \t]*,/$1./g;
        $t =~ s/\b(ma|cha|ka|po|rā|syā|sī|yu)[ \t]+\./$1./g;
        $t =~ s/\.[ \t]+pe[ \t]+\./.pe./g;
        if ($t ne $before_3b) {
            $c_3b++;
        }

        # -- T4: 3d — additional punctuation normalizations (2026-07-16) --
        # Unambiguous punctuation-only fixes beyond the original catalog,
        # derived from a full-corpus census.  None touches a Pali letter
        # (verified: the letters-only projection of every file is
        # identical before and after).  Horizontal whitespace only.
        $c_3d += ($t =~ s/\.[ \t]+pe\./.pe./g)        || 0;  # ". pe." -> ".pe."
        $c_3d += ($t =~ s/\.pe,\./.pe./g)             || 0;  # ".pe,." -> ".pe."
        $c_3d += ($t =~ s/\x{101}[ \t]+([;:])/\x{101}$1/g) || 0;  # "ā :" -> "ā:"
        $c_3d += ($t =~ s/"[ \t]+,/",/g)              || 0;  # '" ,' -> '",'
        $c_3d += ($t =~ s/(\d-)[ \t]+,/$1,/g)         || 0;  # "N- ," -> "N-,"
        $c_3d += ($t =~ s/\([ \t]+/(/g)               || 0;  # "( x" -> "(x"
        $c_3d += ($t =~ s/[ \t]+\)/)/g)               || 0;  # "x )" -> "x)"

        # -- T4: 3e — T3 point corrections (human-approved, 2026-07-16) --
        # Unclosed parenthetical in a cross-reference note of
        # 33-Paramatthadipani-6 p.244: "(khu.ṇetti…, khu.milinda…
        # (cha.Ma." wraps two extra-canonical citations (Netti and
        # Milindapañha are absent from the Siamese canon) and lacks its
        # closing paren.  The $ anchor (with /m) makes it idempotent.
        $c_3e += ($t =~ s/(khuṇetti\. 10\/197, khu\.milinda\. 11\/33 \(cha\.Ma\.\))$/$1)/m) || 0;

        # -- T4: 3c — restore missing "footnote:" prefix --
        #
        # In the BUDSIR corpus, apparatus content is supposed to appear
        # on lines starting with "footnote:".  However, some apparatus
        # lines "spilled" without the prefix — they appear between a
        # "footnote:" line and the next "page number:" marker, but lack
        # the prefix themselves.
        #
        # We detect these by tracking state ($in_fn): once we see a
        # "footnote:" line, subsequent lines are candidates.  A candidate
        # receives the prefix if it contains witness siglas (ma. cha. ka.
        # po. rā. syā. sī. yu.) or starts with a note digit (but NOT a
        # date-like "N/M" pattern, which is body text).
        #
        # \r?\n handles Windows-style CRLF line endings safely.
        my @lines = split /\r?\n/, $t, -1;   # -1 preserves trailing empties
        my ($in_fn, $changed, $file_spilled) = (0, 0, 0);

        for my $i (0 .. $#lines) {
            my $s = $lines[$i];
            # Strip both leading and trailing whitespace (matches Python's
            # str.strip() behavior, which the reference pipeline uses).
            my $s_trim = $s;
            $s_trim =~ s/^\s+|\s+$//g;

            # "page number:" resets the footnote context
            if ($s_trim =~ /^page number:\s*\d+/i) {
                $in_fn = 0;
                next;
            }

            # Enter footnote context
            if ($s_trim =~ /^footnote:/) {
                $in_fn = 1;
                next;
            }

            # Only act on non-empty lines inside a footnote block
            next unless $in_fn && $s_trim;

            # Identify apparatus content by two heuristics:
            #   1. Contains a witness sigla abbreviation (ma. cha. etc.)
            #   2. Starts with a note number (e.g. "7 muggarappahāreti…")
            #      but is NOT a date-like fraction (e.g. "7/8")
            # "i." = PTS English edition sigla (commentaries only).
            # Never add "i" to the 3b comma rule: it would match the
            # roman numeral in PTS refs like "(pts. vin i, 1)".
            my $has_sigla = $s_trim =~ /\b(ma|cha|ka|po|rā|syā|sī|yu|i)\./;
            my $is_note   = $s_trim =~ /^\d+(-\d+)*\s/
                         && $s_trim !~ /^\d+\s*\/\s*\d/;

            if ($has_sigla || $is_note) {
                # Preserve original indentation
                my ($leading) = $lines[$i] =~ /^(\s*)/;
                $lines[$i] = $leading . "footnote: " . $s_trim;
                $file_spilled++;
                $c_3c_lines++;
                $changed = 1;
            }
        }

        # Only join and overwrite if this file had spilled apparatus
        if ($changed) {
            $t = join("\n", @lines);
            $c_3c_files++;
        }

        # ---- write the fully-corrected file to disk ----
        write_file($f, $t);
    }

    # ---- audit report: per-correction statistics ----

    log_msg("T2 encoding corrections:");
    log_msg("  2a. Retroflex th:             $c_2a occurrences");
    log_msg("  2b. Long vowel ii:            $c_2b occurrences");
    log_msg("  2c. Long vowel uu:            $c_2c occurrences");
    log_msg("  2d. Retroflex d:              $c_2d occurrences");
    log_msg("  2f. Apparatus abbrev .M:      $c_2f_M occurrences");
    log_msg("  2f. Apparatus abbrev .m:      $c_2f_m occurrences");
    log_msg("  2g. Residual ss+n-tilde:      $c_2g_fn occurrences");
    log_msg("  2g. Residual ss+a:            $c_2g_a occurrences");
    log_msg("  2g. Residual ss+ii:           $c_2g_ii occurrences");
    log_msg("  2g. Residual ss+acircum:      $c_2g_acirc occurrences");
    log_msg("  2h. HTML husk removed:        $c_2h tags");
    log_msg();
    log_msg("T4 structural normalizations:");
    log_msg("  3a. Footnote calls:           $c_3a occurrences");
    log_msg("  3b. Apparatus punctuation:    $c_3b files");
    log_msg("  3c. Spilled footnote: prefixes: $c_3c_lines lines in $c_3c_files files");
    log_msg("  3d. Additional punctuation:   $c_3d occurrences");
    log_msg("  3e. T3 point corrections:     $c_3e occurrences");
    log_msg();
    log_msg("Processed $total_files files (single-pass I/O).");

    return {
        t2_total => $c_2a + $c_2b + $c_2c + $c_2d + $c_2f_M + $c_2f_m
                  + $c_2g_fn + $c_2g_a + $c_2g_ii + $c_2g_acirc + $c_2h,
        # Sum matches the Python twin's summary: occurrence/line counts
        # only ($c_3c_files would double-count the 3c work).
        t4_total => $c_3a + $c_3b + $c_3c_lines + $c_3d + $c_3e,
    };
}

# ============================================================================
# Entry point
# ============================================================================

print "=" x 60 . "\n";
print "  BUDSIR Corpus — Processing Pipeline (Perl)\n";
print "=" x 60 . "\n";

stage1_extract();
my $stats = process_corpus();

print "\n" . "=" x 60 . "\n";
print "  Pipeline complete  [" . now() . "]\n";
print "=" x 60 . "\n\n";
print "  T2 corrections:  $stats->{t2_total} total occurrences\n";
print "  T4 normaliz.:    $stats->{t4_total} total changes\n";
print "=" x 60 . "\n";

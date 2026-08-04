"""
CodePhoenix — Intake Scanner

Recursively walks a directory tree, fingerprints each file's language
using extension + content heuristics, and produces a ProjectManifest.
"""

from __future__ import annotations
from pathlib import Path
import re
import time

from codephoenix.models import (
    LegacyLanguage,
    SourceFile,
    ProjectManifest,
)


# ─────────────────────────────────────────────
#  Extension-Based Detection
# ─────────────────────────────────────────────

EXTENSION_MAP: dict[str, LegacyLanguage] = {
    # COBOL
    ".cob": LegacyLanguage.COBOL,
    ".cbl": LegacyLanguage.COBOL,
    ".cobol": LegacyLanguage.COBOL,
    ".cpy": LegacyLanguage.COBOL,  # Copybooks
    ".ccp": LegacyLanguage.COBOL,
    # Fortran
    ".f": LegacyLanguage.FORTRAN,
    ".for": LegacyLanguage.FORTRAN,
    ".ftn": LegacyLanguage.FORTRAN,
    ".f77": LegacyLanguage.FORTRAN,
    ".f90": LegacyLanguage.FORTRAN,
    ".f95": LegacyLanguage.FORTRAN,
    ".f03": LegacyLanguage.FORTRAN,
    ".f08": LegacyLanguage.FORTRAN,
    # Pascal
    ".pas": LegacyLanguage.PASCAL,
    ".pp": LegacyLanguage.PASCAL,
    ".p": LegacyLanguage.PASCAL,
    ".dpr": LegacyLanguage.PASCAL,  # Delphi project
    ".dpk": LegacyLanguage.PASCAL,
    ".lpr": LegacyLanguage.PASCAL,  # Lazarus
    # BASIC
    ".bas": LegacyLanguage.BASIC,
    ".bi": LegacyLanguage.BASIC,
    ".bm": LegacyLanguage.BASIC,
    # PL/I
    ".pli": LegacyLanguage.PLI,
    ".pl1": LegacyLanguage.PLI,
    ".pli1": LegacyLanguage.PLI,
    # Assembly
    ".asm": LegacyLanguage.ASSEMBLY,
    ".s": LegacyLanguage.ASSEMBLY,
    ".a51": LegacyLanguage.ASSEMBLY,
    ".a66": LegacyLanguage.ASSEMBLY,
    # RPG
    ".rpg": LegacyLanguage.RPG,
    ".rpgle": LegacyLanguage.RPG,
    ".sqlrpgle": LegacyLanguage.RPG,
    # Ada
    ".adb": LegacyLanguage.ADA,
    ".ads": LegacyLanguage.ADA,
    ".ada": LegacyLanguage.ADA,
    # C (legacy C can be 50 years old too)
    ".c": LegacyLanguage.C,
    ".h": LegacyLanguage.C,
}

# Extensions that indicate copybooks / include files
COPYBOOK_EXTENSIONS = {".cpy", ".ccp", ".bi", ".bm", ".h"}


# ─────────────────────────────────────────────
#  Content-Based Fingerprinting
# ─────────────────────────────────────────────

CONTENT_SIGNATURES: list[tuple[re.Pattern, LegacyLanguage]] = [
    # COBOL — division headers are unmistakable
    (re.compile(r"IDENTIFICATION\s+DIVISION", re.IGNORECASE), LegacyLanguage.COBOL),
    (re.compile(r"DATA\s+DIVISION", re.IGNORECASE), LegacyLanguage.COBOL),
    (re.compile(r"PROCEDURE\s+DIVISION", re.IGNORECASE), LegacyLanguage.COBOL),
    (re.compile(r"WORKING-STORAGE\s+SECTION", re.IGNORECASE), LegacyLanguage.COBOL),
    (re.compile(r"^\s{6}\d", re.MULTILINE), LegacyLanguage.COBOL),  # Column 1-6 seq numbers

    # Fortran
    (re.compile(r"^\s*PROGRAM\s+\w+", re.IGNORECASE | re.MULTILINE), LegacyLanguage.FORTRAN),
    (re.compile(r"^\s*SUBROUTINE\s+\w+", re.IGNORECASE | re.MULTILINE), LegacyLanguage.FORTRAN),
    (re.compile(r"^\s*IMPLICIT\s+NONE", re.IGNORECASE | re.MULTILINE), LegacyLanguage.FORTRAN),
    (re.compile(r"^\s*COMMON\s*/", re.IGNORECASE | re.MULTILINE), LegacyLanguage.FORTRAN),
    (re.compile(r"^\s*INTEGER|REAL|DOUBLE\s+PRECISION", re.IGNORECASE | re.MULTILINE), LegacyLanguage.FORTRAN),

    # Pascal
    (re.compile(r"^\s*program\s+\w+\s*;", re.IGNORECASE | re.MULTILINE), LegacyLanguage.PASCAL),
    (re.compile(r"^\s*begin\s*$", re.IGNORECASE | re.MULTILINE), LegacyLanguage.PASCAL),
    (re.compile(r"^\s*uses\s+\w+", re.IGNORECASE | re.MULTILINE), LegacyLanguage.PASCAL),
    (re.compile(r"^\s*procedure\s+\w+", re.IGNORECASE | re.MULTILINE), LegacyLanguage.PASCAL),

    # BASIC
    (re.compile(r"^\d+\s+(LET|PRINT|GOTO|GOSUB|IF|INPUT|REM)", re.IGNORECASE | re.MULTILINE), LegacyLanguage.BASIC),
    (re.compile(r"^\d+\s+", re.MULTILINE), LegacyLanguage.BASIC),  # Line-numbered code

    # PL/I
    (re.compile(r"^\s*\w+:\s*PROC(EDURE)?", re.IGNORECASE | re.MULTILINE), LegacyLanguage.PLI),
    (re.compile(r"^\s*DCL\s+", re.IGNORECASE | re.MULTILINE), LegacyLanguage.PLI),

    # RPG
    (re.compile(r"^\s{5}[HIFDCOE]\s", re.MULTILINE), LegacyLanguage.RPG),  # RPG spec indicators
    (re.compile(r"^\s*/FREE", re.IGNORECASE | re.MULTILINE), LegacyLanguage.RPG),

    # Assembly
    (re.compile(r"^\s*\.\s*(text|data|bss|global|section)", re.IGNORECASE | re.MULTILINE), LegacyLanguage.ASSEMBLY),
    (re.compile(r"^\s*(MOV|JMP|CALL|RET|PUSH|POP)\s", re.IGNORECASE | re.MULTILINE), LegacyLanguage.ASSEMBLY),

    # Ada
    (re.compile(r"^\s*with\s+\w+\s*;", re.IGNORECASE | re.MULTILINE), LegacyLanguage.ADA),
    (re.compile(r"^\s*package\s+(body\s+)?\w+\s+is", re.IGNORECASE | re.MULTILINE), LegacyLanguage.ADA),
]


def fingerprint_content(content: str) -> LegacyLanguage:
    """Detect language by scanning file content for signatures."""
    # Score each language by number of matching patterns
    scores: dict[LegacyLanguage, int] = {}
    for pattern, lang in CONTENT_SIGNATURES:
        if pattern.search(content):
            scores[lang] = scores.get(lang, 0) + 1

    if not scores:
        return LegacyLanguage.UNKNOWN

    # Return the language with the highest score
    return max(scores, key=lambda k: scores[k])


# ─────────────────────────────────────────────
#  Scanner
# ─────────────────────────────────────────────

# Skip these directories
SKIP_DIRS = {
    ".git", ".svn", ".hg", "__pycache__", "node_modules",
    ".venv", "venv", ".idea", ".vscode", ".codephoenix_checkpoints",
}

# Skip binary / irrelevant files
SKIP_EXTENSIONS = {
    ".exe", ".dll", ".so", ".o", ".obj", ".class", ".jar",
    ".zip", ".tar", ".gz", ".png", ".jpg", ".gif", ".pdf",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
}


def scan_directory(root: Path) -> ProjectManifest:
    """
    Recursively scan a directory for legacy source files.
    
    Returns a ProjectManifest with every discovered file,
    its detected language, line count, and byte size.
    """
    root = Path(root).resolve()
    manifest = ProjectManifest(root_path=root)

    if not root.exists():
        raise FileNotFoundError(f"Directory not found: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {root}")

    for item in sorted(root.rglob("*")):
        # Skip directories in SKIP_DIRS
        if any(skip in item.parts for skip in SKIP_DIRS):
            continue

        if not item.is_file():
            continue

        ext = item.suffix.lower()

        # Skip binary files
        if ext in SKIP_EXTENSIONS:
            continue

        # Try extension-based detection first
        language = EXTENSION_MAP.get(ext, LegacyLanguage.UNKNOWN)

        # Read file for content-based detection and metrics
        try:
            content = item.read_text(encoding="utf-8", errors="replace")
        except Exception:
            try:
                # Try latin-1 as fallback (handles EBCDIC-converted files)
                content = item.read_text(encoding="latin-1", errors="replace")
            except Exception:
                continue

        # If extension didn't match, try content fingerprinting
        if language == LegacyLanguage.UNKNOWN:
            language = fingerprint_content(content)

        # If still unknown, skip this file
        if language == LegacyLanguage.UNKNOWN:
            continue

        line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        byte_size = item.stat().st_size
        is_copybook = ext in COPYBOOK_EXTENSIONS

        source_file = SourceFile(
            path=item,
            language=language,
            line_count=line_count,
            byte_size=byte_size,
            encoding="utf-8",
            is_copybook=is_copybook,
        )

        manifest.files.append(source_file)
        manifest.total_lines += line_count
        manifest.total_bytes += byte_size
        manifest.languages_detected.add(language)

    manifest.scan_timestamp = time.time()
    return manifest

"""
CodePhoenix — Intake Preprocessor

Handles legacy formatting quirks before parsing:
- COBOL column 7 indicator area (comment *, continuation -, debug D)
- Fortran fixed-form column rules (1-5 label, 6 continuation, 7-72 code)
- BASIC line number stripping and GOTO target resolution
- EBCDIC → UTF-8 fallback handling
"""

from __future__ import annotations
import re
from codephoenix.models import LegacyLanguage


def preprocess(source: str, language: LegacyLanguage) -> str:
    """Normalize legacy source code before parsing."""
    if language == LegacyLanguage.COBOL:
        return preprocess_cobol(source)
    elif language == LegacyLanguage.FORTRAN:
        return preprocess_fortran(source)
    elif language == LegacyLanguage.BASIC:
        return preprocess_basic(source)
    elif language == LegacyLanguage.RPG:
        return preprocess_rpg(source)
    else:
        return source


def preprocess_cobol(source: str) -> str:
    """
    Normalize COBOL source:
    - Strip sequence number area (columns 1-6)
    - Handle indicator area (column 7): * = comment, - = continuation, D = debug
    - Strip identification area (columns 73-80)
    - Join continuation lines
    """
    lines = source.splitlines()
    processed = []
    continuation_buffer = ""

    for line in lines:
        # Pad short lines to at least 7 characters
        padded = line.ljust(80) if len(line) < 80 else line

        # Extract columns
        # seq_area = padded[0:6]      # Columns 1-6: sequence numbers
        indicator = padded[6] if len(padded) > 6 else " "   # Column 7: indicator
        code_area = padded[7:72] if len(padded) > 7 else ""  # Columns 8-72: code
        # ident_area = padded[72:]    # Columns 73-80: identification (ignored)

        if indicator == "*" or indicator == "/":
            # Comment line — preserve as a comment marker
            processed.append(f"      * {code_area.rstrip()}")
            continue

        if indicator == "D" or indicator == "d":
            # Debug line — treat as comment in modernization
            processed.append(f"      * DEBUG: {code_area.rstrip()}")
            continue

        if indicator == "-":
            # Continuation line — append to previous line
            if continuation_buffer:
                continuation_buffer = continuation_buffer.rstrip() + code_area.lstrip()
            continue
        else:
            # Regular line
            if continuation_buffer:
                processed.append(continuation_buffer)
                continuation_buffer = ""
            continuation_buffer = f"       {code_area.rstrip()}"

    # Flush remaining buffer
    if continuation_buffer:
        processed.append(continuation_buffer)

    return "\n".join(processed)


def preprocess_fortran(source: str) -> str:
    """
    Normalize Fortran source:
    - Detect fixed-form vs free-form
    - For fixed-form: strip columns, handle continuation markers (col 6)
    - Handle C/c/! comments
    """
    lines = source.splitlines()

    # Heuristic: if most lines are > 6 chars and col 1 has letters/spaces, it's fixed-form
    fixed_indicators = sum(
        1 for line in lines[:50]
        if len(line) >= 6 and (line[0] in "Cc*!" or line[0] == " " or line[0].isdigit())
    )
    is_fixed_form = fixed_indicators > len(lines[:50]) * 0.6

    if not is_fixed_form:
        # Free-form Fortran — minimal preprocessing needed
        return source

    processed = []
    continuation_buffer = ""

    for line in lines:
        if not line.strip():
            if continuation_buffer:
                processed.append(continuation_buffer)
                continuation_buffer = ""
            processed.append("")
            continue

        # Comment lines: C, c, *, or ! in column 1
        if line[0] in "Cc*!":
            if continuation_buffer:
                processed.append(continuation_buffer)
                continuation_buffer = ""
            processed.append(f"! {line[1:].rstrip()}")
            continue

        # Pad line if needed
        padded = line.ljust(72)

        # label_area = padded[0:5].strip()  # Columns 1-5: statement label
        continuation = padded[5] if len(padded) > 5 else " "  # Column 6
        code_area = padded[6:72].rstrip() if len(padded) > 6 else ""  # Columns 7-72

        if continuation != " " and continuation != "0":
            # Continuation line
            if continuation_buffer:
                continuation_buffer += " " + code_area.lstrip()
            continue
        else:
            if continuation_buffer:
                processed.append(continuation_buffer)
            # Start of a new statement
            label = padded[0:5].strip()
            prefix = f"{label:>5} " if label else "      "
            continuation_buffer = prefix + code_area

    if continuation_buffer:
        processed.append(continuation_buffer)

    return "\n".join(processed)


def preprocess_basic(source: str) -> str:
    """
    Normalize BASIC source:
    - Strip line numbers (preserve as comments for GOTO resolution)
    - Build line number → logical line mapping
    """
    lines = source.splitlines()
    processed = []
    line_map: dict[int, int] = {}  # BASIC line number → output line index

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            processed.append("")
            continue

        # Match leading line number
        match = re.match(r"^(\d+)\s*(.*)", stripped)
        if match:
            line_num = int(match.group(1))
            code = match.group(2)
            line_map[line_num] = len(processed)
            # Preserve line number as comment for GOTO resolution
            processed.append(f"' LINE {line_num}: {code}")
            processed.append(code)
        else:
            processed.append(stripped)

    # Append line map as a comment block at the end
    if line_map:
        processed.append("")
        processed.append("' ─── LINE NUMBER MAP ───")
        for basic_num, output_idx in sorted(line_map.items()):
            processed.append(f"' BASIC LINE {basic_num} → OUTPUT LINE {output_idx + 1}")

    return "\n".join(processed)


def preprocess_rpg(source: str) -> str:
    """
    Normalize RPG source:
    - Handle fixed-column specifications (H, F, D, I, C, O specs)
    - Handle /FREE and /END-FREE blocks
    """
    lines = source.splitlines()
    processed = []
    in_free_form = False

    for line in lines:
        stripped = line.strip()

        if stripped.upper().startswith("/FREE"):
            in_free_form = True
            processed.append("// BEGIN FREE-FORM RPG")
            continue
        elif stripped.upper().startswith("/END-FREE"):
            in_free_form = False
            processed.append("// END FREE-FORM RPG")
            continue

        if in_free_form:
            processed.append(line)
        else:
            # Fixed-form RPG — extract spec type and code
            if len(line) >= 6:
                spec_type = line[5] if len(line) > 5 else " "
                code = line[6:].rstrip() if len(line) > 6 else ""
                if spec_type.strip():
                    processed.append(f"// SPEC[{spec_type}]: {code}")
                else:
                    processed.append(f"// {line.rstrip()}")
            else:
                processed.append(f"// {line.rstrip()}")

    return "\n".join(processed)

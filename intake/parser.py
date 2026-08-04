"""
CodePhoenix — Intake Parser

Multi-language structural parser that extracts AST nodes from legacy source code.
Uses regex-based structural parsing to identify:
- Procedure/paragraph/subroutine boundaries
- Variable declarations
- Control flow keywords (GOTO, PERFORM, IF/ELSE, CALL)
- I/O operations (READ, WRITE, DISPLAY, ACCEPT)
- Data structures (record layouts, COMMON blocks)
"""

from __future__ import annotations
import re
from pathlib import Path

from codephoenix.models import (
    LegacyLanguage,
    ASTNode,
    ParsedFile,
    SourceFile,
)
from codephoenix.intake.preprocessor import preprocess


# ─────────────────────────────────────────────
#  Base Parser
# ─────────────────────────────────────────────

class StructuralParser:
    """Base class for language-specific structural parsers."""

    def parse(self, source: str, source_file: SourceFile) -> ParsedFile:
        raise NotImplementedError

    def _make_node(self, node_type: str, name: str = "",
                   start_line: int = 0, end_line: int = 0,
                   source_text: str = "", **props) -> ASTNode:
        return ASTNode(
            node_type=node_type,
            name=name,
            start_line=start_line,
            end_line=end_line,
            source_text=source_text,
            properties=props,
        )


# ─────────────────────────────────────────────
#  COBOL Parser
# ─────────────────────────────────────────────

class COBOLParser(StructuralParser):
    """Structural parser for COBOL programs."""

    # Division/Section/Paragraph patterns
    RE_DIVISION = re.compile(r"^\s*(IDENTIFICATION|ENVIRONMENT|DATA|PROCEDURE)\s+DIVISION", re.IGNORECASE | re.MULTILINE)
    RE_SECTION = re.compile(r"^\s*([\w-]+)\s+SECTION\s*\.", re.IGNORECASE | re.MULTILINE)
    RE_PARAGRAPH = re.compile(r"^\s{7}([\w-]+)\s*\.\s*$", re.IGNORECASE | re.MULTILINE)

    # Data items
    RE_DATA_ITEM = re.compile(r"^\s+(\d{2})\s+([\w-]+)\s+(PIC\s+.+?)\s*\.\s*$", re.IGNORECASE | re.MULTILINE)
    RE_COPY = re.compile(r"^\s+COPY\s+([\w-]+)\s*\.", re.IGNORECASE | re.MULTILINE)

    # Control flow
    RE_PERFORM = re.compile(r"\bPERFORM\s+([\w-]+)(\s+THRU\s+([\w-]+))?", re.IGNORECASE)
    RE_CALL = re.compile(r"\bCALL\s+['\"]?([\w-]+)['\"]?", re.IGNORECASE)
    RE_GOTO = re.compile(r"\bGO\s*TO\s+([\w-]+)", re.IGNORECASE)
    RE_IF = re.compile(r"\bIF\b", re.IGNORECASE)
    RE_EVALUATE = re.compile(r"\bEVALUATE\b", re.IGNORECASE)
    RE_MOVE = re.compile(r"\bMOVE\s+(.+?)\s+TO\s+([\w-]+)", re.IGNORECASE)
    RE_COMPUTE = re.compile(r"\bCOMPUTE\s+([\w-]+)\s*=", re.IGNORECASE)

    # I/O
    RE_READ = re.compile(r"\bREAD\s+([\w-]+)", re.IGNORECASE)
    RE_WRITE = re.compile(r"\bWRITE\s+([\w-]+)", re.IGNORECASE)
    RE_DISPLAY = re.compile(r"\bDISPLAY\b", re.IGNORECASE)
    RE_ACCEPT = re.compile(r"\bACCEPT\s+([\w-]+)", re.IGNORECASE)

    def parse(self, source: str, source_file: SourceFile) -> ParsedFile:
        lines = source.splitlines()
        root = self._make_node("program", name=self._find_program_id(source), end_line=len(lines))

        procedures = []
        variables = []
        calls = []
        data_structures = []
        errors = []

        # Find divisions
        for match in self.RE_DIVISION.finditer(source):
            div_name = match.group(1).upper()
            line_num = source[:match.start()].count("\n") + 1
            div_node = self._make_node("division", name=div_name, start_line=line_num,
                                       source_text=match.group())
            root.children.append(div_node)

        # Find sections
        for match in self.RE_SECTION.finditer(source):
            sec_name = match.group(1)
            line_num = source[:match.start()].count("\n") + 1
            sec_node = self._make_node("section", name=sec_name, start_line=line_num)
            root.children.append(sec_node)

        # Find paragraphs (procedures in COBOL)
        for match in self.RE_PARAGRAPH.finditer(source):
            para_name = match.group(1)
            line_num = source[:match.start()].count("\n") + 1
            para_node = self._make_node("procedure", name=para_name, start_line=line_num)
            procedures.append(para_node)
            root.children.append(para_node)

        # Find data items
        for match in self.RE_DATA_ITEM.finditer(source):
            level = match.group(1)
            name = match.group(2)
            pic = match.group(3)
            line_num = source[:match.start()].count("\n") + 1
            var_node = self._make_node("variable_decl", name=name, start_line=line_num,
                                       level=level, picture=pic)
            variables.append(var_node)
            if level == "01":
                data_structures.append(var_node)

        # Find PERFORM/CALL references
        for match in self.RE_PERFORM.finditer(source):
            target = match.group(1)
            thru = match.group(3)
            line_num = source[:match.start()].count("\n") + 1
            call_node = self._make_node("perform", name=target, start_line=line_num,
                                        thru_target=thru or "")
            calls.append(call_node)

        for match in self.RE_CALL.finditer(source):
            target = match.group(1)
            line_num = source[:match.start()].count("\n") + 1
            call_node = self._make_node("call", name=target, start_line=line_num)
            calls.append(call_node)

        for match in self.RE_GOTO.finditer(source):
            target = match.group(1)
            line_num = source[:match.start()].count("\n") + 1
            call_node = self._make_node("goto", name=target, start_line=line_num)
            calls.append(call_node)

        # Find COPY statements
        for match in self.RE_COPY.finditer(source):
            copybook = match.group(1)
            line_num = source[:match.start()].count("\n") + 1
            root.children.append(self._make_node("copy", name=copybook, start_line=line_num))

        return ParsedFile(
            source_file=source_file,
            ast_root=root,
            procedures=procedures,
            variables=variables,
            calls=calls,
            data_structures=data_structures,
            errors=errors,
        )

    def _find_program_id(self, source: str) -> str:
        match = re.search(r"PROGRAM-ID\.\s*([\w-]+)", source, re.IGNORECASE)
        return match.group(1) if match else "UNKNOWN"


# ─────────────────────────────────────────────
#  Fortran Parser
# ─────────────────────────────────────────────

class FortranParser(StructuralParser):
    """Structural parser for Fortran programs."""

    RE_PROGRAM = re.compile(r"^\s*PROGRAM\s+(\w+)", re.IGNORECASE | re.MULTILINE)
    RE_SUBROUTINE = re.compile(r"^\s*SUBROUTINE\s+(\w+)\s*(\(.*?\))?", re.IGNORECASE | re.MULTILINE)
    RE_FUNCTION = re.compile(r"^\s*(?:INTEGER|REAL|DOUBLE\s+PRECISION|COMPLEX|LOGICAL|CHARACTER)?\s*FUNCTION\s+(\w+)\s*\(", re.IGNORECASE | re.MULTILINE)
    RE_END = re.compile(r"^\s*END\s*(PROGRAM|SUBROUTINE|FUNCTION)?\s*(\w+)?", re.IGNORECASE | re.MULTILINE)

    RE_COMMON = re.compile(r"^\s*COMMON\s*/(\w+)/\s*(.*)", re.IGNORECASE | re.MULTILINE)
    RE_DECL = re.compile(r"^\s*(INTEGER|REAL|DOUBLE\s+PRECISION|COMPLEX|LOGICAL|CHARACTER)\s+(.+)", re.IGNORECASE | re.MULTILINE)
    RE_CALL = re.compile(r"\bCALL\s+(\w+)", re.IGNORECASE)
    RE_GOTO = re.compile(r"\bGO\s*TO\s+(\d+)", re.IGNORECASE)
    RE_DO = re.compile(r"\bDO\s+(\d+)?\s*(\w+)\s*=", re.IGNORECASE)
    RE_IF = re.compile(r"\bIF\s*\(", re.IGNORECASE)
    RE_WRITE = re.compile(r"\b(WRITE|PRINT|READ)\s*[\(,]", re.IGNORECASE)

    def parse(self, source: str, source_file: SourceFile) -> ParsedFile:
        lines = source.splitlines()
        root = self._make_node("program", end_line=len(lines))

        procedures = []
        variables = []
        calls = []
        data_structures = []

        # Find program units
        for match in self.RE_PROGRAM.finditer(source):
            name = match.group(1)
            line_num = source[:match.start()].count("\n") + 1
            node = self._make_node("program_unit", name=name, start_line=line_num)
            root.name = name
            root.children.append(node)

        for match in self.RE_SUBROUTINE.finditer(source):
            name = match.group(1)
            args = match.group(2) or ""
            line_num = source[:match.start()].count("\n") + 1
            node = self._make_node("procedure", name=name, start_line=line_num,
                                    subtype="subroutine", arguments=args)
            procedures.append(node)
            root.children.append(node)

        for match in self.RE_FUNCTION.finditer(source):
            name = match.group(1)
            line_num = source[:match.start()].count("\n") + 1
            node = self._make_node("procedure", name=name, start_line=line_num,
                                    subtype="function")
            procedures.append(node)
            root.children.append(node)

        # Find COMMON blocks
        for match in self.RE_COMMON.finditer(source):
            block_name = match.group(1)
            vars_text = match.group(2)
            line_num = source[:match.start()].count("\n") + 1
            node = self._make_node("common_block", name=block_name, start_line=line_num,
                                    source_text=vars_text)
            data_structures.append(node)
            root.children.append(node)

        # Find variable declarations
        for match in self.RE_DECL.finditer(source):
            dtype = match.group(1)
            var_list = match.group(2)
            line_num = source[:match.start()].count("\n") + 1
            for var_name in re.findall(r"(\w+)", var_list):
                node = self._make_node("variable_decl", name=var_name, start_line=line_num,
                                        data_type=dtype)
                variables.append(node)

        # Find CALL statements
        for match in self.RE_CALL.finditer(source):
            target = match.group(1)
            line_num = source[:match.start()].count("\n") + 1
            calls.append(self._make_node("call", name=target, start_line=line_num))

        for match in self.RE_GOTO.finditer(source):
            target = match.group(1)
            line_num = source[:match.start()].count("\n") + 1
            calls.append(self._make_node("goto", name=f"LABEL_{target}", start_line=line_num))

        return ParsedFile(
            source_file=source_file,
            ast_root=root,
            procedures=procedures,
            variables=variables,
            calls=calls,
            data_structures=data_structures,
        )


# ─────────────────────────────────────────────
#  Pascal Parser
# ─────────────────────────────────────────────

class PascalParser(StructuralParser):
    """Structural parser for Pascal programs."""

    RE_PROGRAM = re.compile(r"^\s*program\s+(\w+)", re.IGNORECASE | re.MULTILINE)
    RE_UNIT = re.compile(r"^\s*unit\s+(\w+)", re.IGNORECASE | re.MULTILINE)
    RE_PROCEDURE = re.compile(r"^\s*procedure\s+(\w+)\s*(\(.*?\))?\s*;", re.IGNORECASE | re.MULTILINE)
    RE_FUNCTION = re.compile(r"^\s*function\s+(\w+)\s*(\(.*?\))?\s*:\s*(\w+)\s*;", re.IGNORECASE | re.MULTILINE)
    RE_VAR = re.compile(r"^\s*(\w+)\s*:\s*([\w\[\].^]+)\s*;", re.IGNORECASE | re.MULTILINE)
    RE_TYPE = re.compile(r"^\s*(\w+)\s*=\s*(record|array|class|object)", re.IGNORECASE | re.MULTILINE)
    RE_USES = re.compile(r"^\s*uses\s+([\w,\s]+);", re.IGNORECASE | re.MULTILINE)
    RE_CALL = re.compile(r"\b(\w+)\s*\(", re.IGNORECASE)

    def parse(self, source: str, source_file: SourceFile) -> ParsedFile:
        lines = source.splitlines()
        root = self._make_node("program", end_line=len(lines))

        procedures = []
        variables = []
        calls = []
        data_structures = []

        # Program name
        match = self.RE_PROGRAM.search(source) or self.RE_UNIT.search(source)
        if match:
            root.name = match.group(1)

        # Procedures
        for match in self.RE_PROCEDURE.finditer(source):
            name = match.group(1)
            args = match.group(2) or ""
            line_num = source[:match.start()].count("\n") + 1
            node = self._make_node("procedure", name=name, start_line=line_num,
                                    subtype="procedure", arguments=args)
            procedures.append(node)
            root.children.append(node)

        # Functions
        for match in self.RE_FUNCTION.finditer(source):
            name = match.group(1)
            args = match.group(2) or ""
            return_type = match.group(3)
            line_num = source[:match.start()].count("\n") + 1
            node = self._make_node("procedure", name=name, start_line=line_num,
                                    subtype="function", arguments=args,
                                    return_type=return_type)
            procedures.append(node)
            root.children.append(node)

        # Type declarations (records, etc.)
        for match in self.RE_TYPE.finditer(source):
            name = match.group(1)
            kind = match.group(2)
            line_num = source[:match.start()].count("\n") + 1
            node = self._make_node("type_decl", name=name, start_line=line_num,
                                    type_kind=kind)
            data_structures.append(node)
            root.children.append(node)

        # Uses clauses (imports)
        for match in self.RE_USES.finditer(source):
            units = [u.strip() for u in match.group(1).split(",")]
            line_num = source[:match.start()].count("\n") + 1
            for unit in units:
                root.children.append(self._make_node("uses", name=unit, start_line=line_num))

        return ParsedFile(
            source_file=source_file,
            ast_root=root,
            procedures=procedures,
            variables=variables,
            calls=calls,
            data_structures=data_structures,
        )


# ─────────────────────────────────────────────
#  BASIC Parser
# ─────────────────────────────────────────────

class BASICParser(StructuralParser):
    """Structural parser for BASIC programs."""

    RE_LINE = re.compile(r"^(\d+)\s+(.*)", re.MULTILINE)
    RE_GOSUB = re.compile(r"\bGOSUB\s+(\d+)", re.IGNORECASE)
    RE_GOTO = re.compile(r"\bGOTO\s+(\d+)", re.IGNORECASE)
    RE_DIM = re.compile(r"\bDIM\s+([\w$]+)", re.IGNORECASE)
    RE_SUB = re.compile(r"^\s*SUB\s+(\w+)", re.IGNORECASE | re.MULTILINE)
    RE_FUNCTION = re.compile(r"^\s*DEF\s+FN(\w+)", re.IGNORECASE | re.MULTILINE)
    RE_INPUT = re.compile(r"\bINPUT\b", re.IGNORECASE)
    RE_PRINT = re.compile(r"\bPRINT\b", re.IGNORECASE)

    def parse(self, source: str, source_file: SourceFile) -> ParsedFile:
        lines = source.splitlines()
        root = self._make_node("program", name="BASIC_PROGRAM", end_line=len(lines))

        procedures = []
        variables = []
        calls = []

        # Find SUB definitions
        for match in self.RE_SUB.finditer(source):
            name = match.group(1)
            line_num = source[:match.start()].count("\n") + 1
            node = self._make_node("procedure", name=name, start_line=line_num,
                                    subtype="sub")
            procedures.append(node)
            root.children.append(node)

        # Find DEF FN definitions
        for match in self.RE_FUNCTION.finditer(source):
            name = f"FN{match.group(1)}"
            line_num = source[:match.start()].count("\n") + 1
            node = self._make_node("procedure", name=name, start_line=line_num,
                                    subtype="def_fn")
            procedures.append(node)

        # Find GOSUB/GOTO targets
        for match in self.RE_GOSUB.finditer(source):
            target = match.group(1)
            line_num = source[:match.start()].count("\n") + 1
            calls.append(self._make_node("gosub", name=f"LINE_{target}", start_line=line_num))

        for match in self.RE_GOTO.finditer(source):
            target = match.group(1)
            line_num = source[:match.start()].count("\n") + 1
            calls.append(self._make_node("goto", name=f"LINE_{target}", start_line=line_num))

        # Find DIM declarations
        for match in self.RE_DIM.finditer(source):
            name = match.group(1)
            line_num = source[:match.start()].count("\n") + 1
            variables.append(self._make_node("variable_decl", name=name, start_line=line_num))

        return ParsedFile(
            source_file=source_file,
            ast_root=root,
            procedures=procedures,
            variables=variables,
            calls=calls,
        )


# ─────────────────────────────────────────────
#  Generic / Fallback Parser
# ─────────────────────────────────────────────

class GenericParser(StructuralParser):
    """Fallback parser for languages without dedicated support."""

    RE_PROC = re.compile(r"^\s*(?:PROC(?:EDURE)?|SUB(?:ROUTINE)?|FUNCTION|DEF)\s+(\w+)", re.IGNORECASE | re.MULTILINE)
    RE_CALL = re.compile(r"\b(?:CALL|PERFORM|GOSUB|INVOKE)\s+(\w+)", re.IGNORECASE)
    RE_GOTO = re.compile(r"\b(?:GOTO|GO\s+TO)\s+(\w+)", re.IGNORECASE)

    def parse(self, source: str, source_file: SourceFile) -> ParsedFile:
        lines = source.splitlines()
        root = self._make_node("program", name=source_file.path.stem, end_line=len(lines))

        procedures = []
        calls = []

        for match in self.RE_PROC.finditer(source):
            name = match.group(1)
            line_num = source[:match.start()].count("\n") + 1
            node = self._make_node("procedure", name=name, start_line=line_num)
            procedures.append(node)
            root.children.append(node)

        for match in self.RE_CALL.finditer(source):
            target = match.group(1)
            line_num = source[:match.start()].count("\n") + 1
            calls.append(self._make_node("call", name=target, start_line=line_num))

        for match in self.RE_GOTO.finditer(source):
            target = match.group(1)
            line_num = source[:match.start()].count("\n") + 1
            calls.append(self._make_node("goto", name=target, start_line=line_num))

        return ParsedFile(
            source_file=source_file,
            ast_root=root,
            procedures=procedures,
            calls=calls,
        )


# ─────────────────────────────────────────────
#  Parser Registry
# ─────────────────────────────────────────────

PARSERS: dict[LegacyLanguage, type[StructuralParser]] = {
    LegacyLanguage.COBOL: COBOLParser,
    LegacyLanguage.FORTRAN: FortranParser,
    LegacyLanguage.PASCAL: PascalParser,
    LegacyLanguage.BASIC: BASICParser,
}


def parse_file(source_file: SourceFile) -> ParsedFile:
    """
    Parse a legacy source file into a structured ParsedFile.
    
    1. Read and preprocess the source
    2. Select the appropriate parser
    3. Extract procedures, variables, calls, and data structures
    """
    try:
        source = source_file.path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        source = source_file.path.read_text(encoding="latin-1", errors="replace")

    # Preprocess for format normalization
    preprocessed = preprocess(source, source_file.language)

    # Select parser
    parser_cls = PARSERS.get(source_file.language, GenericParser)
    parser = parser_cls()

    return parser.parse(preprocessed, source_file)


def parse_manifest(manifest) -> list[ParsedFile]:
    """Parse all files in a ProjectManifest."""
    results = []
    for sf in manifest.files:
        try:
            parsed = parse_file(sf)
            results.append(parsed)
        except Exception as e:
            # Create a minimal ParsedFile with error
            pf = ParsedFile(
                source_file=sf,
                ast_root=ASTNode(node_type="error", name=str(e)),
                errors=[str(e)],
            )
            results.append(pf)
    return results

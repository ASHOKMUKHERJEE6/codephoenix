"""
CodePhoenix — Control Flow Graph Builder

Walks each procedure's AST to identify basic blocks and connect them
via edges for IF/ELSE, PERFORM/THRU, GOTO, EVALUATE/WHEN, DO/WHILE loops.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from codephoenix.models import (
    ASTNode,
    ParsedFile,
    GraphNode,
    GraphEdge,
    EdgeType,
    LegacyLanguage,
)


@dataclass
class BasicBlock:
    """A straight-line sequence of code with no branches in the middle."""
    id: str
    start_line: int
    end_line: int
    statements: list[str] = field(default_factory=list)
    is_entry: bool = False
    is_exit: bool = False


@dataclass
class CFG:
    """Control Flow Graph for a single procedure."""
    procedure_name: str
    file_path: str
    blocks: list[BasicBlock] = field(default_factory=list)
    edges: list[tuple[str, str, EdgeType]] = field(default_factory=list)
    cyclomatic_complexity: int = 1

    @property
    def node_count(self) -> int:
        return len(self.blocks)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def to_graph_nodes_edges(self) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Convert to unified graph format."""
        nodes = []
        edges = []
        for block in self.blocks:
            nodes.append(GraphNode(
                id=block.id,
                node_type="basic_block",
                label=f"BB:{block.start_line}-{block.end_line}",
                file_path=self.file_path,
                start_line=block.start_line,
                end_line=block.end_line,
                properties={
                    "is_entry": block.is_entry,
                    "is_exit": block.is_exit,
                    "statement_count": len(block.statements),
                },
            ))
        for src, dst, etype in self.edges:
            edges.append(GraphEdge(
                source_id=src,
                target_id=dst,
                edge_type=etype,
            ))
        return nodes, edges


# ─────────────────────────────────────────────
#  Control Flow Patterns
# ─────────────────────────────────────────────

# Patterns that create branches (increase cyclomatic complexity)
BRANCH_PATTERNS = {
    LegacyLanguage.COBOL: [
        re.compile(r"\bIF\b", re.IGNORECASE),
        re.compile(r"\bEVALUATE\b", re.IGNORECASE),
        re.compile(r"\bPERFORM\b.*\bUNTIL\b", re.IGNORECASE),
        re.compile(r"\bPERFORM\b.*\bVARYING\b", re.IGNORECASE),
        re.compile(r"\bGO\s*TO\b", re.IGNORECASE),
        re.compile(r"\bWHEN\b", re.IGNORECASE),
        re.compile(r"\bON\s+SIZE\s+ERROR\b", re.IGNORECASE),
        re.compile(r"\bAT\s+END\b", re.IGNORECASE),
        re.compile(r"\bINVALID\s+KEY\b", re.IGNORECASE),
    ],
    LegacyLanguage.FORTRAN: [
        re.compile(r"\bIF\s*\(", re.IGNORECASE),
        re.compile(r"\bELSE\s*IF\b", re.IGNORECASE),
        re.compile(r"\bDO\s+\d", re.IGNORECASE),
        re.compile(r"\bDO\s+WHILE\b", re.IGNORECASE),
        re.compile(r"\bGO\s*TO\b", re.IGNORECASE),
        re.compile(r"\bSELECT\s+CASE\b", re.IGNORECASE),
        re.compile(r"\bCASE\s*\(", re.IGNORECASE),
    ],
    LegacyLanguage.PASCAL: [
        re.compile(r"\bif\b", re.IGNORECASE),
        re.compile(r"\bcase\b", re.IGNORECASE),
        re.compile(r"\bwhile\b", re.IGNORECASE),
        re.compile(r"\bfor\b", re.IGNORECASE),
        re.compile(r"\brepeat\b", re.IGNORECASE),
        re.compile(r"\bgoto\b", re.IGNORECASE),
    ],
    LegacyLanguage.BASIC: [
        re.compile(r"\bIF\b", re.IGNORECASE),
        re.compile(r"\bGOTO\b", re.IGNORECASE),
        re.compile(r"\bGOSUB\b", re.IGNORECASE),
        re.compile(r"\bFOR\b", re.IGNORECASE),
        re.compile(r"\bWHILE\b", re.IGNORECASE),
        re.compile(r"\bON\s+.*\bGOTO\b", re.IGNORECASE),
    ],
}


def build_cfg(parsed_file: ParsedFile) -> list[CFG]:
    """
    Build Control Flow Graphs for every procedure in a parsed file.
    
    For each procedure:
    1. Split code into basic blocks at branch points
    2. Connect blocks with typed edges
    3. Compute cyclomatic complexity
    """
    cfgs = []
    language = parsed_file.source_file.language

    try:
        source = parsed_file.source_file.path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        source = parsed_file.source_file.path.read_text(encoding="latin-1", errors="replace")

    lines = source.splitlines()
    branch_pats = BRANCH_PATTERNS.get(language, [])

    # If no procedures found, treat entire file as one procedure
    procedures = parsed_file.procedures or [
        ASTNode(node_type="procedure", name=parsed_file.source_file.path.stem,
                start_line=1, end_line=len(lines))
    ]

    for proc in procedures:
        proc_id = f"{parsed_file.source_file.path.name}:{proc.name}"
        start = max(proc.start_line - 1, 0)
        end = proc.end_line if proc.end_line > 0 else len(lines)
        proc_lines = lines[start:end]

        # Build basic blocks by splitting at branch points
        blocks: list[BasicBlock] = []
        current_statements: list[str] = []
        block_start = start + 1

        for i, line in enumerate(proc_lines):
            line_num = start + i + 1
            stripped = line.strip()
            if not stripped:
                continue

            is_branch = any(pat.search(stripped) for pat in branch_pats)

            if is_branch and current_statements:
                # Emit the current block
                block_id = f"{proc_id}:BB{len(blocks)}"
                blocks.append(BasicBlock(
                    id=block_id,
                    start_line=block_start,
                    end_line=line_num - 1,
                    statements=current_statements,
                ))
                current_statements = [stripped]
                block_start = line_num
            else:
                current_statements.append(stripped)

        # Emit final block
        if current_statements:
            block_id = f"{proc_id}:BB{len(blocks)}"
            blocks.append(BasicBlock(
                id=block_id,
                start_line=block_start,
                end_line=end,
                statements=current_statements,
            ))

        if not blocks:
            continue

        # Mark entry and exit
        blocks[0].is_entry = True
        blocks[-1].is_exit = True

        # Connect blocks with edges
        edges: list[tuple[str, str, EdgeType]] = []
        for i in range(len(blocks) - 1):
            # Default: falls through to next block
            edges.append((blocks[i].id, blocks[i + 1].id, EdgeType.FALLS_THROUGH))

            # Check for branch statements that create additional edges
            for stmt in blocks[i].statements:
                for pat in branch_pats:
                    if pat.search(stmt):
                        edges.append((blocks[i].id, blocks[i + 1].id, EdgeType.BRANCHES_TO))
                        break

        # Compute cyclomatic complexity: M = E - N + 2
        num_edges = len(edges)
        num_nodes = len(blocks)
        complexity = max(num_edges - num_nodes + 2, 1)

        cfg = CFG(
            procedure_name=proc.name,
            file_path=str(parsed_file.source_file.path),
            blocks=blocks,
            edges=edges,
            cyclomatic_complexity=complexity,
        )
        cfgs.append(cfg)

    return cfgs

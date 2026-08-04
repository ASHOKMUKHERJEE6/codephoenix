"""
CodePhoenix — Shared Data Models

Every data structure used across the pipeline: manifests, AST nodes,
graph structures, translation units, repair records.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional
from pathlib import Path
import json
import time


# ─────────────────────────────────────────────
#  Language Enums
# ─────────────────────────────────────────────

class LegacyLanguage(Enum):
    """Languages this system can intake."""
    COBOL = "cobol"
    FORTRAN = "fortran"
    PASCAL = "pascal"
    BASIC = "basic"
    PLI = "pli"
    ASSEMBLY = "assembly"
    RPG = "rpg"
    ADA = "ada"
    C = "c"
    UNKNOWN = "unknown"


class TargetLanguage(Enum):
    """Languages this system can output."""
    PYTHON = "python"
    RUST = "rust"
    GO = "go"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    CSHARP = "csharp"


# ─────────────────────────────────────────────
#  Intake Models
# ─────────────────────────────────────────────

@dataclass
class SourceFile:
    """A single source file discovered during intake."""
    path: Path
    language: LegacyLanguage
    line_count: int = 0
    byte_size: int = 0
    encoding: str = "utf-8"
    is_copybook: bool = False  # COBOL COPY members, Fortran INCLUDEs


@dataclass
class ProjectManifest:
    """Complete inventory of a legacy project."""
    root_path: Path
    files: list[SourceFile] = field(default_factory=list)
    total_lines: int = 0
    total_bytes: int = 0
    languages_detected: set[LegacyLanguage] = field(default_factory=set)
    scan_timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "root_path": str(self.root_path),
            "total_files": len(self.files),
            "total_lines": self.total_lines,
            "total_bytes": self.total_bytes,
            "languages": [lang.value for lang in self.languages_detected],
            "scan_timestamp": self.scan_timestamp,
            "files": [
                {
                    "path": str(f.path),
                    "language": f.language.value,
                    "lines": f.line_count,
                    "bytes": f.byte_size,
                    "encoding": f.encoding,
                    "is_copybook": f.is_copybook,
                }
                for f in self.files
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


# ─────────────────────────────────────────────
#  AST / Parse Models
# ─────────────────────────────────────────────

@dataclass
class ASTNode:
    """A node in our unified AST representation."""
    node_type: str          # e.g., "procedure", "variable_decl", "if_statement"
    name: str = ""          # Name if applicable (procedure name, variable name)
    start_line: int = 0
    end_line: int = 0
    children: list[ASTNode] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    source_text: str = ""   # Original source code for this node

    def walk(self):
        """Depth-first walk of this subtree."""
        yield self
        for child in self.children:
            yield from child.walk()

    @property
    def descendant_count(self) -> int:
        return sum(1 for _ in self.walk())


@dataclass
class ParsedFile:
    """A fully parsed source file with its AST."""
    source_file: SourceFile
    ast_root: ASTNode
    procedures: list[ASTNode] = field(default_factory=list)
    variables: list[ASTNode] = field(default_factory=list)
    calls: list[ASTNode] = field(default_factory=list)
    data_structures: list[ASTNode] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def total_nodes(self) -> int:
        return self.ast_root.descendant_count


# ─────────────────────────────────────────────
#  Graph Models
# ─────────────────────────────────────────────

class EdgeType(Enum):
    """Types of edges in the knowledge graph."""
    CONTAINS = "contains"
    CALLS = "calls"
    CALLED_BY = "called_by"
    DEFINES = "defines"
    USES = "uses"
    MUTATES = "mutates"
    BRANCHES_TO = "branches_to"
    FALLS_THROUGH = "falls_through"
    LOOPS_BACK = "loops_back"
    DEPENDS_ON = "depends_on"
    INCLUDES = "includes"
    GOTO = "goto"


@dataclass
class GraphNode:
    """A node in the knowledge graph."""
    id: str                      # Unique identifier (file:procedure:line)
    node_type: str               # "procedure", "variable", "basic_block", "file"
    label: str                   # Human-readable label
    file_path: str = ""
    start_line: int = 0
    end_line: int = 0
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """An edge in the knowledge graph."""
    source_id: str
    target_id: str
    edge_type: EdgeType
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphStats:
    """Statistics about the knowledge graph."""
    total_nodes: int = 0
    total_edges: int = 0
    total_procedures: int = 0
    total_variables: int = 0
    total_basic_blocks: int = 0
    max_cyclomatic_complexity: int = 0
    avg_cyclomatic_complexity: float = 0.0
    dead_code_percentage: float = 0.0
    connected_components: int = 0
    most_called_procedures: list[tuple[str, int]] = field(default_factory=list)
    highest_complexity_procedures: list[tuple[str, int]] = field(default_factory=list)


# ─────────────────────────────────────────────
#  Translation Models
# ─────────────────────────────────────────────

class TranslationStatus(Enum):
    PENDING = auto()
    RULE_TRANSLATED = auto()
    LLM_TRANSLATED = auto()
    COMPILES = auto()
    TESTS_PASS = auto()
    REPAIRED = auto()
    FAILED = auto()
    HUMAN_REVIEW = auto()


@dataclass
class TranslationUnit:
    """A single module/procedure being translated."""
    id: str
    original_source: str
    original_language: LegacyLanguage
    target_language: TargetLanguage
    translated_source: str = ""
    status: TranslationStatus = TranslationStatus.PENDING
    repair_iterations: int = 0
    max_repair_iterations: int = 10
    compile_errors: list[CompileError] = field(default_factory=list)
    test_results: list[TestResult] = field(default_factory=list)
    nl_summary: str = ""     # Natural language summary for LLM context
    callers: list[str] = field(default_factory=list)
    callees: list[str] = field(default_factory=list)
    input_vars: list[str] = field(default_factory=list)
    output_vars: list[str] = field(default_factory=list)


@dataclass
class CompileError:
    """A structured compiler error."""
    file: str
    line: int
    column: int
    error_code: str
    message: str
    severity: str = "error"  # error, warning, info


@dataclass
class TestResult:
    """Result of running a test against translated code."""
    test_name: str
    passed: bool
    expected_output: str = ""
    actual_output: str = ""
    error_message: str = ""
    execution_time_ms: float = 0.0


# ─────────────────────────────────────────────
#  Repair Models
# ─────────────────────────────────────────────

class RepairAction(Enum):
    FIX_COMPILE_ERROR = auto()
    FIX_TEST_FAILURE = auto()
    FRESH_RETRANSLATION = auto()
    ESCALATE_TO_HUMAN = auto()


@dataclass
class RepairRecord:
    """Record of a single repair attempt."""
    iteration: int
    action: RepairAction
    diagnosis: str
    fix_applied: str
    success: bool
    timestamp: float = field(default_factory=time.time)


@dataclass
class RepairReport:
    """Complete repair history for a translation unit."""
    unit_id: str
    records: list[RepairRecord] = field(default_factory=list)
    final_status: TranslationStatus = TranslationStatus.PENDING
    total_iterations: int = 0
    oscillation_detected: bool = False

    @property
    def success(self) -> bool:
        return self.final_status in (
            TranslationStatus.COMPILES,
            TranslationStatus.TESTS_PASS,
            TranslationStatus.REPAIRED,
        )


# ─────────────────────────────────────────────
#  Pipeline Models
# ─────────────────────────────────────────────

class PipelinePhase(Enum):
    INTAKE = "intake"
    MAPPING = "mapping"
    TRANSLATION = "translation"
    REPAIR = "repair"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class PipelineState:
    """Checkpoint-able state of the full pipeline."""
    phase: PipelinePhase = PipelinePhase.INTAKE
    manifest: Optional[ProjectManifest] = None
    parsed_files: list[ParsedFile] = field(default_factory=list)
    graph_stats: Optional[GraphStats] = None
    translation_units: list[TranslationUnit] = field(default_factory=list)
    repair_reports: list[RepairReport] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    errors: list[str] = field(default_factory=list)

    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self.start_time

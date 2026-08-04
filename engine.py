"""
CodePhoenix — Main Autonomous Engine

Coordinates the entire pipeline:
1. Intake (Scanner -> Preprocessor -> Parser)
2. Mapper (CFG -> Knowledge Graph)
3. Translator (LLM translation)
4. Repair (Self-healing validation loop)
"""

import os
from pathlib import Path
from typing import Optional

from codephoenix.config import Config
from codephoenix.models import ProjectManifest, TargetLanguage
from codephoenix.intake.scanner import scan_directory
from codephoenix.intake.parser import parse_file
from codephoenix.mapper.graph_builder import KnowledgeGraph
from codephoenix.translator.engine import TranslationEngine
from codephoenix.repair.engine import RepairEngine


class CodePhoenixEngine:
    """The central autonomous modernization system."""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.graph = KnowledgeGraph()
        self.translator = TranslationEngine(self.config)
        self.repair = RepairEngine(self.config)
        
    def modernize_project(self, source_dir: str, target_dir: str, target_language: TargetLanguage):
        """
        End-to-end autonomous modernization of an entire legacy project.
        """
        source_path = Path(source_dir).resolve()
        target_path = Path(target_dir).resolve()
        
        if not source_path.exists():
            raise FileNotFoundError(f"Source directory not found: {source_path}")
            
        target_path.mkdir(parents=True, exist_ok=True)
        
        print(f"=== CodePhoenix Engine Started ===")
        print(f"Source: {source_path}")
        print(f"Target: {target_path} ({target_language.name})")
        print(f"==================================")
        
        # 1. Intake: Scan and Fingerprint
        print("\n[1/4] INTAKE: Scanning and fingerprinting legacy codebase...")
        manifest = scan_directory(source_path)
        print(f"  Found {len(manifest.files)} legacy files ({manifest.total_lines} LOC).")
        
        parsed_files = []
        for src_file in manifest.files:
            print(f"  Parsing: {src_file.path.name} ({src_file.language.name})")
            parsed = parse_file(src_file)
            parsed_files.append(parsed)
            
        # 2. Mapper: Build Knowledge Graph
        print("\n[2/4] MAPPER: Building unified logic graph...")
        for parsed in parsed_files:
            self.graph.ingest(parsed)
        
        print(f"  Graph created: {self.graph.graph.number_of_nodes()} nodes, {self.graph.graph.number_of_edges()} edges.")
        
        # Optional: Export graph for visualization
        graphml_path = target_path / "_codephoenix_graph.graphml"
        self.graph.export_graphml(str(graphml_path))
        print(f"  GraphML exported to {graphml_path.name}")
        
        # 3. Translate & 4. Repair
        print("\n[3/4 & 4/4] TRANSLATE & REPAIR: Autonomous modernization loop...")
        
        for parsed in parsed_files:
            print(f"\n  Processing: {parsed.source_file.path.name}")
            
            # Translate
            print(f"    - Translating...")
            translated_unit = self.translator.translate(parsed, target_language)
            
            # Repair
            if self.config.enable_self_repair:
                print(f"    - Validating and self-healing...")
                translated_unit = self.repair.heal(translated_unit)
                
            # Write to disk
            out_ext = {
                TargetLanguage.RUST: ".rs",
                TargetLanguage.PYTHON: ".py",
                TargetLanguage.GO: ".go",
                TargetLanguage.JAVA: ".java",
                # TargetLanguage.CPP: ".cpp",
                TargetLanguage.CSHARP: ".cs",
                TargetLanguage.TYPESCRIPT: ".ts",
            }.get(target_language, ".txt")
            
            # Preserve directory structure
            rel_path = parsed.source_file.path.relative_to(source_path)
            out_path = target_path / rel_path.with_suffix(out_ext)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            
            out_path.write_text(translated_unit.translated_source, encoding="utf-8")
            print(f"    - Saved modernized code to: {out_path}")
            
        print("\n=== CodePhoenix Modernization Complete ===")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="CodePhoenix - Legacy Modernization Engine")
    parser.add_argument("source", help="Directory containing legacy source code")
    parser.add_argument("target", help="Directory to output modernized code")
    parser.add_argument("--lang", default="RUST", choices=[e.name for e in TargetLanguage], 
                        help="Target modern language")
    
    args = parser.parse_args()
    
    target_lang = TargetLanguage[args.lang]
    engine = CodePhoenixEngine()
    engine.modernize_project(args.source, args.target, target_lang)

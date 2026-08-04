"""
CodePhoenix — Configuration

Manages API keys, model selection, file paths, and pipeline settings.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import json
import os


@dataclass
class LLMConfig:
    """Configuration for the LLM provider."""
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o"
    max_tokens: int = 4096
    temperature: float = 0.2  # Low temperature for deterministic translation
    timeout: int = 60
    max_retries: int = 3

    @classmethod
    def from_env(cls) -> LLMConfig:
        """Load from environment variables."""
        return cls(
            api_key=os.environ.get("OPENAI_API_KEY", ""),
            base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            model=os.environ.get("CODEPHOENIX_MODEL", "gpt-4o"),
        )


@dataclass
class RepairConfig:
    """Configuration for the self-repair engine."""
    max_iterations: int = 10
    fresh_retranslation_threshold: int = 5  # After this many failures, try fresh translation
    compile_timeout: int = 30  # seconds
    test_timeout: int = 30     # seconds
    enable_behavioral_comparison: bool = True


@dataclass
class MapperConfig:
    """Configuration for the logic mapper."""
    max_nodes_networkx: int = 10_000_000  # Switch to streaming above this
    export_format: str = "json"  # json, dot, mermaid
    enable_visualization: bool = True
    detect_dead_code: bool = True


@dataclass
class Config:
    """Master configuration for CodePhoenix."""
    llm: LLMConfig = field(default_factory=LLMConfig)
    repair: RepairConfig = field(default_factory=RepairConfig)
    mapper: MapperConfig = field(default_factory=MapperConfig)

    # Pipeline
    parallel_workers: int = 4
    enable_self_repair: bool = True
    checkpoint_dir: Path = Path(".codephoenix_checkpoints")
    output_dir: Path = Path("./output")
    verbose: bool = True

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        """Load config from JSON file, falling back to defaults + env."""
        config = cls()
        config.llm = LLMConfig.from_env()

        if path and path.exists():
            with open(path) as f:
                data = json.load(f)
            if "llm" in data:
                for k, v in data["llm"].items():
                    if hasattr(config.llm, k):
                        setattr(config.llm, k, v)
            if "repair" in data:
                for k, v in data["repair"].items():
                    if hasattr(config.repair, k):
                        setattr(config.repair, k, v)
            if "mapper" in data:
                for k, v in data["mapper"].items():
                    if hasattr(config.mapper, k):
                        setattr(config.mapper, k, v)
            if "parallel_workers" in data:
                config.parallel_workers = data["parallel_workers"]
            if "verbose" in data:
                config.verbose = data["verbose"]

        return config

    def save(self, path: Path) -> None:
        """Save current config to JSON."""
        data = {
            "llm": {
                "base_url": self.llm.base_url,
                "model": self.llm.model,
                "max_tokens": self.llm.max_tokens,
                "temperature": self.llm.temperature,
            },
            "repair": {
                "max_iterations": self.repair.max_iterations,
                "fresh_retranslation_threshold": self.repair.fresh_retranslation_threshold,
            },
            "mapper": {
                "export_format": self.mapper.export_format,
                "enable_visualization": self.mapper.enable_visualization,
            },
            "parallel_workers": self.parallel_workers,
            "verbose": self.verbose,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

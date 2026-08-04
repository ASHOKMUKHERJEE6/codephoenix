"""
CodePhoenix — Self-Healing Repair Engine

Compiles/analyzes translated modern code. If errors are found,
it feeds the errors back to the LLM for autonomous correction.
"""

from __future__ import annotations
import os
import subprocess
import tempfile
import httpx
from pathlib import Path

from codephoenix.models import TranslationUnit, TargetLanguage
from codephoenix.config import Config


class RepairEngine:
    """Autonomous self-repair loop."""
    
    def __init__(self, config: Config):
        self.config = config
        
    def heal(self, unit: TranslationUnit) -> TranslationUnit:
        """
        Run the self-healing loop up to `max_repair_loops` times.
        1. Check syntax/compile
        2. If error, ask LLM to fix based on error message
        3. Repeat until clean or max loops reached
        """
        current_code = unit.translated_source
        loops = 0
        
        while loops < self.config.repair.max_iterations:
            is_valid, error_msg = self._validate(current_code, unit.target_language)
            
            if is_valid:
                unit.translated_source = current_code
                return unit
                
            # If invalid, attempt repair
            print(f"[REPAIR] Loop {loops+1}/{self.config.repair.max_iterations} for {unit.id}")
            print(f"[REPAIR] Error: {error_msg.splitlines()[0] if error_msg else 'Unknown'}")
            
            current_code = self._request_repair(current_code, error_msg, unit.target_language)
            loops += 1
            
        # If we failed after max loops
        unit.translated_source = f"// [WARNING: Max repair loops reached. Code may contain errors.]\n// Error:\n// {error_msg}\n\n{current_code}"
        return unit

    def _validate(self, code: str, lang: TargetLanguage) -> tuple[bool, str]:
        """Run language-specific validation (syntax check or compilation)."""
        if lang == TargetLanguage.PYTHON:
            return self._validate_python(code)
        elif lang == TargetLanguage.RUST:
            return self._validate_rust(code)
        elif lang == TargetLanguage.GO:
            return self._validate_go(code)
        elif lang == TargetLanguage.JAVA:
            return self._validate_java(code)
        # elif lang == TargetLanguage.CPP:
        #     return self._validate_cpp(code)
        else:
            # Fallback: assume valid if no validator exists
            return True, ""

    def _validate_python(self, code: str) -> tuple[bool, str]:
        """Use Python's built-in compile() to check syntax."""
        try:
            compile(code, "<string>", "exec")
            return True, ""
        except SyntaxError as e:
            return False, f"SyntaxError: {e.msg} at line {e.lineno}, offset {e.offset}\n{e.text}"
        except Exception as e:
            return False, str(e)

    def _validate_rust(self, code: str) -> tuple[bool, str]:
        """Use rustc to check syntax (rustc --emit=metadata)."""
        with tempfile.NamedTemporaryFile(suffix=".rs", delete=False, mode="w") as f:
            f.write(code)
            temp_path = f.name
            
        try:
            result = subprocess.run(
                ["rustc", "--emit=metadata", temp_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return True, ""
            return False, result.stderr
        except Exception as e:
            return False, f"Failed to run rustc: {e}"
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def _validate_go(self, code: str) -> tuple[bool, str]:
        """Use go build to check syntax."""
        with tempfile.TemporaryDirectory() as d:
            file_path = Path(d) / "main.go"
            # Ensure it has a package declaration for go build
            if "package " not in code:
                code = "package main\n\n" + code
            file_path.write_text(code)
            
            try:
                result = subprocess.run(
                    ["go", "build"],
                    cwd=d,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return True, ""
                return False, result.stderr
            except Exception as e:
                return False, f"Failed to run go build: {e}"

    def _validate_java(self, code: str) -> tuple[bool, str]:
        """Use javac to check syntax."""
        with tempfile.TemporaryDirectory() as d:
            # Find class name to name the file correctly
            import re
            match = re.search(r"class\s+(\w+)", code)
            class_name = match.group(1) if match else "Main"
            file_path = Path(d) / f"{class_name}.java"
            file_path.write_text(code)
            
            try:
                result = subprocess.run(
                    ["javac", str(file_path)],
                    cwd=d,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return True, ""
                return False, result.stderr
            except Exception as e:
                return False, f"Failed to run javac: {e}"
                
    def _validate_cpp(self, code: str) -> tuple[bool, str]:
        """Use g++ to check syntax."""
        with tempfile.NamedTemporaryFile(suffix=".cpp", delete=False, mode="w") as f:
            f.write(code)
            temp_path = f.name
            
        try:
            result = subprocess.run(
                ["g++", "-fsyntax-only", temp_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return True, ""
            return False, result.stderr
        except Exception as e:
            return False, f"Failed to run g++: {e}"
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def _request_repair(self, code: str, error_msg: str, target_lang: TargetLanguage) -> str:
        """Ask LLM to fix the code based on the compiler error."""
        prompt = f"""
The following {target_lang.name} code failed to compile/parse.

Error message:
{error_msg}

Source Code:
```
{code}
```

Please fix the errors and provide ONLY the corrected {target_lang.name} code. Do not include markdown codeblocks (```) or explanations.
"""
        
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return f"// [SIMULATED REPAIR]\n// Code failed validation with error:\n// {error_msg.splitlines()[0]}\n\n{code}"
            
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{self.config.llm_endpoint}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.config.llm_model,
                        "messages": [
                            {"role": "system", "content": "You are an expert compiler error fixer."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.1
                    },
                    timeout=60.0
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                
                if content.startswith("```"):
                    content = "\n".join(content.split("\n")[1:])
                if content.endswith("```"):
                    content = "\n".join(content.split("\n")[:-1])
                    
                return content.strip()
        except Exception:
            return code # Fallback to broken code if API fails during repair

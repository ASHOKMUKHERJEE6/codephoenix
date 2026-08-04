"""
CodePhoenix — Translation Engine

Uses context-aware LLM prompting to translate legacy ASTs/CFGs into modern languages.
Handles chunking of large procedures and maintains variable context.
"""

from __future__ import annotations
import os
import httpx
from codephoenix.models import TranslationUnit, ParsedFile, LegacyLanguage, TargetLanguage
from codephoenix.config import Config


class TranslationEngine:
    """Orchestrates the translation of legacy code to modern code."""
    
    def __init__(self, config: Config):
        self.config = config
        
    def translate(self, parsed_file: ParsedFile, target_lang: TargetLanguage) -> TranslationUnit:
        """
        Translate an entire parsed file.
        In a production billion-node system, this would translate node-by-node
        or block-by-block using the Knowledge Graph. For this prototype, we'll
        translate procedure by procedure and stitch them together.
        """
        unit = TranslationUnit(
            id=parsed_file.source_file.path.name,
            original_source="", # Set later or empty
            original_language=parsed_file.source_file.language,
            target_language=target_lang
        )
        
        try:
            source_text = parsed_file.source_file.path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            source_text = parsed_file.source_file.path.read_text(encoding="latin-1", errors="replace")
            
        # Global context (Variables, Data Structures)
        global_context = self._extract_global_context(parsed_file)
        
        # Translate procedures
        translated_procs = []
        if parsed_file.procedures:
            for proc in parsed_file.procedures:
                # Extract the source code for this procedure
                start_idx = max(0, proc.start_line - 1)
                end_idx = proc.end_line if proc.end_line > 0 else len(source_text.splitlines())
                proc_source = "\n".join(source_text.splitlines()[start_idx:end_idx])
                
                # Translate it
                translated_code = self._call_llm(
                    source_code=proc_source,
                    source_lang=parsed_file.source_file.language,
                    target_lang=target_lang,
                    context=global_context
                )
                translated_procs.append(translated_code)
        else:
            # No clear procedures (e.g., simple script), translate the whole thing
            translated_procs.append(self._call_llm(
                source_code=source_text,
                source_lang=parsed_file.source_file.language,
                target_lang=target_lang,
                context=global_context
            ))
            
        unit.translated_source = "\n\n".join(translated_procs)
        unit.is_complete = True
        return unit
        
    def _extract_global_context(self, parsed_file: ParsedFile) -> str:
        """Extract variables and data structures to provide context to the LLM."""
        context = []
        if parsed_file.variables:
            context.append("Variables:")
            for v in parsed_file.variables:
                context.append(f"- {v.name} ({v.properties.get('data_type', v.properties.get('picture', 'Unknown'))})")
                
        if parsed_file.data_structures:
            context.append("Data Structures (Records/Common Blocks):")
            for ds in parsed_file.data_structures:
                context.append(f"- {ds.name}")
                
        return "\n".join(context)

    def _call_llm(self, source_code: str, source_lang: LegacyLanguage, target_lang: TargetLanguage, context: str) -> str:
        """Call the LLM API to perform the translation."""
        
        prompt = f"""
You are CodePhoenix, an autonomous legacy modernization engine.
Translate the following {source_lang.name} code into idiomatic {target_lang.name}.

Context:
{context}

Source Code:
```
{source_code}
```

Provide ONLY the translated {target_lang.name} code. Do not include markdown codeblocks (```) or explanations.
"""
        
        # In a real implementation, we would call the actual LLM API here.
        # For the prototype, we'll simulate the LLM call or use a basic fallback if no key is present.
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return f"// [SIMULATED TRANSLATION]\n// API Key not found. Simulated translation of {source_lang.name} to {target_lang.name}\n\n// Original code:\n/*\n{source_code}\n*/\n"
            
        # Actual LLM call (assuming OpenAI compatible endpoint)
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
                            {"role": "system", "content": "You are an expert code translator."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.1
                    },
                    timeout=60.0
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                
                # Strip markdown blocks if the LLM ignored instructions
                if content.startswith("```"):
                    content = "\n".join(content.split("\n")[1:])
                if content.endswith("```"):
                    content = "\n".join(content.split("\n")[:-1])
                    
                return content.strip()
        except Exception as e:
            return f"// [TRANSLATION ERROR]\n// {str(e)}\n\n/*\n{source_code}\n*/\n"

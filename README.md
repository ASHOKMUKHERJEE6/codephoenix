<div align="center">
  
# 🦅 CodePhoenix

**Autonomous Legacy Modernization Engine**

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Self-Healing](https://img.shields.io/badge/Self--Healing-Active-brightgreen.svg)]()

CodePhoenix is a conceptual autonomous pipeline that intakes fifty-year-old legacy software (COBOL, Fortran, Pascal, BASIC), instantly maps its trillion-node logic using advanced graph analysis, and completely rewrites it into a modern language (Rust, Python, Go, Java) while actively repairing its own bugs in real time.

[Features](#-features) • [Architecture](#-architecture) • [Usage](#-usage) • [Supported Languages](#-supported-languages)

</div>

## ✨ Features

- 🕵️ **Intelligent Intake Scanner**: Automatically fingerprints and pre-processes legacy constraints (like COBOL fixed columns and BASIC line numbers).
- 🕸️ **Logic Mapper**: Uses structural parsers to convert legacy code into a massive `NetworkX` Directed Graph containing procedures, control flows, basic blocks, and variables.
- 🧠 **Context-Aware Translation**: Leverages configurable LLMs (OpenAI, local models) to surgically translate legacy AST structures into idiomatic modern code.
- 🛠️ **Real-Time Self-Healing Loop**: The repair engine takes the output of the translator, validates it against a native compiler (like `rustc` or `javac`), captures errors, and recursively prompts the LLM to autonomously fix its own bugs until compilation succeeds.

## 🏗️ Architecture

The CodePhoenix pipeline operates in a continuous, autonomous loop containing four decoupled pillars:

1. **Intake Engine** (`intake/`): Cleans and structurally parses ancient syntax.
2. **Logic Mapper** (`mapper/`): Builds the unified Knowledge Graph and computes cyclomatic complexity.
3. **Translation Engine** (`translator/`): Feeds context-rich chunks into the LLM.
4. **Repair Engine** (`repair/`): Validates output and runs the autonomous self-healing process.

## 🚀 Usage

You can run CodePhoenix locally on any directory containing legacy code:

```bash
# Clone the repository
git clone https://github.com/yourusername/codephoenix.git
cd codephoenix

# Install requirements
pip install networkx httpx

# Run the engine
export PYTHONPATH="."
python engine.py ./legacy_samples ./modernized_output --lang RUST
```

*(Note: Set the `OPENAI_API_KEY` environment variable for real LLM translations. Without it, the system falls back to a simulated placeholder response to demonstrate the repair loop mechanics.)*

## 🌐 Supported Languages

### Intake (Legacy)
- COBOL
- Fortran
- Pascal
- BASIC
- RPG
- Assembly
- PL/I

### Target (Modern)
- Rust
- Python
- Go
- Java
- TypeScript
- C#

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

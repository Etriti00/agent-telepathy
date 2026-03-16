# Contributing to TPCP

Thank you for your interest in contributing to TPCP! This guide will get you set up quickly.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/Etriti00/agent-telepathy.git
cd tpcp

# Create a virtual environment and install dev dependencies
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Run the test suite to verify everything works
pytest
```

For the TypeScript SDK:
```bash
cd tpcp-ts
npm install
npm run build
```

For the Go SDK:
```bash
cd tpcp-go
go mod tidy
go test ./...
```

For the Rust SDK:
```bash
cd tpcp-rs
cargo test --workspace
```

For the Java SDK:
```bash
cd tpcp-java
mvn clean package    # requires Java 21+
```

## How to Contribute

1. **Fork** the repository on GitHub
2. Create a **feature branch** (`git checkout -b feat/your-feature`)
3. Make your changes with clear, focused commits
4. Ensure all tests pass: `pytest` (Python) or `npm test` (TypeScript)
5. Open a **Pull Request** with a clear description of your changes

## What We're Looking For

- 🐛 **Bug fixes** — check the Issues tab for confirmed bugs
- ✨ **New adapters** — connect new AI frameworks (AutoGen, Semantic Kernel, etc.)
- 📖 **Documentation** — improve clarity, add real-world examples
- 🧪 **Tests** — improvements to coverage

## Code Style

- **Python:** Follow PEP 8. We use `ruff` for linting and `black` for formatting.  
  Run `ruff check tpcp/` and `black tpcp/` before committing.
- **TypeScript:** Follow the existing tsconfig; strict mode is on.

## A Note on Licensing and CLA (Contributor License Agreement)

TPCP operates under a dual-license model (AGPLv3 for open-source, and a Commercial License for enterprise). 

To ensure we can maintain this dual-license ecosystem, by submitting a Pull Request, you agree to grant the TPCP project maintainers a perpetual, worldwide, non-exclusive, transferable, royalty-free, irrevocable license to use, modify, and distribute your contributions under both the AGPLv3 license and any commercial licenses offered by the project. You retain the copyright to your own work, but you grant us the right to include it in commercial offerings.

If your contribution is for your own proprietary enterprise integration, please review [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md) first.

## Release Process

1. Ensure all SDK tests pass:
   - `cd tpcp && pytest`
   - `cd tpcp-ts && npm run build && npm test`
   - `cd tpcp-go && go test ./...`
   - `cd tpcp-rs && cargo test --workspace`
   - `cd tpcp-java && mvn test`
2. Update version in all SDK manifests (`pyproject.toml`, `package.json`, `Cargo.toml`, `pom.xml`)
3. Update `CHANGELOG.md`
4. Commit: `git commit -m "chore: release vX.Y.Z"`
5. Tag: `git tag vX.Y.Z && git push origin vX.Y.Z`
6. GitHub Actions will automatically publish to PyPI and npm

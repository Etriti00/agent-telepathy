# Contributing to TPCP

Thank you for your interest in contributing to TPCP! This guide will get you set up quickly.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/YourUsername/tpcp.git
cd tpcp/tpcp

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

## A Note on Licensing

By submitting a PR, you agree that your contributions are licensed under the same AGPLv3 license as the project. If your contribution is for enterprise/commercial integration use, please review [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md) first.

# Last Wish

A commercial card game built with Python and pygame.

> **Copyright © 2026 Angel Hernandez. All rights reserved.**
> This software is proprietary. See [LICENSE](LICENSE) for terms of use.

---

## Requirements

- [Python 3.13+](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) — Python package and project manager

## Installation

### 1. Install uv

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone the repository

```bash
git clone <repository-url>
cd last-wish
```

### 3. Install dependencies

```bash
uv sync
```

> **Note:** If you are behind a corporate proxy or get a certificate error, add `--system-certs`:
> ```bash
> uv sync --system-certs
> ```

## Running the game

```bash
uv run main.py
```

## Running the tests

```bash
# Full test suite
uv run pytest tests/

# Verbose output
uv run pytest tests/ -v

# A single file or test
uv run pytest tests/domain/test_rarity.py
uv run pytest tests/domain/test_rarity.py::TestTiers::test_five_tiers
```

## License

This game is proprietary software. It is **not** open source.  
Redistribution, modification, and commercial use by third parties are strictly prohibited.  
See the [LICENSE](LICENSE) file for the full End User License Agreement.

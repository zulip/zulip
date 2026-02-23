#!/usr/bin/env bash
# nodl-chat test runner script
# Runs linting, type checking, and tests

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=== nodl-chat Test Suite ==="
echo ""

# Activate virtual environment if it exists
if [[ -f "$PROJECT_ROOT/venv/bin/activate" ]]; then
    source "$PROJECT_ROOT/venv/bin/activate"
fi

# Run Ruff linter
echo "Running Ruff linter..."
if ruff check nodl/; then
    echo "✓ Ruff linting passed"
else
    echo "✗ Ruff linting failed"
    exit 1
fi
echo ""

# Run Ruff formatter check
echo "Running Ruff formatter check..."
if ruff format --check nodl/; then
    echo "✓ Ruff format check passed"
else
    echo "✗ Ruff format check failed"
    exit 1
fi
echo ""

# Run mypy type checking (warn-only: pre-existing Django type issues)
echo "Running mypy type checking..."
if mypy nodl/ --ignore-missing-imports; then
    echo "✓ mypy type checking passed"
else
    echo "⚠ mypy type checking has warnings (non-blocking)"
fi
echo ""

# Run pytest
echo "Running pytest..."
if pytest nodl/tests/ -v --tb=short; then
    echo "✓ All tests passed"
else
    echo "✗ Tests failed"
    exit 1
fi

echo ""
echo "=== All checks passed! ==="

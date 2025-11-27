#!/usr/bin/env bash
# nodl-chat development setup script
# Sets up local development environment

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== nodl-chat Development Setup ==="
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f2)

if [[ "$PYTHON_MAJOR" -lt 3 ]] || [[ "$PYTHON_MAJOR" -eq 3 && "$PYTHON_MINOR" -lt 10 ]]; then
    echo "ERROR: Python 3.10+ required. Found: $PYTHON_VERSION"
    exit 1
fi
echo "✓ Python version: $PYTHON_VERSION"

# Create virtual environment if it doesn't exist
VENV_DIR="$PROJECT_ROOT/venv"
if [[ ! -d "$VENV_DIR" ]]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi
echo "✓ Virtual environment ready"

# Activate virtual environment
source "$VENV_DIR/bin/activate"
echo "✓ Virtual environment activated"

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip -q

# Install dependencies
echo "Installing dependencies..."
if [[ -f "$PROJECT_ROOT/requirements.txt" ]]; then
    pip install -r "$PROJECT_ROOT/requirements.txt" -q
fi

# Install development dependencies
echo "Installing development dependencies..."
pip install pytest pytest-asyncio pytest-django ruff mypy httpx -q
echo "✓ Dependencies installed"

# Check for PostgreSQL
if command -v psql &> /dev/null; then
    echo "✓ PostgreSQL found"
else
    echo "WARNING: PostgreSQL not found. Install it to run database migrations."
fi

# Database setup (if PostgreSQL is available)
if command -v psql &> /dev/null; then
    echo ""
    echo "Database setup instructions:"
    echo "  1. Ensure PostgreSQL is running"
    echo "  2. Create database: createdb zulip"
    echo "  3. Run migrations: python manage.py migrate"
fi

# Run Django check
echo ""
echo "Running Django system check..."
cd "$PROJECT_ROOT"
if python manage.py check 2>/dev/null; then
    echo "✓ Django check passed"
else
    echo "Note: Django check may require additional configuration"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To activate the virtual environment:"
echo "  source venv/bin/activate"
echo ""
echo "To run tests:"
echo "  ./scripts/run-tests.sh"
echo ""
echo "To start development server:"
echo "  python manage.py runserver"

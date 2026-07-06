#!/bin/bash
# Developer tools for signalbox

set -e

# Prefer tools from the local venv when it exists (no activation required)
if [ -d "venv/bin" ]; then
    PATH="$(pwd)/venv/bin:$PATH"
fi

CMD="${1:-help}"

case "$CMD" in
    format)
        echo "🎨 Running black formatter..."
        black signalbox/ tests/
        echo "✅ Formatting complete!"
        ;;

    lint)
        echo "🔍 Running flake8 linter..."
        flake8 signalbox/
        echo "✅ Linting passed!"
        ;;
    
    check)
        echo "🔍 Running all checks..."
        echo ""
        echo "1. Black formatting check..."
        black --check signalbox/ tests/
        echo "✅ Format check passed!"
        echo ""
        echo "2. Flake8 linting..."
        flake8 signalbox/
        echo "✅ Lint check passed!"
        echo ""
        echo "3. Running tests..."
        ./test_all.sh
        echo ""
        echo "✅ All checks passed!"
        ;;
    
    test)
        echo "🧪 Running tests..."
        ./test_all.sh
        ;;
    
    install-dev)
        echo "📦 Installing development dependencies..."
        pip install -e ".[dev]"
        echo "✅ Development dependencies installed!"
        ;;
    
    help|*)
        echo "SignalBox Developer Tools"
        echo ""
        echo "Usage: ./dev.sh [command]"
        echo ""
        echo "Commands:"
        echo "  format       - Format code with black"
        echo "  lint         - Run flake8 linter"
        echo "  check        - Run all checks (format, lint, test)"
        echo "  test         - Run test suite"
        echo "  install-dev  - Install development dependencies"
        echo "  help         - Show this help message"
        echo ""
        echo "Examples:"
        echo "  ./dev.sh format      # Format all code"
        echo "  ./dev.sh check       # Run all checks before commit"
        echo ""
        ;;
esac

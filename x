#!/bin/sh
set -e
cd "$(dirname "$0")"

cmd_setup() {
    echo "Installing uv (if missing)..."
    command -v uv >/dev/null || brew install uv

    echo "Creating .venv (if missing)..."
    test -d .venv || uv venv

    echo "Installing core dependencies..."
    uv pip install -r requirements.txt

    for demo_req in domains/*/demo/requirements.txt; do
        [ -f "$demo_req" ] || continue
        domain=$(echo "$demo_req" | cut -d/ -f2)
        echo "Installing demo dependencies for $domain..."
        uv pip install -r "$demo_req"
    done

    echo "Installing OPA (if missing)..."
    command -v opa >/dev/null || brew install opa

    echo "✓ Setup complete"
}

cmd_generate_schema() {
    python tools/civil_schema.py
}

case "$1" in
    setup)           cmd_setup ;;
    generate-schema) cmd_generate_schema ;;
    *)               exec python x.py "$@" ;;
esac

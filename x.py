#!/usr/bin/env python3
"""
xlator CLI — replaces the Makefile.

Usage:
  ./x <action> [domain] [module]

Actions (domain + module required):
  validate   <domain> <module>   Validate CIVIL YAML
  transpile  <domain> <module>   Generate Rego from CIVIL
  test       <domain> <module>   Start OPA, run tests, stop OPA
  demo       <domain> <module>   Start OPA + FastAPI demo (foreground)
  graph      <domain> <module>   Generate computation graph
  pipeline   <domain> <module>   validate → transpile → test

Actions (no domain/module):
  list                           Show all domain/module pairs
"""

import argparse
import glob
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from rich.console import Console
from rich.table import Table

ROOT = Path(__file__).parent
_console = Console()
_err_console = Console(stderr=True)


def _print_ok(msg):
    _console.print(f"[green]✓[/green] {msg}")


def _print_err(msg):
    _err_console.print(f"[red]✗[/red] {msg}")


def _print_info(msg):
    _console.print(msg)


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def resolve_paths(domain, module):
    base = ROOT / "domains" / domain
    return {
        "civil":    base / "specs" / f"{module}.civil.yaml",
        "rego":     base / "output" / f"{module}.rego",
        "tests":    base / "specs" / "tests" / f"{module}_tests.yaml",
        "package":  f"{domain}.{module}",
        "opa_path": f"/v1/data/{domain}/{module}/decision",
        "demo_sh":  base / "output" / f"demo-{module}" / "start.sh",
        "demo_req": base / "output" / f"demo-{module}" / "requirements.txt",
    }


def require_file(path, label):
    if not path.exists():
        _print_err(f"{label} not found: {path}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# OPA lifecycle
# ---------------------------------------------------------------------------

def start_opa(rego_path, port=8181):
    """Start OPA server as a subprocess. Poll health endpoint. Return Popen."""
    proc = subprocess.Popen(
        ["opa", "run", "--server", "--addr", f":{port}", str(rego_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    health_url = f"http://localhost:{port}/health"
    for _ in range(10):
        try:
            urllib.request.urlopen(health_url, timeout=1)
            return proc
        except Exception:
            time.sleep(0.5)
    proc.kill()
    _print_err(
        f"OPA failed to start within 5 seconds. "
        f"Port {port} may already be in use, or OPA is not installed."
    )
    sys.exit(1)


def stop_opa(proc):
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


# ---------------------------------------------------------------------------
# Subprocess helper
# ---------------------------------------------------------------------------

def run(cmd, **kwargs):
    """Run a command. Exit 1 on non-zero return code."""
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        sys.exit(result.returncode)


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def cmd_validate(domain, module):
    paths = resolve_paths(domain, module)
    require_file(paths["civil"], "CIVIL spec")
    run([sys.executable, str(ROOT / "tools" / "validate_civil.py"), str(paths["civil"])])


def cmd_transpile(domain, module):
    paths = resolve_paths(domain, module)
    require_file(paths["civil"], "CIVIL spec")
    paths["rego"].parent.mkdir(parents=True, exist_ok=True)
    run([
        sys.executable, str(ROOT / "tools" / "transpile_to_opa.py"),
        str(paths["civil"].relative_to(ROOT)),
        str(paths["rego"].relative_to(ROOT)),
        "--package", paths["package"],
    ], cwd=str(ROOT))


def cmd_test(domain, module):
    paths = resolve_paths(domain, module)
    require_file(paths["rego"], "Rego file (run transpile first)")
    require_file(paths["tests"], "Test cases")
    _print_info(f"Starting OPA server with {paths['rego'].name}...")
    opa = start_opa(paths["rego"])
    _print_ok("OPA ready")
    sys.stdout.flush()
    try:
        result = subprocess.run([
            sys.executable, str(ROOT / "tools" / "run_tests.py"),
            str(paths["tests"]),
            "--opa-path", paths["opa_path"],
        ])
        sys.exit(result.returncode)
    finally:
        stop_opa(opa)
        _print_info("OPA stopped")


def cmd_demo(domain, module):
    paths = resolve_paths(domain, module)
    if not paths["demo_sh"].exists():
        _print_err(
            f"No demo script found at {paths['demo_sh']}. "
            f"Create domains/{domain}/output/demo-{module}/start.sh to enable the demo."
        )
        sys.exit(1)
    _print_info(f"Starting demo for {domain}/{module}...")
    run(["bash", str(paths["demo_sh"])])


def cmd_graph(domain, module):
    paths = resolve_paths(domain, module)
    require_file(paths["civil"], "CIVIL spec")
    run([sys.executable, str(ROOT / "tools" / "computation_graph.py"), str(paths["civil"])])


def cmd_pipeline(domain, module):
    """validate → transpile → test. Stops on first failure."""
    _print_info(f"Pipeline: {domain}/{module}")
    cmd_validate(domain, module)
    cmd_transpile(domain, module)
    cmd_test(domain, module)


def cmd_list():
    pattern = str(ROOT / "domains" / "*" / "specs" / "*.civil.yaml")
    rows = []
    for path in sorted(glob.glob(pattern)):
        parts = Path(path).parts
        domain = parts[-3]
        module = parts[-1].removesuffix(".civil.yaml")
        rows.append((domain, module))

    if not rows:
        _print_info("No domain/module pairs found under domains/*/specs/")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Domain")
    table.add_column("Module")
    for domain, module in rows:
        table.add_row(domain, module)
    _console.print(table)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="x",
        description="xlator CLI — run pipeline actions for any domain/module",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  ./x list
  ./x validate snap eligibility
  ./x pipeline snap eligibility
  ./x test ak_doh apa_adltc
        """,
    )
    sub = parser.add_subparsers(dest="action", required=True, metavar="action")

    for action, help_text in [
        ("validate",  "Validate CIVIL YAML"),
        ("transpile", "Generate Rego from CIVIL"),
        ("test",      "Start OPA, run tests, stop OPA"),
        ("demo",      "Start OPA + FastAPI demo (foreground)"),
        ("graph",     "Generate computation graph"),
        ("pipeline",  "validate → transpile → test"),
    ]:
        p = sub.add_parser(action, help=help_text)
        p.add_argument("domain", help="Domain name (e.g. snap, ak_doh)")
        p.add_argument("module", help="Module name (e.g. eligibility, apa_adltc)")

    sub.add_parser("list",            help="Show all domain/module pairs")

    args = parser.parse_args()

    match args.action:
        case "validate":        cmd_validate(args.domain, args.module)
        case "transpile":       cmd_transpile(args.domain, args.module)
        case "test":            cmd_test(args.domain, args.module)
        case "demo":            cmd_demo(args.domain, args.module)
        case "graph":           cmd_graph(args.domain, args.module)
        case "pipeline":        cmd_pipeline(args.domain, args.module)
        case "list":            cmd_list()


if __name__ == "__main__":
    main()

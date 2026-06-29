#!/usr/bin/env python3
"""Run the full algo-trade stack locally -- one command.

What this script does, in order:

  1. Checks Python 3.11+ (the project requires it).
  2. Checks Node + npm are installed (needed for the frontend).
     Skipped when running with --backend-only.
  3. Verifies the algo_trade package is importable. If not, runs
     `pip install -e ".[dev]"` once and re-checks.
  4. Verifies frontend/node_modules exists. If not, runs `npm install`
     in `frontend/` once.
  5. Creates a repo-root `.env` from `.env.example` on first run, so the
     backend's `load_env()` and Vite's `envDir: '..'` both find one.
  6. Starts the FastAPI backend (`python -m backend.api`) on :8000.
  7. Starts the Vite dev server in `frontend/` on :5173.
  8. Opens http://localhost:5173 in your default browser.
  9. Streams both processes' output to this terminal, prefixed with
     [api] / [web] so you can tell who said what.
 10. On Ctrl-C (or if one process exits), terminates the other cleanly.

You do NOT need an Anthropic API key to run the stack:

  - With no API key, the backend boots in read-only mode. Live
    extraction (POST /api/v1/extract) returns 503 with a clear error,
    but the dashboard, explorer, and per-material curves all work
    against whatever the SQLite buffer already has.
  - The frontend falls back to bundled mock JSON if the live API isn't
    reachable, so even with the backend down you see a working UI.

Common invocations:
    python dev.py                  # full stack, opens browser
    python dev.py --no-open        # full stack, no browser
    python dev.py --backend-only   # just the API (for curl / Postman)
    python dev.py --frontend-only  # just the UI (mock data only)
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

REPO = Path(__file__).resolve().parent
IS_WIN = os.name == "nt"


# --------------------------------------------------------------------------- #
# Pre-flight checks
# --------------------------------------------------------------------------- #


def _die(msg: str) -> "None":
    sys.stderr.write(f"\n[dev.py] {msg}\n")
    sys.exit(1)


def check_python() -> None:
    if sys.version_info < (3, 11):
        _die(
            f"need Python 3.11+, you have "
            f"{sys.version_info.major}.{sys.version_info.minor}."
        )


def check_node() -> None:
    if shutil.which("npm") is None:
        _die(
            "npm not found on PATH. Install Node 20+ from "
            "https://nodejs.org and retry, or run with --backend-only."
        )


def ensure_python_deps() -> None:
    try:
        import algo_trade  # noqa: F401
        return
    except ImportError:
        pass
    print("[dev.py] installing Python deps (pip install -e \".[dev]\")...")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-e", ".[dev]"],
        cwd=str(REPO),
    )


def ensure_frontend_deps() -> None:
    if (REPO / "frontend" / "node_modules").exists():
        return
    print("[dev.py] installing frontend deps (npm install)...")
    subprocess.check_call(
        ["npm", "install"],
        cwd=str(REPO / "frontend"),
        shell=IS_WIN,
    )


def ensure_env_file() -> None:
    env = REPO / ".env"
    if env.exists():
        return
    example = REPO / ".env.example"
    if not example.exists():
        return
    print("[dev.py] copying .env.example -> .env (edit it if you want)")
    env.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Process management
# --------------------------------------------------------------------------- #


def _stream(proc: subprocess.Popen, prefix: str) -> None:
    """Pipe a child process's combined output to our stdout, line by line."""
    assert proc.stdout is not None
    for line in iter(proc.stdout.readline, ""):
        if not line:
            break
        sys.stdout.write(f"{prefix} {line}")
        sys.stdout.flush()


def _spawn(cmd: list[str], cwd: Path, prefix: str) -> subprocess.Popen:
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        shell=IS_WIN,   # npm.cmd / python.exe resolution on Windows
    )
    threading.Thread(target=_stream, args=(proc, prefix), daemon=True).start()
    return proc


def _terminate_tree(proc: subprocess.Popen) -> None:
    """Cross-platform best-effort terminate -> kill."""
    if proc.poll() is not None:
        return
    try:
        if IS_WIN:
            proc.terminate()
        else:
            proc.send_signal(signal.SIGTERM)
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--backend-only", action="store_true",
        help="Don't start the frontend (and skip npm checks).",
    )
    parser.add_argument(
        "--frontend-only", action="store_true",
        help="Don't start the backend.",
    )
    parser.add_argument(
        "--no-open", action="store_true",
        help="Don't auto-open the browser.",
    )
    args = parser.parse_args()

    if args.backend_only and args.frontend_only:
        _die("--backend-only and --frontend-only are mutually exclusive")

    # Pre-flight
    check_python()
    if not args.backend_only:
        check_node()
    ensure_python_deps()
    if not args.backend_only:
        ensure_frontend_deps()
    ensure_env_file()

    # Spawn
    processes: list[tuple[str, subprocess.Popen]] = []

    if not args.frontend_only:
        api = _spawn(
            [sys.executable, "-m", "backend.api"],
            cwd=REPO,
            prefix="[api]",
        )
        processes.append(("api", api))

        # Brief head start so the first frontend request lands after the API
        # has bound the port. Vite handles a dead backend fine, but better UX.
        if not args.backend_only:
            time.sleep(1.5)

    if not args.backend_only:
        web = _spawn(
            ["npm", "run", "dev"],
            cwd=REPO / "frontend",
            prefix="[web]",
        )
        processes.append(("web", web))

    if not args.no_open and not args.backend_only:
        # Vite takes ~2s to bind; open after a small delay.
        threading.Timer(3.0, lambda: webbrowser.open("http://localhost:5173")).start()

    # Print a banner so the user knows what they're looking at.
    banner_url = "http://localhost:5173" if not args.backend_only else "http://localhost:8000"
    print()
    print("=" * 60)
    print(f" algo-trade dev stack up  ->  {banner_url}")
    print(" press Ctrl-C to stop everything")
    print("=" * 60)
    print()

    # Wait for either a child exit (= unhealthy) or Ctrl-C.
    try:
        while True:
            time.sleep(0.5)
            for name, proc in processes:
                if proc.poll() is not None:
                    print(
                        f"\n[dev.py] {name} exited with code {proc.returncode}; "
                        f"shutting down the rest.",
                        file=sys.stderr,
                    )
                    raise KeyboardInterrupt
    except KeyboardInterrupt:
        print("\n[dev.py] stopping...")
    finally:
        for _, proc in processes:
            _terminate_tree(proc)
        # Grace period, then escalate to kill on anything still alive.
        deadline = time.time() + 5.0
        while time.time() < deadline:
            if all(p.poll() is not None for _, p in processes):
                break
            time.sleep(0.1)
        for name, proc in processes:
            if proc.poll() is None:
                try:
                    proc.kill()
                except Exception:
                    pass
                print(f"[dev.py] force-killed {name}", file=sys.stderr)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# ///
"""Generate the environment for docker-compose.coolify.yml.

Prints KEY=value lines ready to paste into Coolify's environment editor, and
optionally writes them to a file. Secrets already present in an existing file
are kept: rotating POSTGRES_PASSWORD after the database volume is initialized
locks the cache out of its own metadata. Runners need no secret: the cache
accepts anonymous requests on its private network.

    uv run deploy/coolify/generate_env.py              # print to stdout
    uv run deploy/coolify/generate_env.py -o .env      # write (or update) .env
"""

from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

# Hex secrets only: compose interpolates them into a postgres:// URL, so they
# must need no URL escaping.
SECRETS = {
    "POSTGRES_PASSWORD": lambda: secrets.token_hex(32),
}

DEFAULTS = {
    # Host loopback port for debugging; runners use http://mbx-cache:7543.
    "MBX_CACHE_HOST_PORT": "7543",
    "MBX_CACHE_DATABASE_MAX_CONNECTIONS": "32",
    "MBX_CACHE_MAX_BLOB_BYTES": str(5 * 1024**3),
    "MBX_CACHE_RETENTION_DAYS": "30",
    "MBX_CACHE_SWEEP_INTERVAL_S": "21600",
    "RUST_LOG": "mbx_cache=info,tower_http=info",
}


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-o", "--output", type=Path, help="write to this file, keeping its existing values")
    parser.add_argument("--rotate", action="append", default=[], metavar="KEY", choices=sorted(SECRETS),
                        help="regenerate this secret even if the file has one (repeatable)")
    args = parser.parse_args()

    existing = read_env(args.output) if args.output else {}
    env: dict[str, str] = {}
    for key, generate in SECRETS.items():
        env[key] = existing[key] if existing.get(key) and key not in args.rotate else generate()
    for key, default in DEFAULTS.items():
        env[key] = existing.get(key) or default
    # Preserve anything else the operator added by hand.
    env.update({key: value for key, value in existing.items() if key not in env})

    rendered = "".join(f"{key}={value}\n" for key, value in env.items())
    if args.output:
        args.output.write_text(rendered)
        args.output.chmod(0o600)
        print(f"wrote {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(rendered)

    print(
        "\nRunner side (containers joined to the external `mbx-cache` network):\n"
        "  mbx:  [remote] url = \"http://mbx-cache:7543\", namespace = \"<project>\", no token",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

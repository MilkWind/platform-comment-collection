"""Regenerate the danmaku protobuf bindings from the checked-in .proto.

Run from the repo root:  uv run python scripts/gen_proto.py

The generated file is checked in so copy-the-core users do not need the
protobuf compiler. The runtime pins ``protobuf>=7.35,<8`` and grpcio-tools is a
matching dev dependency: generated-by-newer-than-runtime fails at import, so
regenerate only with the version pinned in pyproject.toml.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROTO_DIR = ROOT / "skills" / "bilibili" / "core" / "bilicrawl" / "proto"


def main() -> int:
    if not (PROTO_DIR / "dm_v1.proto").exists():
        print(f"proto not found: {PROTO_DIR / 'dm_v1.proto'}", file=sys.stderr)
        return 1
    cmd = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        f"-I{PROTO_DIR}",
        f"--python_out={PROTO_DIR}",
        str(PROTO_DIR / "dm_v1.proto"),
    ]
    print("running:", " ".join(cmd))
    result = subprocess.run(cmd, check=False)
    if result.returncode == 0:
        print(f"wrote {PROTO_DIR / 'dm_v1_pb2.py'}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

"""Scan an explicit public-file allowlist. Never load runtime files or credentials."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
FILES = ["README.md", "LICENSE", "app.py", "worker.py", "requirements.txt", ".env.example", ".gitignore",
         "frontend/heartbeat-client.js", "examples/index.html", "examples/demo.js",
         "deploy/nginx.conf.example", "deploy/heartbeat-api.service", "deploy/heartbeat-worker.service",
         "tests/test_backend.py", "tests/test_client.mjs", "docs/PRINCIPLES.md", ".github/workflows/test.yml",
         "tools/privacy_scan.py"]


def scan():
    signatures = [r"gsk_[A-Za-z0-9]{20,}", r"sk-[A-Za-z0-9]{20,}",
                  r"gh[pousr]_[A-Za-z0-9]{20,}", r"github_pat_[A-Za-z0-9_]{20,}",
                  r"-----BEGIN [A-Z ]*PRIVATE KEY-----", r"[A-Za-z]:\\Users\\[^\s]+",
                  r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])"]
    failures = []
    for name in FILES:
        path = ROOT / name
        if not path.is_file() or path.is_symlink():
            failures.append(name)
            continue
        text = path.read_text(encoding="utf-8").replace("127.0.0.1", "LOOPBACK")
        if any(re.search(pattern, text) for pattern in signatures):
            failures.append(name)
    if failures:
        print("Privacy scan failed in:", ", ".join(failures))
        return 1
    print("PASS privacy scan:", len(FILES), "allowlisted text files; no runtime data selected")
    return 0


if __name__ == "__main__":
    sys.exit(scan())

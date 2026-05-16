from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

CONFLICT_MARKER_RE = re.compile(r"<<<<<<<|=======|>>>>>>>")
AI_HYPE_RE = re.compile(r"AI가|AI 예측|AI 분석|AI analysis")
LLM_NUMERIC_RE = re.compile(r"fair_value|buy_zone|sell_zone|valuation_methods")

CONFLICT_FILES = (
    "README.md",
    "CHANGELOG.md",
    "API_CONTRACT.md",
    "ARCHITECTURE.md",
    "DESIGN_BIBLE.md",
    "AGENTS.md",
)

AI_COPY_ROOTS = (
    "README.md",
    "frontend",
    "backend/app",
)

LLM_NUMERIC_FILES = (
    "backend/app/analysis/prompts.py",
    "backend/app/analysis/stock_analyzer.py",
)

STALE_API_CONTRACT_PATTERNS = (
    re.compile(r"`POST /api/watchlist`"),
    re.compile(r"`PATCH /api/portfolio/profile`"),
    re.compile(r"`GET /api/portfolio/holdings`"),
    re.compile(r"`DELETE /api/portfolio/holdings/\{ticker\}`"),
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def iter_source_files(root: Path):
    if root.is_file():
        yield root
        return
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".md", ".py", ".ts", ".tsx"}:
            yield path


def check_regex_absent(paths: tuple[str, ...], pattern: re.Pattern[str], label: str) -> list[str]:
    failures: list[str] = []
    for raw_path in paths:
        path = ROOT / raw_path
        if not path.exists():
            continue
        for file_path in iter_source_files(path):
            text = read_text(file_path)
            match = pattern.search(text)
            if match:
                rel = file_path.relative_to(ROOT)
                failures.append(f"{label}: {rel} contains '{match.group(0)}'")
    return failures


def load_backend_version() -> str:
    text = read_text(ROOT / "backend/app/version.py")
    match = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', text)
    return match.group(1) if match else ""


def load_frontend_versions() -> tuple[str, str, str]:
    package = json.loads(read_text(ROOT / "frontend/package.json"))
    lock = json.loads(read_text(ROOT / "frontend/package-lock.json"))
    return (
        str(package.get("version", "")),
        str(lock.get("version", "")),
        str((lock.get("packages") or {}).get("", {}).get("version", "")),
    )


def check_version_sync() -> list[str]:
    failures: list[str] = []
    backend_version = load_backend_version()
    frontend_version, lock_version, lock_root_version = load_frontend_versions()
    expected = {backend_version, frontend_version, lock_version, lock_root_version}
    if len(expected) != 1 or not backend_version:
        failures.append(
            "version sync: backend/app/version.py, frontend/package.json, "
            "frontend/package-lock.json versions differ"
        )
        return failures

    readme = read_text(ROOT / "README.md")
    changelog = read_text(ROOT / "CHANGELOG.md")
    version_label = f"v{backend_version}"
    if f"현재 릴리즈: `{version_label}`" not in readme:
        failures.append(f"version sync: README.md current release is not {version_label}")
    if not re.search(rf"^## {re.escape(version_label)} - ", changelog, flags=re.MULTILINE):
        failures.append(f"version sync: CHANGELOG.md top release does not include {version_label}")
    return failures


def check_api_contract() -> list[str]:
    text = read_text(ROOT / "API_CONTRACT.md")
    failures = []
    for stale in STALE_API_CONTRACT_PATTERNS:
        if stale.search(text):
            failures.append(f"api contract drift: stale route remains '{stale.pattern}'")
    return failures


def check_frontend_check_script() -> list[str]:
    package = json.loads(read_text(ROOT / "frontend/package.json"))
    check_script = str((package.get("scripts") or {}).get("check", ""))
    required = ("npm run test", "npm run build", "tsc --noEmit")
    missing = [item for item in required if item not in check_script]
    if missing:
        return [f"frontend check script: missing {' / '.join(missing)}"]
    return []


def collect_failures() -> list[str]:
    failures: list[str] = []
    failures.extend(check_regex_absent(CONFLICT_FILES, CONFLICT_MARKER_RE, "conflict marker"))
    failures.extend(check_regex_absent(AI_COPY_ROOTS, AI_HYPE_RE, "AI hype copy"))
    failures.extend(check_regex_absent(LLM_NUMERIC_FILES, LLM_NUMERIC_RE, "LLM numeric prompt"))
    failures.extend(check_api_contract())
    failures.extend(check_frontend_check_script())
    failures.extend(check_version_sync())
    return failures


def main() -> int:
    failures = collect_failures()
    if failures:
        print("[evaluation-gate] failures detected:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("[evaluation-gate] all score-report static gates passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

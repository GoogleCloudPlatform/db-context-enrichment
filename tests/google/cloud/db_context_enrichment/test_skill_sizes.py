import re
from pathlib import Path

MAX_SKILL_FILE_BYTES = 24_000
REPO_ROOT = Path(__file__).resolve().parents[4]
SKILLS_DIR = REPO_ROOT / "plugin" / "skills"


def test_all_skill_markdown_files_under_24kb():
    """Ensure every skill and reference markdown file stays below Antigravity's 24 KB truncation limit."""
    md_files = sorted(SKILLS_DIR.rglob("*.md"))
    assert md_files, f"No markdown files found under {SKILLS_DIR}"

    oversized = []
    for md_file in md_files:
        size_bytes = md_file.stat().st_size
        if size_bytes >= MAX_SKILL_FILE_BYTES:
            rel_path = md_file.relative_to(REPO_ROOT)
            oversized.append(
                f"{rel_path} ({size_bytes} bytes >= {MAX_SKILL_FILE_BYTES} bytes)"
            )

    assert not oversized, (
        "Skill markdown files must be < 24,000 bytes to prevent client truncation:\n  - "
        + "\n  - ".join(oversized)
    )


def test_skill_markdown_relative_links_exist():
    """Ensure all relative markdown links across skill and reference files resolve to existing files."""
    link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    broken_links = []

    for md_file in sorted(SKILLS_DIR.rglob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        for match in link_pattern.finditer(text):
            target = match.group(1).strip()
            if (
                not target
                or target.startswith(("http://", "https://", "mailto:", "#"))
                or "<" in target
                or ">" in target
            ):
                continue
            target_path = target.split("#", 1)[0]
            if not target_path:
                continue
            resolved = (md_file.parent / target_path).resolve()
            if not resolved.exists():
                rel_src = md_file.relative_to(REPO_ROOT)
                broken_links.append(f"{rel_src} -> {target}")

    assert not broken_links, (
        "Broken relative markdown links in plugin/skills/:\n  - "
        + "\n  - ".join(broken_links)
    )

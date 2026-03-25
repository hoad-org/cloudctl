import re
import sys
from pathlib import Path

# Constraints for mandatory visual coverage
DIAGRAM_REQUIRED_PREFIXES = ("arch-", "lifecycle-", "security-")


def has_mermaid(content: str) -> bool:
    return "```mermaid" in content


def has_image(content: str) -> bool:
    return "![" in content


def strip_non_mermaid_fences(content: str) -> str:
    """
    Remove all fenced code blocks that are NOT Mermaid blocks.
    This prevents bash/yaml/json examples from breaking Mermaid validation.
    """
    return re.sub(
        r"(?ms)^```(?!mermaid)[^\n]*\n.*?\n^```",
        "",
        content,
    )


def lint():
    root = Path(__file__).resolve().parents[2]
    wiki_dir = root / "docs" / "wiki"
    image_dir = wiki_dir / "images"
    diag_src_dir = root / "diagrams-src"
    errors = []

    if not wiki_dir.exists():
        print(f"❌ Wiki directory not found at {wiki_dir}")
        sys.exit(1)

    md_files = list(wiki_dir.glob("*.md"))

    # Home.md must exist
    if not (wiki_dir / "Home.md").exists():
        errors.append("❌ DOCS-REQ-01: Wiki requires Home.md as the landing page.")

    for md_file in md_files:
        content = md_file.read_text()
        filename = md_file.name
        rel_path = md_file.relative_to(root)

        # Enforce diagrams where required
        if filename.startswith(DIAGRAM_REQUIRED_PREFIXES):
            if not (has_mermaid(content) or has_image(content)):
                errors.append(
                    f"❌ {filename}: Diagram required (Mermaid or image) but none found."
                )

        # Validate image references
        image_matches = re.findall(r"!\[.*?\]\((images/[^)]+)\)", content)
        for match in image_matches:
            img_filename = Path(match).name
            if not (image_dir / img_filename).exists():
                errors.append(
                    f"❌ {filename}: Referenced image missing in filesystem: {match}"
                )

        # ---- Mermaid validation (correct) ----
        sanitized = strip_non_mermaid_fences(content)

        mermaid_blocks = re.findall(
            r"(?ms)^```mermaid\s*\n.*?\n^```",
            sanitized,
        )

        mermaid_openings = sanitized.count("```mermaid")
        if mermaid_openings != len(mermaid_blocks):
            errors.append(f"❌ Malformed Mermaid fencing in {rel_path}.")

    # Source parity: YAML → PNG
    for yaml_file in diag_src_dir.glob("*.yaml"):
        expected_png = f"diag-arch-{yaml_file.stem}.png"
        if not (image_dir / expected_png).exists():
            errors.append(
                f"❌ BUG-03: Source '{yaml_file.name}' exists but '{expected_png}' is missing."
            )

    if errors:
        print("\n".join(errors))
        sys.exit(1)

    print("✅ Documentation integrity verified.")


if __name__ == "__main__":
    lint()

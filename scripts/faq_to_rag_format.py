#!/usr/bin/env python3
"""
Normalize FAQ CSV files into RAG-friendly Markdown (one block per Q&A).
Run from repo root: python scripts/faq_to_rag_format.py

Output: data/FAQs/processed/*.md — upload these via the RAG pipeline, not the raw CSVs.
"""
import csv
import os
import re
from pathlib import Path

# Base paths (script may be run from repo root or scripts/)
REPO_ROOT = Path(__file__).resolve().parent.parent
FAQS_DIR = REPO_ROOT / "data" / "FAQs"
OUT_DIR = REPO_ROOT / "data" / "FAQs" / "processed"


def _normalize_text(s: str) -> str:
    if s is None or (isinstance(s, float) and (s != s)):  # NaN
        return ""
    s = str(s).strip()
    # Collapse multiple newlines to double; clean whitespace
    s = re.sub(r"\n\s*\n\s*\n+", "\n\n", s)
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def _row_to_block(category: str, question: str, answer: str, source: str, extra: str = "") -> str:
    """One FAQ as a single RAG-friendly block."""
    lines = []
    if category:
        lines.append(f"## [{category}]")
    lines.append(f"**Question:** {_normalize_text(question)}")
    lines.append("")
    lines.append(f"**Answer:**")
    lines.append(_normalize_text(answer))
    if source:
        lines.append("")
        lines.append(f"*Source: {_normalize_text(source)}*")
    if extra:
        lines.append("")
        lines.append(extra.strip())
    return "\n".join(lines)


def load_csv(path: Path) -> list[dict]:
    """Load CSV with headers; return list of dicts."""
    rows = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({k.strip(): v for k, v in row.items() if k})
    return rows


def process_general_faq(path: Path) -> list[str]:
    # Columns: Category, Question, Possible Answer, Source
    rows = load_csv(path)
    blocks = []
    category = ""
    for row in rows:
        cat = _normalize_text(row.get("Category", ""))
        if cat:
            category = cat
        q = _normalize_text(row.get("Question", ""))
        a = _normalize_text(row.get("Possible Answer", ""))
        src = _normalize_text(row.get("Source", ""))
        if not q and not a:
            continue
        if not q:
            q = "(No question text)"
        if not a:
            a = "(No answer text)"
        blocks.append(_row_to_block(category, q, a, src))
    return blocks


def process_onboarding_faq(path: Path) -> list[str]:
    # Columns: Category, Typical Questions, Chatbot Response, Action/Link, Escalation Rule
    rows = load_csv(path)
    blocks = []
    category = ""
    for row in rows:
        cat = _normalize_text(row.get("Category", ""))
        if cat:
            category = cat
        q = _normalize_text(row.get("Typical Questions", ""))
        a = _normalize_text(row.get("Chatbot Response", ""))
        action = _normalize_text(row.get("Action/Link", ""))
        escalation = _normalize_text(row.get("Escalation Rule", ""))
        extra_parts = []
        if action:
            extra_parts.append(f"*Action/Link:* {action}")
        if escalation:
            extra_parts.append(f"*Escalation:* {escalation}")
        extra = "\n".join(extra_parts) if extra_parts else ""
        if not q and not a:
            continue
        if not q:
            q = "(No question text)"
        if not a:
            a = "(No answer text)"
        blocks.append(_row_to_block(category, q, a, "", extra))
    return blocks


def process_post_joining_faq(path: Path) -> list[str]:
    # Columns: Category, Typical Questions, Chatbot Response, Source
    rows = load_csv(path)
    blocks = []
    category = ""
    for row in rows:
        cat = _normalize_text(row.get("Category", ""))
        if cat:
            category = cat
        q = _normalize_text(row.get("Typical Questions", ""))
        a = _normalize_text(row.get("Chatbot Response", ""))
        src = _normalize_text(row.get("Source", ""))
        if not q and not a:
            continue
        if not q:
            q = "(No question text)"
        if not a:
            a = "(No answer text)"
        blocks.append(_row_to_block(category, q, a, src))
    return blocks


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    configs = [
        ("General FAQs-Table 1.csv", process_general_faq, "General_FAQs.md"),
        ("Onboarding FAQ-Table 1.csv", process_onboarding_faq, "Onboarding_FAQ.md"),
        ("Post Joining FAQs-Table 1.csv", process_post_joining_faq, "Post_Joining_FAQs.md"),
    ]

    all_blocks = []
    for filename, processor, out_name in configs:
        path = FAQS_DIR / filename
        if not path.exists():
            print(f"Skip (not found): {path}")
            continue
        blocks = processor(path)
        body = "\n\n---\n\n".join(blocks)
        out_path = OUT_DIR / out_name
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"# {out_name.replace('.md', '').replace('_', ' ')}\n\n")
            f.write(body)
        print(f"Wrote {len(blocks)} FAQs -> {out_path}")
        all_blocks.extend(blocks)

    # Optional: one combined file
    combined_path = OUT_DIR / "All_FAQs_Combined.md"
    with open(combined_path, "w", encoding="utf-8") as f:
        f.write("# All FAQs (General, Onboarding, Post Joining)\n\n")
        f.write("\n\n---\n\n".join(all_blocks))
    print(f"Wrote combined {len(all_blocks)} FAQs -> {combined_path}")
    print("\nNext: Upload the .md file(s) under data/FAQs/processed/ via your RAG pipeline (do not upload the raw CSVs).")


if __name__ == "__main__":
    main()

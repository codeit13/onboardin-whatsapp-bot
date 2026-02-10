# FAQ Documents – RAG Ingestion Guide

## Summary

**Do not upload the raw CSV files as-is.** The pipeline’s generic CSV handling turns each row into key-value text and then splits by character count. That mixes columns, can split Q&A pairs across chunks, and hurts retrieval. **Normalize the FAQs into a single, consistent text format first, then ingest the generated file(s) via the existing RAG pipeline.**

---

## 1. FAQ files overview

| File | Columns | Notes |
|------|--------|--------|
| **General FAQs-Table 1.csv** | Category, Question, Possible Answer, Source | Clear Q&A. Some empty Category (inherit from above). Long multi-line answers (e.g. rewards, DEI). |
| **Onboarding FAQ-Table 1.csv** | Category, Typical Questions, Chatbot Response, Action/Link, Escalation Rule | “Typical Questions” can be several questions in one cell. Extra columns: links and escalation rules. |
| **Post Joining FAQs-Table 1.csv** | Category, Typical Questions, Chatbot Response, Source | Same question/response pattern as Onboarding; some empty Category. |

Issues for RAG if used raw:

- **Multiple columns** → Chunks contain “Category: … Question: … Answer: … Source: …” in one blob; retrieval and LLM see mixed structure.
- **Different column names** → “Possible Answer” vs “Chatbot Response” vs “Typical Questions” vs “Question” → no consistent schema.
- **Character-based chunking** → Default pipeline concatenates all rows then splits by ~1000 chars, so one chunk can contain parts of several FAQs or half an answer.
- **Action/Link, Escalation Rule** → Useful for bots but noisy for pure semantic search; better as optional context inside a single answer block.

So: **improve format first, then insert.**

---

## 2. Recommended approach

1. **Normalize**  
   - One logical “block” per FAQ: **Question** + **Answer** (required).  
   - Optionally in the same block: **Category**, **Source**, and for Onboarding, **Action/Link** or **Escalation** folded into the answer text if you want them in RAG.

2. **Produce RAG-friendly text**  
   - The script outputs Markdown with blocks separated by `---`.  
   - The pipeline **chunks FAQ-style Markdown as 1 chunk per FAQ** (it detects `\n\n---\n\n` and `**Question:**` and splits on `---`). So each retrieval chunk is one full Q&A.

3. **Ingest via existing pipeline**  
   - Upload the **normalized** `.md` file(s) from `data/FAQs/processed/` via your RAG “add document” API or UI.  
   - Do **not** upload the original CSVs.

---

## 3. Using the normalization script

From repo root:

```bash
python scripts/faq_to_rag_format.py
```

This script:

- Reads the three CSVs from `data/FAQs/`.
- Maps columns to a common schema: **Category**, **Question**, **Answer**, **Source** (and optionally **Action/Link**, **Escalation** for Onboarding).
- Fills forward empty Category.
- Writes one RAG-friendly Markdown file per CSV (and optionally one combined file) under `data/FAQs/processed/`.

Then:

- Upload the file(s) in `data/FAQs/processed/` via your RAG pipeline (e.g. “upload document” with the `.md` file).
- Optionally use a single combined file if you prefer one “FAQ knowledge doc” in the vector DB.

---

## 4. Optional: FAQ-specific ingestion

If you want to keep CSVs as the source of truth and avoid a separate “processed” step:

- Add an **FAQ CSV loader** in your app that:
  - Parses the CSV with the same column mapping as the script.
  - Builds **one chunk per FAQ row** (one Q&A per chunk).
  - Optionally stores **Category** (and Source) in chunk metadata for filtering.
- Use this path only for FAQ CSVs; keep the rest of the pipeline as-is.

Until that exists, **use the script + upload of the generated `.md` (or `.txt`) files** as above.

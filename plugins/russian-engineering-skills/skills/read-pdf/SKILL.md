---
name: read-pdf
description: Use this skill when you need to read local PDF files, extract searchable text page by page, find specific phrases or sections, and answer questions based on PDF contents. Best for project documentation, letters, reports, specifications, and other text-based PDFs stored on disk.
---

# Read PDF

## Overview

This skill is for reading local PDF documents and turning them into searchable text for analysis.
Use it for letters, project documentation, contracts, reports, explanatory notes, and similar text PDFs.

If the PDF is a scan without a text layer, extraction may be incomplete. In that case, say so clearly and fall back to OCR only if the environment supports it.

## Quick Start

1. Confirm the PDF exists locally.
2. If the original path has problematic characters for a tool, copy the file into the working folder with a short ASCII name first.
3. Run `scripts/extract_pdf_text.py` to extract text page by page.
4. Search the extracted text for the requested facts, tables, dates, names, or quantities.
5. Answer using concise source-backed statements.

## Workflow

If the PDF is being read to answer remarks, comments, or checklist items:

1. Turn the remarks into a short requirements list first.
2. Read only the parts of the PDF needed to close those points.
3. Keep page references for every important fact.
4. Avoid pulling unrelated text into the answer.

### 2a. Engineering drawings, specifications, and schedules

For project PDFs containing drawings, title blocks, specifications, material schedules, reinforcement schedules, or other graphical tables, text extraction is not sufficient by itself.

- Check the PDF page count and render the pages relevant to the requested section at readable resolution (normally 150–300 dpi).
- Visually inspect the whole sheet, including the right-hand and lower-right areas where specifications, steel-consumption schedules, legends, and notes are commonly placed.
- When a table is too small to read in the full-sheet render, render or crop the table at higher resolution and inspect the crop separately. Do not infer values from a failed or garbled OCR extraction.
- Read the title block and record both the physical PDF page and the drawing-sheet number shown in the stamp. They are different references.
- For reinforcement and similar schedules, capture the material class/grade, diameter, quantity, unit mass, total mass, and any multiplier in the table heading or notes. Independently recompute the total before using it as a project basis.
- Search all related drawing sheets for the same structure/foundation rather than stopping at the first text match. Tables may be located beside the drawing on a later sheet.
- If text extraction is incomplete but the rendered drawing is legible, treat the visual reading as the primary evidence and explicitly note that the text layer was incomplete.

### 1. Extract text

Use the bundled script:

```powershell
& python scripts/extract_pdf_text.py "C:\path\to\file.pdf"
```

The script writes a UTF-8 `.txt` file next to the PDF by default and inserts page markers like `===== PAGE 1 =====`.

### 2. Search for facts

For targeted questions, search the extracted text with keywords such as:

- `водоснабжение`
- `водоотведение`
- `договор`
- `ТУ`
- `отход`
- `спецификация`

If you already know the search terms, you can use the script directly:

```powershell
& python scripts/extract_pdf_text.py "C:\path\to\file.pdf" --find "водоснабжение" --find "отход"
```

### 3. Answer carefully

- Prefer exact project values over assumptions.
- Quote dates, numbers, document codes, and contract numbers exactly.
- When working from remarks or a summary table, answer point by point in the same order.
- Keep page-level traceability for critical facts.
- If data is missing from the PDF, say that it is not found in the document.
- Distinguish clearly between document facts and your assumptions.

## When To Use This Skill

- The user asks to study or read one or more local PDF files.
- You need to extract text from a PDF before answering questions.
- You need to find page-level evidence for technical or business facts inside a PDF.
- You need a repeatable workflow for PDF-based document review.

## Limits

- `pypdf` works best on text PDFs.
- Scanned PDFs may return partial or empty text.
- Tables may extract imperfectly; verify critical numbers against nearby text.

## Resources

### scripts/

- `scripts/extract_pdf_text.py` - extracts text from a PDF into a UTF-8 text file and optionally searches for keywords.

---
name: project-cover-title
description: Create or update Russian project documentation cover sheets and title pages from existing Word `.docx` templates. Use when Codex is asked to make "обложка", "титульник", "титул", "обложка и титул", or front matter for a project volume and must preserve template frames, logos, stamps, signatures, images, and Word layout.
---

# Project Cover Title

## Core Rule

Treat the Word template as the source of truth. Never rebuild the document from scratch and never serialize the whole OOXML tree through a generic XML writer unless there is no other option. Project cover/title templates often contain frames, VML shapes, floating images, signature placeholders, headers, footers, and relationships that are easy to damage.

Preferred edit path on Windows:

1. Copy the `.docx` template to a new output file.
2. Use Microsoft Word automation (`scripts/word_find_replace.ps1`) to perform text replacements inside the copy.
3. Compare the template and output package structure (`scripts/docx_package_audit.py`).
4. Render the output with the Documents skill (`render_docx.py --renderer artifact-tool`) and inspect every page image before delivery.

## Workflow

1. Identify the template `.docx`.
   - If the user gives a folder of examples, pick the template matching the project section, e.g. `ИОС6`.
   - Prefer `.docx` over companion `.pdf`.
   - Do not use a lock file such as `~$...docx`.
   - Determine whether the deliverable is expected to have a design frame/title block. If the rendered template or output has no visible frame but the user expects one, stop and choose a framed template or ask for the correct one instead of delivering a frameless file.

2. Extract source project facts.
   - For source PDFs, use the `read-pdf` skill.
   - Capture at least: object name, address, section/subsection name, cipher, volume, stage, year, GIP if shown.
   - If long text will not fit the template, shorten only display wording while keeping the engineering meaning.

3. Map exact old template text to new text.
   - Read template paragraphs first; replace exact strings already present in the template.
   - Keep the same line count and approximate length where possible.
   - For oversized titles, prefer 2-3 balanced lines over copying full cadastral/legal wording into the main title.

4. Edit with Word automation.
   - Create a JSON replacement map with exact old/new pairs.
   - Run `scripts/word_find_replace.ps1`.
   - This preserves drawing objects, logos, frames, headers, footers, stamps, and signatures better than OOXML rewrite scripts.

5. Verify package preservation.
   - Run `scripts/docx_package_audit.py TEMPLATE OUTPUT`.
   - Treat missing `word/media/*`, `.rels`, `vmlDrawing`, header/footer, or drawing parts as a blocker.

6. Visual QA.
   - Use the `documents` skill render workflow.
   - Inspect PNGs for every page.
   - Check: logo present, frame/title block present when expected, stamp present when expected, signature area present, no extra blank page, title text not clipped, year visible, section/cipher correct.
   - For footer title blocks, inspect the exported PDF/PNG, not only Word layout view. Treat any cell overflow, clipped organization name, overlapping stamp lines, or right stamp block extending outside the page frame as a blocker.
   - Compare the output preview against the source template preview. Missing frames, title blocks, logos, or signature graphics are blockers even if text replacements succeeded.
   - If the rendered output has extra pages or missing graphics, fix and rerender before final response.

## Executor List Sheet

When the task asks to create a framed `Список исполнителей` sheet, prefer the deterministic PDF generator over manually rebuilding a DOCX footer table. DOCX footer stamps are fragile: Word and LibreOffice can reflow the lower-right stamp cells differently during PDF export, causing the organization name, `Листов`, or title-block grid to overflow.

Use `scripts/create_executor_list_sheet.py`:

```powershell
python "$env:USERPROFILE\.codex\skills\project-cover-title\scripts\create_executor_list_sheet.py" `
  --output "C:\path\ГСП.004.25-ИОС4-СИ_Список_исполнителей.pdf" `
  --cipher "ГСП.004.25-ИОС4-СИ" `
  --person "ГИП=Демченков А.В." `
  --person "Ведущий инженер=Ремпель В.В." `
  --person "Нормоконтроль=Ремпель С.В."
```

After generation, render the PDF with Poppler and inspect the PNG. The stamp is acceptable only if:

- the right stamp block stays inside the outer frame;
- `Стадия`, `Лист`, `Листов`, stage value, sheet number, and sheet count are centered in their cells;
- `ООО "ГазСнабПроект"` fits inside the organization cell without crossing vertical lines;
- the executor table does not touch the outer frame and has no title/table overlap.

## Commands

PowerShell replacement example:

```powershell
$map = @{
  "ГСП.004.25-ИОС6" = "К1732-150/2-ИОС6"
  "Подраздел 6. Система газоснабжения" = "Подраздел 6. Система наружного газоснабжения"
}
$map | ConvertTo-Json | Set-Content .\replacements.json -Encoding UTF8
& "$env:USERPROFILE\.codex\skills\project-cover-title\scripts\word_find_replace.ps1" `
  -Template "C:\path\template.docx" `
  -Output "C:\path\Обложка и титул.docx" `
  -ReplacementsJson ".\replacements.json"
```

Package audit:

```powershell
python "$env:USERPROFILE\.codex\skills\project-cover-title\scripts\docx_package_audit.py" `
  "C:\path\template.docx" `
  "C:\path\Обложка и титул.docx"
```

## Fallbacks

- If Word automation is unavailable, ask before using a fallback because preservation risk is high.
- A fallback may use low-level OOXML only when it edits the smallest possible part and preserves every ZIP member, relationship, content type, media file, VML part, header/footer, and drawing part. Always audit and render afterward.
- If the template already contains a visible placeholder such as a gray `Image` box, report that it exists in the source template rather than silently deleting it.

---
name: komponovka-gsn
description: Assemble Russian GSN/IOS6 gas-supply issue packages from existing project PDFs. Use when Codex needs to prepare "компоновка ГСН", "скомпоновать ГСН", "сделать выдачу ГСН/ИОС6", add cover/title sheets on ГазСнабПроект letterhead, attach technical conditions (ТУ) and an MPU/MTU equipment passport, or produce final combined PDFs for stage P and stage R.
---

# Компоновка ГСН

## Core Rule

Preserve source project files and template formatting. Create new output files in the issue/delivery folder, leave original PDFs untouched, and verify the first pages visually before reporting completion.

Use `project-cover-title` when creating or editing cover/title DOCX files. Use `read-pdf` when source facts must be extracted from local PDFs.

## Workflow

1. Locate the working folders.
   - Treat the user's named folder as the delivery/output folder.
   - If they say "общая папка" or "корень проекта", inspect the parent project folder for ТУ, equipment passports, templates, and related source PDFs.
   - List candidate PDFs and DOCX templates before choosing.

2. Identify project PDFs and stages.
   - `ИОС6`, `ИОС5.6`, or "стадия П" normally means project documentation stage P.
   - `ГСН` normally means working documentation stage R.
   - If the user explicitly maps names to stages, follow their mapping.

3. Extract facts for cover/title sheets.
   - Capture cipher, stage, document name, object name/address, year, GIP, and volume/tom if present.
   - Prefer facts from the project PDF title block/text over filename guesses.
   - For stage P IOS6, use wording like `ПРОЕКТНАЯ ДОКУМЕНТАЦИЯ` and `Раздел 5. Подраздел 6. Система наружного газоснабжения` when consistent with the PDF.
   - For stage R GSN, use wording like `РАБОЧАЯ ДОКУМЕНТАЦИЯ` and `Наружное газоснабжение`.

4. Create cover/title sheets.
   - Prefer existing ГазСнабПроект two-page DOCX templates with cover and title pages.
   - Copy the template and perform exact text replacements with Word automation from `project-cover-title`.
   - Export the resulting DOCX to PDF using Microsoft Word.
   - Run DOCX package audit against the template after replacements.

5. Attach common appendices.
   - Add technical conditions to each final combined PDF when the user says "техусловия", "ТУ", or "общий том".
   - Add the MPU/MTU passport when the user says "паспорт МПУ", "паспорт МТУ", or similar.
   - Preserve appendix PDFs as-is; append them after the project PDF unless the user asks for another order.

6. Assemble final PDFs.
   - Recommended order: cover/title PDF, source project PDF, technical conditions PDF, equipment passport PDF.
   - Use a PDF library such as `pypdf` for deterministic merging.
   - Name outputs clearly, for example:
     - `<cipher>_с_обложкой_ТУ_паспортом.pdf`
     - `4603-81-10-ИОС6_с_обложкой_ТУ_паспортом.pdf`
     - `4603-81-10-ГСН_с_обложкой_ТУ_паспортом.pdf`

7. Verify.
   - Render or preview at least the first two pages of each final PDF.
   - Check logo, frame, stage, cipher, object name/address, year, GIP/signature area, and no stale text from the donor template.
   - Check page counts match the sum of all merged parts.
   - Remove temporary replacement JSON files and preview folders unless they are useful deliverables.

## Practical Notes

- If a donor template contains split or hidden text that Word find/replace cannot replace cleanly, choose a simpler compatible two-page template instead of forcing a fragile OOXML rewrite.
- If a ТУ PDF is scanned and text extraction is blank, still attach it as a PDF if its filename and location clearly identify it.
- If multiple candidate passports or ТУ files exist, prefer the one in the same project root and mention any ambiguity.
- Do not delete, overwrite, or rename the original source project PDFs.

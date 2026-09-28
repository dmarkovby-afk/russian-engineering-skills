---
name: registration-changes-table
description: Add and fill a Russian project documentation "Таблица регистрации изменений" sheet in a PDF using the saved TBE-style template. Use when the user asks to make, add, copy, fill, or correct a registration changes table/list/sheet for project volumes, especially when preserving the same beautiful stamp/table from the provided TBE example matters.
---

# Registration Changes Table

## Purpose

Use this skill to append a filled "Таблица регистрации изменений" sheet to the end of a project PDF while preserving the exact visual template copied from the user's TBE example.

The saved template is:

`assets/registration-table-template.png`

It is a clean version of the TBE registration table sheet: the first data row and bottom designation/sheet cells are blanked, but the table, frame, and stamp are preserved.

## Workflow

1. Identify the source PDF that needs the registration sheet.
2. Determine the first-row values from explicit evidence:
   - `changed`: changed sheet numbers.
   - `replaced`: replaced sheet numbers, or `-`.
   - `new`: new sheet numbers, or `-`.
   - `annulled`: annulled sheets, or `-`.
   - `total`: total sheets/pages in the final document after appending the registration table.
   - `doc-number`: usually `И1` unless the user or project says otherwise.
   - `date`: usually month/year such as `06.2026`.
   - `designation`: bottom-stamp designation, e.g. `СП050325-ИОС6-РИ`.
   - `sheet`: usually `1`.
3. If a field is not clear from the supplied files, ask the user instead of guessing.
4. Run `scripts/append_registration_table.py`.
5. Render/check the appended last page before returning the final PDF path.

## Script

Example:

```powershell
python "$env:USERPROFILE\.codex\skills\registration-changes-table\scripts\append_registration_table.py" `
  "input.pdf" "output.pdf" `
  --changed "ТЧ л.1,3,5;`nГЧ л.3" `
  --replaced "СП л.1" `
  --new "РИ л.1" `
  --annulled "-" `
  --total "39" `
  --doc-number "И1" `
  --date "06.2026" `
  --designation "СП050325-ИОС6-РИ" `
  --sheet "1"
```

## Guardrails

- Do not redraw the table from scratch when this template is available.
- Do not overwrite the user's original PDF unless explicitly asked.
- Do not include unrelated review commentary in the final answer when the user asks for only the filled file.
- For change detection, prefer explicit user-provided remarks, comparison against old/new PDFs, or file names that identify changed sheets. Do not invent changed sheets.

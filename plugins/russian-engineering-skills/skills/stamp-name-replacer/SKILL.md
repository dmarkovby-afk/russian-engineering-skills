---
name: stamp-name-replacer
description: Replace surnames and initials in Russian project PDF title-block stamps, including developer, norm-control, GIP, and similar stamp rows, while preserving PDF pages, frames, drawings, dates, and signatures.
---

# Stamp Name Replacer

Use this skill when a Russian project PDF needs name changes in title-block stamps. Typical requests mention stamps, title blocks, developer rows, norm-control rows, GIP rows, surnames, initials, or names in the lower-right project documentation frame.

## Workflow

1. Confirm the target PDF exists and identify the requested replacements exactly.
2. Search the PDF text with PyMuPDF to find all old names and page numbers.
3. Render crops of each affected stamp before editing when placement is uncertain.
4. Create a backup next to the original before any in-place change.
5. Redact only the small rectangles containing old names, with white fill.
6. Insert replacement names as transparent raster text overlays. Prefer this over direct PDF text insertion for Cyrillic, because some PyMuPDF and font combinations render Cyrillic as dots or question marks.
7. Render every affected page or stamp crop after editing and visually inspect it.
8. Verify old searchable names are gone. New names inserted as raster overlays may not be searchable; visual QA is authoritative.
9. If the user also asks to rename the PDF, derive the name from the title page and follow the folder's existing naming style.

## DWG Fallback

If the rendered check shows mismatched font, fuzzy text, frame overlap, or a visible PDF patch, stop PDF overlay work. Find the source DWG near the PDF, create a DWG backup, and edit the stamp attribute/text in AutoCAD or AutoCAD Core Console instead. Regenerate the PDF from the corrected DWG so the stamp keeps the native SHX/font, line weights, and cell boundaries.

For developer-row replacements, avoid broad name replacement. Match the name only when it is horizontally near the `Разраб` / `Разработал` label in the same row, then save the DWG. Keep norm-control, checked-by, and GIP rows unchanged unless requested.

## Preferred Script

Use `scripts/replace_stamp_names.py` for repeatable replacements.

Example:

```powershell
python $env:USERPROFILE\.codex\skills\stamp-name-replacer\scripts\replace_stamp_names.py `
  --pdf "C:\path\to\volume.pdf" `
  --replace "OLD_NAME=NEW_NAME" `
  --replace "OLD_CONTROL_NAME=NEW_CONTROL_NAME"
```

Useful options:

- `--output "C:\path\to\new.pdf"` writes a copy instead of modifying in place.
- `--render-dir "C:\path\to\qa"` writes PNG crops for visual QA.
- `--font "C:\Windows\Fonts\calibrii.ttf"` changes the raster overlay font.
- `--scale 6` controls raster text sharpness; keep 5-8 for PDF stamps.

## Rules

- Do not replace by broad page text rewriting. Only redact found name rectangles.
- Do not alter dates, signatures, frame lines, sheet numbering, drawing content, or page order.
- Treat rotated stamps normally: detect text direction and rotate the replacement overlay.
- Keep replacement text inside the name cell and above the row separator. If the replacement is longer than the original, reduce the rendered text instead of letting it cross into the signature column.
- If a clean native DWG source is available, prefer DWG correction over raster PDF overlay for final deliverables.
- Keep original PDFs untouched when the task is archival or delivery packaging; otherwise, in-place edits are acceptable only after creating a backup.
- If the old names are not searchable, render the stamp pages and use a manual overlay plan instead of guessing.

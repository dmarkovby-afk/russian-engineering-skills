---
name: dwg-batch-publish-layouts
description: Configure AutoCAD/AutoCAD LT DWG batch publishing when one paper-space Layout contains many drawing frames arranged in a row or strip. Use when Codex needs to find all sheet frames in a DWG, create separate publish-ready Layouts such as Sheet_01/Sheet_02, set DWG To PDF window plotting, create DSD files, or debug incorrect DWG publish output where only some frames were found or neighbouring sheets appear in a plot.
---

# DWG Batch Publish Layouts

Use this skill for Russian project DWG files where one paper-space Layout contains many оформленные рамки/листы in a horizontal strip and the user needs one PDF page per frame.

## Core Rules

- Work on a copy of the DWG. Never modify the user’s source file directly.
- Prefer AutoCAD/AutoCAD LT Core Console for repeatable scripts, but expect limitations: `-PUBLISH` may be unavailable in AutoCAD LT Core Console, and Cyrillic paths/names may be fragile.
- Use ASCII temp paths for scripts and working DWGs, for example `C:\Temp\dwg_publish_work`.
- Keep original Layouts (`Model`, source `Лист1`, `ГСВ`, etc.). Do not delete or move source geometry.
- Prefer creating Layout copies with saved `Window` plot settings over copying geometry into new Layouts. Copying geometry can leave missing objects or neighbour fragments.
- Verify with real PDF output from several or all generated Layouts before reporting success.

## Workflow

1. Copy source DWG to a temp work folder and create a timestamped backup.
2. Inspect Layouts and identify the source Layout containing the sheet strip.
3. Detect every frame, not just the first frame type:
   - Dump all `INSERT` entities on the source Layout.
   - Identify repeated frame blocks by coordinates and scale.
   - Compute block definition bounding boxes for candidate frame blocks.
   - Include all frame types: normal A3 frames, narrow calculation/title frames, and specification/table frames.
4. Sort frame windows left-to-right by minimum X, then by Y if needed.
5. Create `Sheet_01`, `Sheet_02`, ... by copying the source Layout.
6. For each new Layout, save plot settings:
   - device: `DWG To PDF.pc3`
   - units: millimeters
   - plot area: `Window`
   - window: exact frame bounds
   - scale: `Fit`
   - center plot: yes
   - plot style: `monochrome.ctb` when available
   - orientation from window proportions
7. Generate a DSD file containing only created `Sheet_*` Layouts. Exclude `Model` and the source Layout.
8. Plot control PDFs from the generated Layouts and make a contact sheet image. Check that each PDF page contains exactly one drawing frame.
9. Save outputs in a clear folder with DWG, DSD, script, report, PDFs, and contact sheet.

## Detection Notes

Do not assume all frames share one block name. In the Верзилово ОПС example, the full correct set required:

- `A$C72c2bba3`: regular A3-like frames
- `A$Cf3803f95`: narrow frame
- `A$Cd65abf49` and `A$C59f35141`: yellow specification/table frames

When a user points to a missed frame in AutoCAD, ask for or infer from the Properties palette:

- object type (`Вхождение` means block insert)
- layer
- insertion position
- scale
- block name if visible

Then rerun insert/block-bound diagnostics and rebuild the frame list.

## Validation Standard

Do not say the DWG is ready just because Layouts were created. It is ready only after:

- the number of detected frames matches the visible strip,
- control PDFs are non-empty,
- contact sheet shows one frame per page,
- missing special frames (narrow sheets, specifications, C1/C2 tables) are included.

If previews show blank pages, neighbour sheets, or missing frames, treat the result as failed and revise detection.

## Useful Script Pattern

Use the bundled script template `scripts/make_window_layouts_template.lsp` as a starting point. Fill `srcLayout` and `frames`, where each frame is:

```lisp
(list left bottom right top "source-block-or-note")
```

Then run it with Core Console:

```powershell
& 'C:\Program Files\Autodesk\AutoCAD LT 2025\accoreconsole.exe' /i 'C:\Temp\dwg_publish_work\work.dwg' /s 'C:\Temp\dwg_publish_work\make_window_layouts.scr'
```

Create a separate plotting script for control PDFs and render a contact sheet before final delivery.

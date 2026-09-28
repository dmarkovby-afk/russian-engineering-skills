---
name: compare-1c-documents
description: Compare 1C web-client realization/receipt/sales/purchase documents by tabular item parts, verify full row coverage, export Excel reports, and, when explicitly authorized, perform controlled line corrections in batches with save checkpoints. Use for read-only comparisons by item names/row counts and for carefully staged 1C document corrections that must not post/conduct documents without a separate command.
---

# Compare 1C Documents

## Core Safety Rules

Treat live 1C as production data.

- Default mode is read-only: do not change, save, post, conduct, unpost, create, delete, or edit data unless the user explicitly authorizes an edit workflow.
- Never click `Провести`, `Провести и закрыть`, `Отменить проведение`, deletion, reposting, or document creation unless the user gives a separate explicit command.
- If the user authorizes edits, change only the document, tabular part, rows, and columns named in the request.
- If 1C opens a dialog that could save, post, overwrite, reload, lose changes, or alter data, pause and report the exact prompt unless the user already authorized that exact operation.
- Keep a local progress log before and during long runs so work can resume after browser timeouts.

## Read-Only Comparison Workflow

1. Identify both documents and the target tabular part, usually `Товары`.
2. Confirm the row count visible in each document tab, such as `Товары (7 306)`.
3. Try a read-only bulk extraction first:
   - `Вывести список`;
   - `Сохранить список`;
   - `Сохранить как`;
   - Excel/CSV/HTML export;
   - copying the generated tabular document.
4. If export or clipboard is unavailable, read the 1C grid DOM while scrolling automatically.
5. Validate coverage before comparing:
   - collected row count equals the visible 1C row count;
   - row numbers from `1..N` have no missing values;
   - raw extracted rows are saved locally before comparison.
6. Compare only the fields requested by the user. For item-list checks, compare normalized `Номенклатура` names and total row counts unless the user asks for quantities, prices, VAT, accounts, or sums.
7. Output only discrepancies. Do not list matching positions.

## Controlled Correction Workflow

Use this only after the user explicitly authorizes edits.

1. Re-run or load a fresh comparison immediately before editing.
2. Do not start corrections unless row counts and item composition match, or unless the user explicitly accepts the listed unresolved differences.
3. Build a correction plan from trusted source data:
   - source document rows;
   - target document rows;
   - row number;
   - normalized item name;
   - old target values;
   - new source values;
   - columns to edit.
4. For duplicate item names, match by row number plus name when possible. If order or row number is unreliable, match by a stable combination such as name, quantity, price, and sum. Stop and report ambiguous duplicates.
5. Before editing, write the plan to disk as JSON/CSV.
6. Apply changes in batches of at most 300 rows.
7. After each batch:
   - verify edited cells in the visible grid or by export/re-read;
   - update the progress log with applied rows, skipped rows, errors, and current totals;
   - stop and ask the user for permission to save the batch.
8. Save only after the user approves that batch save. Saving is allowed only with `Записать`; never use `Провести` or `Провести и закрыть`.
9. After saving a batch, verify the document remains unposted/unconducted when the UI exposes that state, then continue with the next batch.
10. If the 1C web client stops rendering rows, hangs, or shows only headers, stop editing. Ask whether to `Перечитать`, close/reopen the document, or continue later.

Recommended batch report:

| Batch | Rows attempted | Rows changed | Rows skipped | Errors | Needs save | Saved | Posted |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- |

Recommended row correction report:

| № | Позиция | Колонка | Было в поступлении | Должно быть как в реализации | Статус | Комментарий |
| ---: | --- | --- | ---: | ---: | --- | --- |

## Editing Validation Rules

- Every edited cell must match the corresponding source value requested by the user.
- If changing `Сумма без НДС` causes 1C to recalculate `Цена без НДС`, verify that the recalculated price also matches the source document if the user requires all changed cells to match.
- If 1C refuses an exact value or rounds it differently, do not silently accept it. Report the row, item, target value, actual value, and likely reason.
- Track totals after every batch when sums are being corrected.
- Do not continue after repeated verification failures; inspect the cause first.

## Browser Extraction Notes

Use the Browser skill for the Codex in-app browser. Prefer stable DOM selectors over visual OCR when possible.

For 1C web-client item grids, visible rows often have this shape:

- grid id: `grid_<formId>_Товары`
- vertical scroll id: `vertScroll_<formId>_Товары`
- row containers: `.gridLine`
- row number cell: `.gridBox[colindex="0"]`
- item-name cell: `.gridBox[colindex="1"]`

Use visible row numbers to build a map `{ rowNumber: itemName }`. Scroll in small chunks, merge by row number, and periodically write partial JSON to disk so long browser calls can resume after timeout.

If a name is visually truncated with `...`, resolve it only when there is a unique full-name match from the other document or from a read-only export. Otherwise mark the result as truncated or requiring manual verification.

## Comparison Rules

Normalize names by trimming, replacing non-breaking spaces with normal spaces, and collapsing repeated whitespace.

Use set or multiset logic according to the request:

- If the user asks whether positions exist in both documents, report names present in one document and absent in the other.
- If duplicate line counts for the same name affect the total row count, report `Разное число строк с этим наименованием` unless the user explicitly says to ignore duplicate-row differences.
- Do not compare per-item quantity, price, amount, VAT, accounts, or other fields unless explicitly requested.

Recommended discrepancy columns:

| № | Строки реализации | Позиция | Есть в реализации | Есть в поступлении | Тип расхождения | Комментарий |
| ---: | --- | --- | --- | --- | --- | --- |

For documents other than realization/receipt, adapt the row-number column names.

## Excel Report

When the user asks for Excel, use the spreadsheet skill and the bundled script `scripts/build_report.mjs` when raw row JSON files are available.

Expected JSON format:

```json
{
  "expected": 7306,
  "missing": [],
  "rows": [
    { "n": 1, "name": "Item name" }
  ]
}
```

Example:

```powershell
node scripts/build_report.mjs `
  --left realization_rows.json `
  --right receipt_rows.json `
  --left-label "реализации" `
  --right-label "поступлении" `
  --output comparison.xlsx
```

The workbook should include:

- `Расхождения`: discrepancy table with filters and source row numbers;
- `Итог`: document labels, row counts, missing-row checks, discrepancy count, and final result.

Verify the workbook opens as a valid `.xlsx` and inspect the first rows before reporting completion.

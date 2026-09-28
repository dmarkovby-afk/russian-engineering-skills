---
name: xmlonline-expert-comments
description: Process Russian expert review remarks for project documentation and update an XMLonline explanatory note. Use when Codex is asked to study remarks/замечания, compare them with ПЗ/XML/PDF project volumes, fill or correct data in https://xmlonline.ru, remove duplicates, add missing norms or section references, and draft concise replies to эксперты.
---

# XMLonline Expert Comments

## Overview

Use this skill for the recurring workflow: read expert remarks, determine the objective correction, update the open XMLonline explanatory note, verify the resulting fields, and give the user a short report plus a ready-to-paste expert response.

## Workflow

1. Identify the remark source: screenshot, PDF, DOCX, browser page, or user text. Extract the expert's exact requirement, code, affected section, and latest comment.
2. Find the current project source of truth: open XMLonline page, local XML in the ОПЗ folder, and relevant project PDFs when the remark depends on another volume.
3. Decide whether the remark is about missing information, wrong wording, wrong section reference, duplicate entries, or stale uploaded files.
4. Update XMLonline in the browser when the user asks to fill/correct there. Use the Browser skill first. Avoid reloading `https://xmlonline.ru/projects/...` unless necessary because unsaved state may be lost.
5. Verify after every edit with targeted checks: total row count, exact key matches, duplicates, blank rows, and whether the edited field is in the intended XML block.
6. When the user is preparing a corrected XML for upload, also verify the local XML with `https://checkxml.gge.ru/check` when the user authorizes that site, using slot `Explanatorynote`.
7. Report what changed and provide a concise answer for the expert's comment.

## Browser Editing Rules

- Work in the currently open XMLonline tab whenever possible.
- Expand parent sections before editing nested fields. Common top-level button: `data-tag-name="ExplanatoryNote"`.
- Prefer stable XMLonline attributes such as `data-tag-name`, `data-id`, `data-tag-id`, `id`, and field `name`.
- Before clicking an add/delete button, verify that the locator is scoped to the intended block and resolves to exactly one element.
- After adding rows, check for blank rows and duplicate key entries.
- If deleting a row prompts a browser confirmation, accept only when the row has been verified as the duplicate or wrong entry.
- Distinguish "present in XML" from "visually visible in XMLonline". If the user asks to check visual presence, inspect the browser form values, radio choices, and visible field context, not only the local XML.
- If XMLonline storage mode is shown as off, file names and CRC values may not be visible in ordinary browser fields even when the XML contains them. In that case, report that visual file storage cannot confirm CRC, and verify filenames/checksums against the XML.
- For document rows with three radio options, verify the chosen option:
  - `Файл документа или файл фрагмента документа` for uploaded local files;
  - `Ссылка на официально опубликованный документ в сети Интернет` for official web links;
  - `Сведения о документе, приложением к которому является текущий документ` only when the document is referenced as an attachment to another current document.

## Common XMLonline Blocks

Read `references/xmlonline-patterns.md` when editing XMLonline fields or when you need common selectors and validation patterns.

## XML File Details

- In `File` elements, preserve schema order: `FileName`, then `FileFormat`, then optional `FileRelativePath`, then `FileChecksum`, then optional `SignFile`. If `FileFormat` is missing, add it before `FileChecksum`.
- For PDF files, use `FileFormat` value `pdf`. For GGE files use `gge`; for ZIP files use `zip`; for XLSX files use `xlsx`; for IFC files use `ifc`.
- Calculate CRC32 from the actual file bytes when replacing files. Do not invent or reuse a checksum unless it is explicitly from the expert comparison table and the XML is being aligned to that exact already-uploaded file.
- When a file is intentionally replaced by a newer project volume, mention the replacement explicitly in the report instead of treating the older expert-table filename as still required.

## Technical And Economic Indicators

When correcting TEP/TEI remarks, match the expert or source-volume wording one-for-one:

- Preserve the exact indicator names requested by the expert or taken from СПОЗУ/АР.
- Preserve the exact values and decimal separators, e.g. `112,5`, `187,7`, `88,82`, `308,22`.
- Remove extra split-out indicators when the expert requires a compact list, unless the source document requires both aggregate and detail rows.
- Common units in XMLonline may be coded in XML while rendered as text in the print form: `055` for square meters, `113` for cubic meters, `006` for meters, `796` for floors, and project-specific power units may already exist in `PowerIndicator`. Prefer the code already used in the XML when it renders correctly.
- After editing TEP/TEI, dump the final list and compare it to the requested list by name, unit, and value before reporting completion.

## Control Sums And File Comparison Remarks

For remarks like "Контрольные суммы файлов не соответствуют или отсутствуют в ПЗxml":

- Use the expert comparison table as the target list where available.
- Compare by exact filename and CRC32.
- Include all affected groups in the answer when they were part of the table: main project volumes, сметная документация, engineering survey reports, survey tasks/programs, source/permit documents, IFC files, and other attachments.
- If the user asks "что конкретно поменяли", list the corrected groups and the most important filenames/checksums, not a vague "актуализировано".
- If an expert-table row is superseded by a newer volume at the user's instruction, say so plainly, e.g. "Раздел 03 АР заменен на актуальную версию от <date>, сведения в ПЗ актуализированы."

## Frequent Remark-Specific Checks

- `Заверение проектной организации`: use the exact wording required by subpoint `ф)` of point 10 of Decree 87 when requested. In particular, preserve "в пункте 5 настоящего Положения" and "с соблюдением технических условий" if those phrases are in the expert comment.
- `Основания для разработки проектной документации`: for a municipal program, use the block "Основания для разработки проектной документации"; if the user asks for an official publication URL, select/add the `Link` option rather than a `File`.
- `Перечень исходно-разрешительной документации, кроме отчетной документации по результатам инженерных изысканий`: place certificates and similar source documents here, with visible реквизиты and file/link selection checked.
- `Результаты инженерных изысканий`: verify report date, filename, and CRC together. Do not assume a report date from file modification time; extract it from the report or use the expert's stated date.

## Normative Lists

For `UsedNorms`, preserve the existing format: document identifier, tab, title, optional section reference. Do not add invented section references unless the expert explicitly asks for them or the existing list consistently uses them.

When correcting expert comments about a missing document list:

- Add each document as a separate `UsedNorm` row.
- Use full names from the expert comment, but correct obvious formal notation when needed, such as `СанПиН 2.2.1/2.1.1.1200-03`.
- Check that every added key appears exactly once.
- Remove duplicates only after identifying which row is redundant.

## Expert Replies

Keep replies short and factual. Mention where the information was added, using the section and block name.

Template:

`Исправлено. В разделе 1 «Пояснительная записка», в блок «<название блока>», <что добавлено/уточнено/исключено>.`

For repeated objections:

`Исправлено повторно. В открытом XML раздела 1 «Пояснительная записка» в блок «<название блока>» добавлены <данные>. Проверено: <количество/отсутствие дублей/пустых строк>.`

For control-sum remarks:

`Исправлено. В разделе 1 «Пояснительная записка», в блоке «Состав проектной документации», актуализированы наименования файлов и контрольные суммы CRC32 по <группы документов>. Контрольные суммы приведены к значениям из таблицы сравнения эксперта.`

For TEP remarks:

`Исправлено. В разделе 1 «Пояснительная записка», в блоке «Технико-экономические показатели проектируемого объекта капитального строительства», наименования показателей, единицы измерения и значения приведены в соответствие с разделами СПОЗУ и АР.`

## Final Report

Tell the user:

- which remark was addressed;
- exactly what was added, changed, or removed;
- where it was added in the ПЗ/XMLonline structure;
- what verification passed;
- the ready-to-paste expert response.

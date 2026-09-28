import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

async function loadArtifactTool() {
  try {
    return await import("@oai/artifact-tool");
  } catch {
    const candidates = [
      process.env.ARTIFACT_TOOL_MODULE,
      path.join(process.cwd(), "node_modules", "@oai", "artifact-tool", "dist", "artifact_tool.mjs"),
    ].filter(Boolean);
    for (const candidate of candidates) {
      try {
        return await import(pathToFileURL(candidate).href);
      } catch {
        // Try the next candidate.
      }
    }
    throw new Error("Cannot load @oai/artifact-tool. Run from a workspace with node_modules linked to Codex workspace dependencies, or set ARTIFACT_TOOL_MODULE.");
  }
}

const { SpreadsheetFile, Workbook } = await loadArtifactTool();

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 1) {
    if (!argv[i].startsWith("--")) continue;
    const key = argv[i].slice(2);
    const value = argv[i + 1] && !argv[i + 1].startsWith("--") ? argv[++i] : "true";
    args[key] = value;
  }
  return args;
}

const args = parseArgs(process.argv.slice(2));
for (const required of ["left", "right", "output"]) {
  if (!args[required]) throw new Error(`Missing --${required}`);
}

const leftLabel = args["left-label"] ?? "левом документе";
const rightLabel = args["right-label"] ?? "правом документе";
const leftTitle = args["left-title"] ?? "Левый документ";
const rightTitle = args["right-title"] ?? "Правый документ";

const left = JSON.parse(await fs.readFile(args.left, "utf8"));
const right = JSON.parse(await fs.readFile(args.right, "utf8"));

const normalize = (value) =>
  String(value ?? "")
    .replace(/\u00a0/g, " ")
    .replace(/\s+/g, " ")
    .trim();

function resolveEllipses(sourceRows, referenceRows) {
  for (const row of sourceRows) {
    const name = normalize(row.name);
    if (!name.endsWith("...")) continue;
    const prefix = name.slice(0, -3);
    const matches = referenceRows.filter((candidate) => normalize(candidate.name).startsWith(prefix));
    if (matches.length === 1) row.name = matches[0].name;
  }
}

resolveEllipses(left.rows, right.rows);
resolveEllipses(right.rows, left.rows);

function countByName(rows) {
  const counts = new Map();
  for (const row of rows) {
    const name = normalize(row.name);
    counts.set(name, (counts.get(name) ?? 0) + 1);
  }
  return counts;
}

function rowNumbersByName(rows) {
  const result = new Map();
  for (const row of rows) {
    const name = normalize(row.name);
    if (!result.has(name)) result.set(name, []);
    result.get(name).push(row.n);
  }
  return result;
}

const leftCounts = countByName(left.rows);
const rightCounts = countByName(right.rows);
const leftRowsByName = rowNumbersByName(left.rows);
const allNames = [...new Set([...leftCounts.keys(), ...rightCounts.keys()])].sort((a, b) =>
  a.localeCompare(b, "ru"),
);

const discrepancies = [];
const leftRowsText = (name) => {
  const rows = leftRowsByName.get(name) ?? [];
  return rows.length ? rows.join(", ") : "-";
};

for (const name of allNames) {
  const inLeft = leftCounts.get(name) ?? 0;
  const inRight = rightCounts.get(name) ?? 0;
  if (inLeft > 0 && inRight === 0) {
    discrepancies.push([
      discrepancies.length + 1,
      leftRowsText(name),
      name,
      "Да",
      "Нет",
      `Отсутствует в ${rightLabel}`,
      `${inLeft} строк(и) только в ${leftLabel}`,
    ]);
  } else if (inLeft === 0 && inRight > 0) {
    discrepancies.push([
      discrepancies.length + 1,
      leftRowsText(name),
      name,
      "Нет",
      "Да",
      `Отсутствует в ${leftLabel}`,
      `${inRight} строк(и) только в ${rightLabel}`,
    ]);
  } else if (inLeft !== inRight) {
    discrepancies.push([
      discrepancies.length + 1,
      leftRowsText(name),
      name,
      "Да",
      "Да",
      "Разное число строк с этим наименованием",
      `${leftLabel}: ${inLeft}; ${rightLabel}: ${inRight}`,
    ]);
  }
}

const workbook = Workbook.create();
const diff = workbook.worksheets.add("Расхождения");
const summary = workbook.worksheets.add("Итог");
diff.showGridLines = false;
summary.showGridLines = false;

const headers = [
  "№",
  `Строки в ${leftLabel}`,
  "Позиция",
  `Есть в ${leftLabel}`,
  `Есть в ${rightLabel}`,
  "Тип расхождения",
  "Комментарий",
];
const rowCount = Math.max(discrepancies.length + 1, 2);
diff.getRangeByIndexes(0, 0, 1, headers.length).values = [headers];
if (discrepancies.length) diff.getRangeByIndexes(1, 0, discrepancies.length, headers.length).values = discrepancies;
diff.tables.add(`A1:G${rowCount}`, true, "Discrepancies");
diff.freezePanes.freezeRows(1);
diff.getRange("A1:G1").format = {
  fill: "#1F4E79",
  font: { bold: true, color: "#FFFFFF" },
  wrapText: true,
  horizontalAlignment: "center",
};
diff.getRange(`A1:G${rowCount}`).format = {
  font: { name: "Arial", size: 10 },
  verticalAlignment: "top",
};
diff.getRange(`A2:B${rowCount}`).format = { horizontalAlignment: "center" };
diff.getRange(`D2:E${rowCount}`).format = { horizontalAlignment: "center" };
diff.getRange(`C2:C${rowCount}`).format = { wrapText: true };
diff.getRange(`F2:G${rowCount}`).format = { wrapText: true };
diff.getRange("A:A").format.columnWidthPx = 48;
diff.getRange("B:B").format.columnWidthPx = 130;
diff.getRange("C:C").format.columnWidthPx = 520;
diff.getRange("D:E").format.columnWidthPx = 120;
diff.getRange("F:F").format.columnWidthPx = 230;
diff.getRange("G:G").format.columnWidthPx = 260;

const summaryRows = [
  ["Показатель", "Значение"],
  ["Левый документ", leftTitle],
  ["Правый документ", rightTitle],
  [`Количество строк в ${leftLabel}`, left.rows.length],
  [`Количество строк в ${rightLabel}`, right.rows.length],
  ["Количество расхождений", discrepancies.length],
  [`Контроль пропусков в ${leftLabel}`, left.missing?.length ?? 0],
  [`Контроль пропусков в ${rightLabel}`, right.missing?.length ?? 0],
  ["Итог", discrepancies.length === 0 ? "совпадает" : "не совпадает"],
];
summary.getRangeByIndexes(0, 0, summaryRows.length, 2).values = summaryRows;
summary.tables.add(`A1:B${summaryRows.length}`, true, "Summary");
summary.getRange("A1:B1").format = { fill: "#1F4E79", font: { bold: true, color: "#FFFFFF" } };
summary.getRange(`A1:B${summaryRows.length}`).format = {
  font: { name: "Arial", size: 10 },
  wrapText: true,
  verticalAlignment: "top",
};
summary.getRange("A:A").format.columnWidthPx = 300;
summary.getRange("B:B").format.columnWidthPx = 520;

await fs.mkdir(path.dirname(args.output), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(args.output);
console.log(JSON.stringify({ output: args.output, discrepancies: discrepancies.length }));

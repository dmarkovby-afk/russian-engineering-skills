from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from xml.etree import ElementTree as ET


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    description: str
    passed: bool
    evidence: str = ""


def extract_docx_paragraphs(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as package:
        root = ET.fromstring(package.read("word/document.xml"))
    paragraphs: list[str] = []
    for paragraph in root.iter(W + "p"):
        parts: list[str] = []
        for element in paragraph.iter():
            if element.tag == W + "t" and element.text:
                parts.append(element.text)
            elif element.tag == W + "tab":
                parts.append("\t")
        value = "".join(parts).replace("\u00a0", " ").strip()
        if value:
            paragraphs.append(re.sub(r"\s+", " ", value))
    return paragraphs


def first_matching(paragraphs: list[str], patterns: list[str]) -> str:
    for paragraph in paragraphs:
        if all(re.search(pattern, paragraph, re.IGNORECASE) for pattern in patterns):
            return paragraph
    return ""


def result(check_id: str, description: str, paragraphs: list[str], patterns: list[str]) -> CheckResult:
    evidence = first_matching(paragraphs, patterns)
    return CheckResult(check_id, description, bool(evidence), evidence)


def result_across_paragraphs(
    check_id: str, description: str, paragraphs: list[str], patterns: list[str]
) -> CheckResult:
    evidence: list[str] = []
    for pattern in patterns:
        match = next((p for p in paragraphs if re.search(pattern, p, re.IGNORECASE)), "")
        if not match:
            return CheckResult(check_id, description, False, "")
        if match not in evidence:
            evidence.append(match)
    return CheckResult(check_id, description, True, " | ".join(evidence))


def decimal_pattern(value: str) -> str:
    normalized = value.strip().replace(" ", "").replace(".", ",")
    integer, separator, fraction = normalized.partition(",")
    if not separator:
        return rf"(?<!\d){re.escape(integer)}(?:[,.]0+)?(?!\d)"
    fraction = fraction.rstrip("0") or "0"
    return rf"(?<!\d){re.escape(integer)}[,.]{re.escape(fraction)}0*(?!\d)"


def audit(path: Path, expected_max: str | None) -> list[CheckResult]:
    paragraphs = extract_docx_paragraphs(path)
    checks = [
        result("heat_balance", "Сумма тепловых нагрузок", paragraphs, [r"Q", r"=", r"Гкал/ч", r"\+"]),
        result("gcal_to_mw", "Перевод Гкал/ч в МВт", paragraphs, [r"1[,.]163", r"МВт", r"="]),
        result("hourly_by_load", "Часовой расход по тепловой нагрузке", paragraphs, [r"[ВB]ч[.]?(?:нагр|1)", r"10\s*[⁶^]", r"8000", r"м[³3]/ч"]),
        result("heating_value_conversion", "Перевод Qн из ккал/м³ в МДж/м³", paragraphs, [r"Qн", r"4[,.]1868", r"1000", r"МДж/м[³3]"]),
        result("hourly_by_power", "Часовой расход по установленной мощности", paragraphs, [r"[ВB]ч[.]?мощ", r"3600", r"МДж/м[³3]", r"м[³3]/ч"]),
        result("hourly_by_passport", "Часовой расход по паспортным данным", paragraphs, [r"[ВB]ч[.]?пасп", r"=", r"[×*·]", r"м[³3]/ч"]),
        result("maximum_selection", "Явный выбор максимума из трех расходов", paragraphs, [r"[ВB]ч[.]?расч", r"max\s*\(", r"[ВB]ч[.]?нагр", r"[ВB]ч[.]?мощ", r"[ВB]ч[.]?пасп", r"м[³3]/ч"]),
        result("annual_heat", "Годовой отпуск тепла с итогом", paragraphs, [r"Qгод", r"=", r"Гкал/год"]),
        result("conditional_fuel", "Годовой расход условного топлива", paragraphs, [r"[ВB]у[.]?т", r"Qгод", r"7", r"т\s*у[.]?т[.]?/год"]),
        result_across_paragraphs("annual_natural_gas", "Годовой расход природного газа", paragraphs, [r"[ВB](?:г|год)", r"Qгод", r"10\s*[⁶^]", r"8000", r"м[³3]/год"]),
        result("monthly_heat", "Помесячная формула расхода тепла", paragraphs, [r"Q(?:от|гвс)[.](?:м|мес)", r"="]),
        result("monthly_gas", "Помесячная формула расхода природного газа", paragraphs, [r"[VВ]м", r"Qм", r"10\s*[⁶^]", r"8000", r"м[³3]/мес"]),
    ]

    full_text = "\n".join(paragraphs)
    if re.search(r"II\s+категор", full_text, re.IGNORECASE):
        reserve_evidence = first_matching(paragraphs, [r"(?:ГВС|горячее водоснабжение)", r"отключ", r"%"])
        if not reserve_evidence:
            reserve_evidence = first_matching(paragraphs, [r"одн(?:ой|а)\s+МТУ", r"%"])
        checks.append(CheckResult("reservation", "Резервирование для II категории", bool(reserve_evidence), reserve_evidence))

    if expected_max:
        number = decimal_pattern(expected_max)
        occurrences = re.findall(number + r"\s*м[³3]/ч", full_text, re.IGNORECASE)
        maximum_formula = first_matching(paragraphs, [r"[ВB]ч[.]?расч", r"max\s*\(", number, r"м[³3]/ч"])
        checks.append(
            CheckResult(
                "expected_max_formula",
                "Ожидаемый МЧРГ присутствует в формуле выбора максимума",
                bool(maximum_formula),
                maximum_formula,
            )
        )
        checks.append(
            CheckResult(
                "expected_max",
                "Ожидаемый МЧРГ согласован в документе не менее чем в трех местах",
                len(occurrences) >= 3,
                f"Найдено совпадений: {len(occurrences)}",
            )
        )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Проверка полноты обязательных формул в расчете МЧРГ DOCX")
    parser.add_argument("docx", type=Path)
    parser.add_argument("--expected-max", required=True, help="Ожидаемый максимальный часовой расход, м3/ч")
    parser.add_argument("--json", action="store_true", help="Вывести отчет в JSON")
    args = parser.parse_args()

    if not args.docx.is_file() or args.docx.suffix.lower() != ".docx":
        parser.error("Укажите существующий DOCX")

    checks = audit(args.docx, args.expected_max)
    failed = [item for item in checks if not item.passed]
    if args.json:
        print(json.dumps({"file": str(args.docx.resolve()), "passed": not failed, "checks": [asdict(item) for item in checks]}, ensure_ascii=False, indent=2))
    else:
        for item in checks:
            mark = "OK" if item.passed else "FAIL"
            print(f"[{mark}] {item.check_id}: {item.description}")
            if item.evidence:
                print(f"  {item.evidence}")
        print("ПРОВЕРКА ПРОЙДЕНА" if not failed else f"ПРОВЕРКА НЕ ПРОЙДЕНА: отсутствуют блоки — {', '.join(item.check_id for item in failed)}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())

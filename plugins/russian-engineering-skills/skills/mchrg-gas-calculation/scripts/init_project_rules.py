from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timezone
from pathlib import Path


START = "<!-- MCHRG_TEMPLATE_BINDING_START -->"
END = "<!-- MCHRG_TEMPLATE_BINDING_END -->"
DEFAULT_TEMPLATE_NAME = "МЧРГ Боброво 76,7 м3ч II категория с приложением ТЗ подписи.docx"
DEFAULT_TEMPLATE_SHA256 = "8886656DCE6D1330570CDEBE15A857CD72D6B9938EE3DF772C6FFBC6AD8E8EAE"
MULTI_BUILDING_TEMPLATE_NAME = "Шаблон МЧРГ - несколько зданий.docx"
MULTI_BUILDING_TEMPLATE_SHA256 = "BB280237C279457A0C1EF71AEAFE07EC9F4949BBD8C9B8599DF4578DAE672DE5"


def bundled_template(building_count: int) -> Path:
    if building_count < 1:
        raise ValueError("Building count must be at least 1")
    if building_count > 1:
        name = MULTI_BUILDING_TEMPLATE_NAME
        expected = MULTI_BUILDING_TEMPLATE_SHA256
    else:
        name = DEFAULT_TEMPLATE_NAME
        expected = DEFAULT_TEMPLATE_SHA256
    template = Path(__file__).resolve().parent.parent / "assets" / "templates" / name
    if not template.is_file():
        raise FileNotFoundError(f"Bundled template does not exist: {template}")
    actual = sha256(template)
    if actual != expected:
        raise RuntimeError(
            "Bundled template was modified: "
            f"expected SHA-256 {expected}, actual {actual}"
        )
    return template


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def binding_block(template: Path | None) -> str:
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    if template is None:
        status = "НЕ ОПРЕДЕЛЕН — РЕДАКТИРОВАНИЕ DOCX ЗАПРЕЩЕНО"
        details = (
            "- Файл шаблона: не указан\n"
            "- SHA-256: не определен\n"
            "- Дата изменения файла: не определена"
        )
    else:
        template = template.resolve()
        if not template.is_file():
            raise FileNotFoundError(f"Template does not exist: {template}")
        if template.suffix.lower() != ".docx":
            raise ValueError(f"Template must be a DOCX file: {template}")
        modified = datetime.fromtimestamp(template.stat().st_mtime).astimezone().isoformat(timespec="seconds")
        status = "ЗАФИКСИРОВАН — ОБЯЗАТЕЛЕН ДЛЯ ТЕКУЩЕЙ ЗАДАЧИ МЧРГ"
        details = (
            f"- Файл шаблона: `{template}`\n"
            f"- SHA-256: `{sha256(template)}`\n"
            f"- Дата изменения файла: `{modified}`"
        )
    return (
        f"{START}\n"
        "## Привязка к шаблону крайней редакции\n\n"
        f"- Статус: **{status}**\n"
        f"{details}\n"
        f"- Привязка обновлена: `{now}`\n\n"
        "Использовать только этот шаблон. При указании пользователем новой редакции "
        "обновить привязку до дальнейшего создания или редактирования DOCX.\n"
        f"{END}"
    )


def replace_managed_block(text: str, block: str) -> str:
    start = text.find(START)
    end = text.find(END)
    if start < 0 and end < 0:
        return text.rstrip() + "\n\n" + block + "\n"
    if start < 0 or end < 0 or end < start:
        raise ValueError("AGENTS.md contains a damaged MCHRG_TEMPLATE_BINDING block")
    end += len(END)
    return text[:start].rstrip() + "\n\n" + block + "\n\n" + text[end:].lstrip()


def ensure_template_policy(text: str, base_rules: str) -> str:
    heading = "## Обязательная привязка к шаблону крайней редакции"
    old_rule = "Указанный пользователем шаблон DOCX является неизменяемым эталоном."
    new_rule = "Зафиксированный в блоке `MCHRG_TEMPLATE_BINDING` шаблон DOCX является неизменяемым эталоном."
    text = text.replace(old_rule, new_rule)
    if heading in text:
        return text
    policy_start = base_rules.index(heading)
    policy_end = base_rules.index("## Неизменность DOCX-шаблона", policy_start)
    policy = base_rules[policy_start:policy_end].strip()
    first_line_end = text.find("\n")
    if first_line_end < 0:
        return text.rstrip() + "\n\n" + policy + "\n"
    return text[:first_line_end].rstrip() + "\n\n" + policy + "\n\n" + text[first_line_end:].lstrip()


def ensure_formula_policy(text: str, base_rules: str) -> str:
    heading = "## Обязательная проверка полноты формул"
    if heading in text:
        return text
    policy_start = base_rules.index(heading)
    policy = base_rules[policy_start:].strip()
    binding_start = text.find(START)
    if binding_start >= 0:
        return text[:binding_start].rstrip() + "\n\n" + policy + "\n\n" + text[binding_start:].lstrip()
    return text.rstrip() + "\n\n" + policy + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create/update MChRG project rules and bind a DOCX template"
    )
    parser.add_argument("--project-root", required=True)
    parser.add_argument(
        "--template",
        help=(
            "Explicit DOCX template. If omitted, bind the immutable bundled "
            "template selected by --building-count."
        ),
    )
    parser.add_argument(
        "--building-count",
        type=int,
        default=1,
        help="Number of buildings. More than one selects the bundled multi-building template.",
    )
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    project_root.mkdir(parents=True, exist_ok=True)
    target = project_root / "AGENTS.md"
    asset = Path(__file__).resolve().parent.parent / "assets" / "AGENTS.md"
    base_rules = asset.read_text(encoding="utf-8")

    if target.exists():
        text = target.read_text(encoding="utf-8")
        if "# Правила подготовки расчета МЧРГ" not in text:
            text = text.rstrip() + "\n\n" + base_rules.rstrip() + "\n"
        else:
            text = ensure_template_policy(text, base_rules)
            text = ensure_formula_policy(text, base_rules)
    else:
        text = base_rules

    template = Path(args.template) if args.template else bundled_template(args.building_count)
    updated = replace_managed_block(text, binding_block(template))
    target.write_text(updated, encoding="utf-8", newline="\n")
    print(target)


if __name__ == "__main__":
    main()

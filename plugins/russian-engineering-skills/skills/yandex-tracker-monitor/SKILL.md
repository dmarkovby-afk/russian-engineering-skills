---
name: yandex-tracker-monitor
description: "Мониторить Яндекс Трекер через API и собирать отчеты по очередям и исполнителям: просрочки, блокеры, приоритеты, сроки и статусы задач. Используй, когда нужно ежедневное наблюдение за проектами в Tracker, управленческая сводка по всем исполнителям или персональный отчет по выбранному исполнителю."
---

# Yandex Tracker Monitor

Запускай мониторинг через скрипт:

`powershell -ExecutionPolicy Bypass -File $env:USERPROFILE\.codex\skills\yandex-tracker-monitor\scripts\tracker_morning_report.ps1`

## Обязательные переменные окружения

Перед запуском убедись, что заданы:

- `TRACKER_TOKEN`
- `TRACKER_ORG_ID`

Опционально:

- `TRACKER_AUTH_SCHEME` (`OAuth` по умолчанию)
- `TRACKER_ORG_HEADER` (`X-Org-ID` по умолчанию, может быть `X-Cloud-Org-ID`)
- `TRACKER_QUEUE_KEYS` (через запятую, например `DEV,SUP,OPS`)

## Режимы запуска

- Общий отчет по очередям и всем исполнителям:
  `powershell -ExecutionPolicy Bypass -File $env:USERPROFILE\.codex\skills\yandex-tracker-monitor\scripts\tracker_morning_report.ps1`
- Отчет только по одному исполнителю:
  `powershell -ExecutionPolicy Bypass -File $env:USERPROFILE\.codex\skills\yandex-tracker-monitor\scripts\tracker_morning_report.ps1 -Assignee "Имя или логин"`
- JSON для дальнейшей обработки:
  `powershell -ExecutionPolicy Bypass -File $env:USERPROFILE\.codex\skills\yandex-tracker-monitor\scripts\tracker_morning_report.ps1 -AsJson`

## Что делает скрипт

1. Загружает открытые задачи по очередям.
2. Если ключи очередей не переданы параметром и не заданы в `TRACKER_QUEUE_KEYS`, получает список очередей из API.
3. Собирает сводку по очередям.
4. Собирает сводку по каждому исполнителю.
5. Для каждого исполнителя показывает список задач со сроком, статусом и очередью.
6. При использовании `-Assignee` строит персональный отчет только по выбранному исполнителю.

## Требования к итоговой сводке

1. Не показывай токены, ID и другие чувствительные данные.
2. Показывай конкретные ключи задач, сроки, статусы и краткий смысл риска.
3. Если отчет общий, сначала дай короткий вывод по очередям, затем блок по исполнителям.
4. Если отчет персональный, сфокусируй вывод на выбранном исполнителе и его задачах.
5. Если API недоступен, верни понятную диагностику и шаги восстановления.
6. Всегда выводи итоговую сводку прямо в текущий диалог, обычным текстом или markdown.
7. Не перенаправляй итог в файл, если пользователь отдельно не попросил сохранить отчет.

## Saved Audit Baseline

Перед рекомендациями по реорганизации процессов прочитай:

`$env:USERPROFILE\.codex\skills\yandex-tracker-monitor\references\audit-2026-04-14.md`

Rules:

1. Use this file as the current factual baseline.
2. Do not invent missing process rules or SLA targets.
3. Ask user for all missing clarifications listed in the baseline.
4. Provide final reconfiguration roadmap only after clarifications are answered.

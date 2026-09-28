# AutoCAD LT для оцифровки

На этой машине рабочий консоль:

`C:\Program Files\Autodesk\AutoCAD LT 2025\accoreconsole.exe`

Есть также LT 2022 и LT 2023. Скрипт `scripts/convert_to_dwg.ps1` берёт LT 2025, затем более новые/старые `accoreconsole.exe` из `C:\Program Files\Autodesk`.

## Правила

- Исходный DXF не открывать «поверх» пользовательского чертежа. Копировать в `C:\Temp\ocsifrovka_work`.
- Кириллические пути для Core Console хрупкие: и DXF, и SCR, и выходной DWG — ASCII.
- `FILEDIA=0`, `CMDDIA=0`.
- В выдаваемом DWG не должно быть IMAGE, PDFUNDERLAY, OLE.
- После SAVEAS в рабочей копии допустим `AUDIT`.

## Конвертация

```powershell
powershell -NoProfile -File scripts/convert_to_dwg.ps1 -Dxf "C:\Temp\ocsifrovka_work\scheme.dxf" -OutDwg "C:\Temp\ocsifrovka_work\scheme.dwg"
```

Скрипт копирует DXF в temp, гоняет `scripts/saveas_dwg.lsp`, копирует DWG обратно.

Если команда `SAVEAS` в LT отвергает формат `LT2018`, LSP пробует `2018` и `LT2013`. Лог — `accore_saveas.log` рядом с temp-копией.

## Что не делать

- Не публиковать PDF вместо DWG, если просили DWG.
- Не считать успешным файл, который открывается только как растр.
- Не запускать интерактивный AutoCAD и не закрывать сессию пользователя.
- Контрольный PNG для сверки делать `render_preview.py`, а не плоттером, пока идёт подгонка сцены.

# Схема scene.json

Файл — единственный редактируемый источник геометрии. DXF собирается скриптом, а не вручную.

Координаты: миллиметры листа, X вправо, Y вверх, (0,0) — левый нижний угол. Это CAD, не пиксели фото. Перевод пикселей:

```text
x_mm = x_px * width_mm / width_px
y_mm = height_mm - y_px * height_mm / height_px
```

Пиксели исходника — начало в левом верхнем углу.

## Корень

```json
{
  "meta": {
    "title": "Схема ГРУ ...",
    "source": "source.jpg",
    "paper": {
      "format": "A3",
      "orientation": "landscape",
      "width_mm": 420,
      "height_mm": 297
    },
    "default_lineweight": 0.35,
    "text_height": 2.5,
    "draw_frame": false
  },
  "pipes": [],
  "symbols": [],
  "texts": [],
  "leaders": [],
  "arrows": [],
  "hatches": [],
  "primitives": [],
  "unreadable": []
}
```

Поля `pipes` / `symbols` / `texts` обязательны (могут быть пустыми массивами). Остальные массивы опциональны.

## paper.format

`A4` `A3` `A2` `A1` или `custom`. Для `custom` обязательны `width_mm` и `height_mm`. Ориентация `landscape` или `portrait` меняет стороны стандартного формата.

`meta.draw_frame` по умолчанию `false`: контур листа и рамка не рисуются. Ставить `true` только по прямой просьбе пользователя.

## pipes[]

```json
{
  "id": "p-inlet",
  "points": [[40, 150], [200, 150], [200, 80]],
  "dn": 100,
  "width": 0.5,
  "layer": "PIPES"
}
```

- `points` — минимум две точки.
- `dn` — справочно, на геометрию не влияет, если задан `width`.
- Если `width` нет, взять `meta.default_lineweight`.
- Ломаные с углом 45° допустимы. Не спрямлять изометрию исходника в ортогональ.
- Не упрощать: число изломов, параллельные байпасы и положение узла должны совпадать с фото, а не с «удобной» схемой.

## symbols[]

```json
{
  "id": "v1",
  "type": "valve_ball",
  "pos": [120, 150],
  "rotation": 0,
  "scale": 1,
  "layer": "FITTINGS",
  "attrs": { "size": 8 }
}
```

- `type` — имя из [symbols.md](symbols.md).
- `pos` — точка вставки на оси трубы.
- `rotation` — градусы против часовой, 0 = локальная ось символа вдоль +X (поток вправо). Вертикальная труба: `90` или `-90`.
- `scale` по умолчанию 1.
- Не дублировать геометрию символа примитивами, если тип есть в каталоге.

## texts[]

```json
{
  "text": "Кран шаровой",
  "pos": [120, 162],
  "height": 2.5,
  "rotation": 0,
  "halign": "center",
  "valign": "bottom",
  "layer": "TEXT"
}
```

- `halign`: `left` `center` `right`
- `valign`: `bottom` `middle` `top`
- Текст копировать буквально. Индекс/степень: `кгс/см2` допустим, если верхний индекс на фото ненадёжно читается; если видно `см²` — писать `см²`.

## leaders[]

```json
{ "p1": [120, 154], "p2": [120, 160], "layer": "THIN" }
```

Тонкая выноска от аппарата к полке текста. Не путать с трубой.

## arrows[]

```json
{ "pos": [90, 150], "rotation": 0, "size": 3, "layer": "PIPES" }
```

Стрелка потока. `rotation` 0 — остриё в +X.

## hatches[]

```json
{
  "points": [[50, 148], [90, 148], [90, 152], [50, 152]],
  "pattern": "ANSI31",
  "scale": 1.5,
  "layer": "HATCH"
}
```

Для заштрихованных участков труб на исходнике.

## primitives[]

Только уникальная геометрия, которой нет в каталоге УГО:

```json
{ "kind": "line", "p1": [10, 10], "p2": [40, 10], "layer": "FRAME" }
{ "kind": "rect", "p1": [300, 250], "p2": [400, 290], "layer": "FRAME" }
{ "kind": "circle", "center": [80, 80], "r": 5, "layer": "INSTR" }
{ "kind": "arc", "center": [80, 80], "r": 5, "a1": 0, "a2": 90, "layer": "INSTR" }
{ "kind": "polyline", "points": [[0, 0], [10, 0], [10, 10]], "closed": true, "layer": "FRAME" }
```

## unreadable[]

```json
{ "region": [180, 140, 220, 170], "note": "блик на марке фильтра" }
```

`region` — `xmin ymin xmax ymax` в мм. Каждая такая запись должна попасть в `report.md`.

## Слои

Если `layer` не указан, скрипт ставит:

| объект | слой |
|---|---|
| pipes, arrows | PIPES |
| symbols арматуры | FITTINGS |
| manometer* | INSTR |
| texts | TEXT |
| leaders | THIN |
| hatches | HATCH |
| primitives | 0 |

Не создавать слой под каждый объект.

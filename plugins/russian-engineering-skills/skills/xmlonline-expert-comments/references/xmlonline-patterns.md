# XMLonline Patterns

## Frequent Fields

- `ExplanatoryNote`: root explanatory note section.
- `UsedNorms`: list of documents whose application ensures compliance with technical regulations and other requirements.
- `UsedNorm`: one row inside `UsedNorms`; usually an `input[name="UsedNorm"]`.
- `DesignerNote`: free-form explanatory note rows used for additional descriptions.
- `IndustrialSafetyLinks`: rows that link industrial safety requirements to project sections.
- `Resources`: resource/consumption rows.

## Useful Checks

Use a bounded browser-side read to inspect fields:

```js
const vals = Array.from(document.querySelectorAll('input[name="UsedNorm"]'))
  .map((el, idx) => ({
    idx,
    id: el.id,
    dataId: el.getAttribute('data-id'),
    value: el.value,
    visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length),
  }));
```

For each added item, check by a stable key, not by the full long title only:

```js
const count = vals.filter(x => x.value.includes('СанПиН 2.1.3684-21')).length;
```

Also check:

- no blank rows: `vals.filter(x => !x.value.trim())`;
- no duplicates for the affected keys;
- target block row count changed as expected;
- edited rows are visible after expanding the parent section.

## Adding Rows

For `UsedNorms`, the add button is usually scoped like:

```css
#UsedNorms<id> .btn.btn-secondary.mb-3
```

Do not click a global `+ Добавить`; scope the button to the exact container.

Sequence:

1. Count current `input[name="UsedNorm"]`.
2. Click the scoped `+ Добавить`.
3. Find the newly created last input.
4. Fill it.
5. Re-check the added key and blank rows.

## Deleting Rows

Repeated rows usually have an enclosing row with `data-id="<row id>"` and a trash button:

```css
[data-id="<row id>"].row .btn.btn-fix-width.btn-outline-danger
```

Before deletion, verify:

- the row value exactly matches the duplicate or wrong text;
- another correct row remains;
- deletion is scoped to the intended list.

Accept confirmation only after these checks.

## Typical Reply Locations

When replying to an expert comment, name the path in plain Russian:

- `раздел 1 «Пояснительная записка»`;
- `блок «Перечень документов, в результате применения которых обеспечивается соблюдение требований технических регламентов и иных требований…»`;
- `блок «Идентификационные признаки объекта по требованиям пожарной безопасности»`;
- `блок со ссылками на разделы/пункты проектной документации`.

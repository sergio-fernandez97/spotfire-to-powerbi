# Spotfire → DAX reference

`dxp2pbi` already applies the rows marked **rule**. Everything else is for you (Claude) or a
person, recorded in `translations.json` with `status: "ai"` / `"human"`.

## Aggregations (visual value axes → measures)

| Spotfire | DAX | Notes |
|---|---|---|
| `Sum([c])` | `SUM('T'[c])` | **rule** |
| `Avg([c])` | `AVERAGE('T'[c])` | **rule** |
| `Min` / `Max` / `Median` | `MIN` / `MAX` / `MEDIAN` | **rule** |
| `Count([c])` | `COUNT` (numeric) / `COUNTA` (other) | **rule** |
| `Count()` | `COUNTROWS('T')` | **rule** |
| `UniqueCount([c])` | `DISTINCTCOUNTNOBLANK('T'[c])` | **rule**; both ignore empty values |
| `StdDev` / `Var` | `STDEV.S` / `VAR.S` | **rule** |
| `First([c])` / `Last([c])` | `FIRSTNONBLANK('T'[c], 1)` / `LASTNONBLANK('T'[c], 1)` | Spotfire uses row order, DAX has none: say so in `notes`, or use MIN/MAX if the value is constant per group |
| `Percentile([c], p)` | `PERCENTILE.INC('T'[c], p / 100)` | |
| `a / b` of aggregations | `DIVIDE(a, b)` | **rule** for a single top-level division |
| `… as [Alias]` | measure named `Alias` | **rule**; renamed if it clashes with a column |

## OVER (Spotfire's windowing) → CALCULATE / window functions

| Spotfire | DAX pattern |
|---|---|
| `X OVER (All([Axis.X]))` | `CALCULATE([X], REMOVEFILTERS('T'[xcol]))` |
| `X / X OVER (All([Axis.Color]))` (share) | `DIVIDE([X], CALCULATE([X], REMOVEFILTERS('T'[colorcol])))` |
| `X OVER (Intersect(Parent([Axis.X]), …))` | percent of parent: `CALCULATE([X], ALLEXCEPT('T', 'T'[parentcol]))` |
| `X OVER (AllPrevious([Axis.X]))` (running total) | `CALCULATE([X], FILTER(ALLSELECTED('T'[xcol]), 'T'[xcol] <= MAX('T'[xcol])))`, or `DATESYTD` for dates |
| `X OVER (Previous([Axis.X]))` | `CALCULATE([X], OFFSET(-1, ALLSELECTED('T'[xcol]), ORDERBY('T'[xcol])))` |
| `X OVER (FirstNode([Axis.X]))` | `CALCULATE([X], INDEX(1, ALLSELECTED('T'[xcol]), ORDERBY('T'[xcol])))` |

`[Axis.X]` means "whatever is on the X axis of the visual". Look it up in `spec.json` →
`pages[].visuals[].axes` for the visual the expression comes from, and name that column
explicitly. If the axis is `BinByDateTime(...)`, use the date column, and use time intelligence
where it fits.

## Calculated columns

| Spotfire | DAX |
|---|---|
| `case when c1 then v1 … else v end` | `SWITCH(TRUE(), c1, v1, …, v)` — **rule** for simple conditions |
| `If(c, a, b)` | `IF(c, a, b)` |
| `a & b`, `Concatenate(a, b, …)` | `a & b & …` |
| `Upper` / `Lower` / `Trim` / `Len` | `UPPER` / `LOWER` / `TRIM` / `LEN` |
| `Left(s, n)` / `Right(s, n)` / `Mid(s, start, n)` | `LEFT` / `RIGHT` / `MID` (both 1-based) |
| `Substitute(s, a, b)` | `SUBSTITUTE(s, a, b)` |
| `Round(x, n)` / `Abs` / `Sqrt` | `ROUND` / `ABS` / `SQRT` |
| `Ln(x)` / `Log10(x)` / `Log(x, b)` | `LN` / `LOG10` / `LOG(x, b)` |
| `Year` / `Month` / `Day` / `Quarter` / `Week` | `YEAR` / `MONTH` / `DAY` / `QUARTER` / `WEEKNUM` |
| `DateDiff("day", d1, d2)` | `DATEDIFF(d1, d2, DAY)` |
| `DateAdd("month", n, d)` | `EDATE(d, n)` (months) / `d + n` (days) |
| `DateTimeNow()` / `Today()` | `NOW()` / `TODAY()` |
| `SN(x, v)` | `COALESCE(x, v)` |
| `IsNull(x)` | `ISBLANK(x)` |
| `Rank([c])` | `RANKX(ALL('T'), 'T'[c])` |
| `BinByEvenIntervals` / `BinByEvenDistribution` / `BinBySpecificLimits` | `SWITCH(TRUE(), …)` over **explicit** thresholds. Spotfire computes the bins from the data, so state the thresholds you chose in `notes`, or mark `unsupported` |
| `RowId()` / `BaseRowId()` | no DAX equivalent. Add an index column in Power Query (Phase 2), so mark `unsupported` |
| `[${property}]` / `${property}` | document property: use a field parameter or a what-if parameter, so mark `unsupported` unless the user gives a fixed value |
| `TERR_*`, `R_*`, `Python_*` | inline R/Python: mark `unsupported` |

## Gotchas

- **Empty values:** Spotfire arithmetic with an empty value gives empty. DAX treats BLANK as 0 in
  `+ - *`. Guard with `IF(ISBLANK(...), BLANK(), ...)` when it matters.
- **Text comparison:** DAX text comparisons are case-insensitive. Note it if the Spotfire logic
  depends on case.
- **Long literals:** Spotfire writes long integers as `10000000000l`. Drop the `l`.
- **Column names:** column names with `]` are escaped as `]]` in both languages. Table names always
  go in single quotes in DAX.

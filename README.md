# Spotfire → Power BI migration

Turn a Spotfire analysis (`.dxp`) into a Power BI semantic model (`.tmdl`) plus a reference
document for rebuilding the report.

Works on macOS. Spotfire is not needed, and Power BI is not needed until the last step.

```
.dxp  ──①──►  reference document   ──②──►  .tmdl semantic model  ──③──►  Power BI report
   export      spec.md + spec.json        tables, columns, measures      you build the visuals
   (manual)    (this repo)                (this repo)                    (Power BI Desktop)
```

Steps ① and ② are what this repo automates — steps 2 and 3 of the flow diagram. Building the
report visuals is still manual, and the reference document gives you the checklist for it.

---

## Migrate a `.dxp`, start to finish

### Before you start

You need two things:

1. **The `.dxp` file**, exported from Spotfire (File → Save As → file).
2. **The data file it reads** (CSV, Excel…). **A `.dxp` does not contain its data** — only the
   path on the author's machine, such as `\\Mac\Home\Downloads\Viajes2024.csv`. Ask whoever
   exported the analysis for the data file too.

Put the `.dxp` in `data/`.

### Step 1 — run the pipeline

From the repo root:

```sh
uv run --project dxp2pbi dxp2pbi all "data/Viajes2024.dxp"
```

This reads the file, writes the reference document, translates the formulas it can, generates the
semantic model and checks it. Expect output like:

```
Viajes2024: 1 tables, 18 columns, 1 pages, 1 visuals, 3 expressions, 3 risks -> out/Viajes2024
Viajes2024: translations not_applicable=2, rule=1
Viajes2024: wrote out/Viajes2024/Viajes2024.SemanticModel (0 TODO)
Viajes2024.SemanticModel: OK (0 errors, 0 warnings)
```

Read that last line as: the model is structurally valid. `TODO` means something needs a human or
AI decision; those spots hold a `BLANK()` placeholder so the model still loads.

Everything lands in `out/<analysis>/`:

| File | What it is |
|---|---|
| `spec.md` | **The reference document.** Read this one. |
| `spec.json` | The same content for machines; everything else is generated from it. |
| `translations.json` | Each Spotfire formula and its Power BI equivalent. |
| `<analysis>.SemanticModel/` | **The Power BI model** in TMDL format. |
| `preview.png` | The Spotfire thumbnail, to compare against. |

### Step 2 — read the reference document

Open `out/<analysis>/spec.md`. It has:

1. **Data sources** — every file the analysis reads, with its settings (separator, encoding, sheet).
2. **Data model** — each table's columns, their Spotfire type and the matching Power BI type.
3. **Relationships** — how the tables join.
4. **Expressions** — every Spotfire formula, where it is used, and its Power BI translation.
5. **Pages and visuals** — a checklist for rebuilding the report, with a suggested Power BI visual
   for each Spotfire one, and the fields on every axis.
6. **Scripts and data functions** — IronPython and R/TERR, which have no Power BI equivalent.
7. **Migration risks** — ranked high / medium / low.

### Step 3 — finish the formulas with Claude Code

Simple formulas are translated automatically (`Sum([Tarifa])` → `SUM('Viajes2024'[Tarifa])`).
Harder ones — `OVER`, data-driven binning, document properties — are deliberately left alone
rather than guessed. To finish them, ask Claude Code in this repo:

```
/dxp-tmdl out/Viajes2024
```

It translates the open items, regenerates the model and validates it. Two other skills:

| Skill | Use it for |
|---|---|
| `/dxp-migrate` | Everything below, for one file or a folder, in one go |
| `/dxp-spec` | Writing the overview and migration assessment in `spec.md` |
| `/dxp-tmdl` | Translating the remaining formulas and rebuilding the model |

Whenever a `.tmdl` or `translations.json` changes, a hook re-validates automatically and reports
errors back to Claude.

> Edit `translations.json`, never the `.tmdl` files — those are regenerated from it every time.

### Step 4 — open it in Power BI (Windows)

The generated model is a folder, not a `.pbix`. To open it you need **Power BI Desktop on
Windows**, with *File → Options → Preview features → Power BI Project (.pbip)* enabled.

1. Copy `out/<analysis>/<analysis>.SemanticModel` to the Windows machine, next to the data file.
2. Create a `<analysis>.pbip` file beside it, plus a `<analysis>.Report` folder for the (still
   empty) report:

   ```json
   {
     "version": "1.0",
     "artifacts": [{ "report": { "path": "<analysis>.Report" } }]
   }
   ```

   This wrapper is written from Microsoft's PBIP documentation and has not been tested here —
   if Power BI Desktop rejects it, create an empty `.pbip` project in Desktop instead and copy
   the generated `definition/` folder into its `.SemanticModel`.
3. Open the `.pbip` in Power BI Desktop.
4. **Point it at your data:** Transform data → Manage parameters → set `CsvPath` (or `ExcelPath`)
   to the real path of the data file. This is the only edit the model needs.
5. Refresh. The tables, columns and measures load.

> Not yet verified: no generated model has been opened in Power BI Desktop, because this was built
> on a Mac. The checks so far are structural. See
> [`docs/phase1-gap-report.md`](docs/phase1-gap-report.md).

### Step 5 — rebuild the report

Work through section 5 of `spec.md`, one visual at a time, using `preview.png` as the target.
Section 5 gives you the Spotfire visual type, the suggested Power BI visual, the table, and the
field on every axis.

---

## What does not migrate automatically

| Thing | Why | What to do |
|---|---|---|
| The data itself | A `.dxp` stores only the path | Get the CSV/Excel file from the author |
| SBDF files (Spotfire's own format) | Power BI cannot read SBDF | Re-export as CSV from Spotfire |
| Map geometry (shapefiles, binary columns) | Not importable | Use Power BI maps / Azure Maps geography |
| Tags columns (a saved Spotfire selection) | No equivalent | Dropped on purpose |
| IronPython scripts, R/TERR functions | No equivalent | Re-implement upstream, or drop |
| Report visuals | Phase 2 of this project | Build by hand from the checklist |
| Cardinality of relationships | Spotfire does not store it | Emitted as many-to-many; tighten it in Power BI |

---

## Commands

```sh
uv run --project dxp2pbi dxp2pbi all data/*.dxp          # everything, for each file
uv run --project dxp2pbi dxp2pbi spec data/X.dxp         # reference document only
uv run --project dxp2pbi dxp2pbi translate out/X         # re-apply rules (keeps AI/human edits)
uv run --project dxp2pbi dxp2pbi tmdl out/X              # rebuild the model and validate
uv run --project dxp2pbi dxp2pbi validate out/           # check every generated model
uv run --project dxp2pbi dxp2pbi inspect data/X.dxp      # what is inside a .dxp
```

## Repo layout

| Path | What |
|---|---|
| `data/` | Source `.dxp` files |
| `out/` | Generated output, one folder per analysis (gitignored) |
| `dxp2pbi/` | The tool — see [`dxp2pbi/README.md`](dxp2pbi/README.md) for internals |
| `.claude/` | Claude Code skills and the validation hook |
| `docs/` | [Gap report](docs/phase1-gap-report.md) and Spotfire API research |

## Requirements

[uv](https://docs.astral.sh/uv/) and Python 3.12. Dependencies install themselves on first run.
Tests: `cd dxp2pbi && uv run pytest`.

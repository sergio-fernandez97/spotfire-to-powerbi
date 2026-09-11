---
name: dxp-migrate
description: Run the full Spotfire → Power BI phase-1 pipeline for one .dxp or a folder of them: reference document, expression translation, TMDL semantic model and validation, then summarize. Use when the user asks to migrate, convert or process .dxp files end to end.
---

# dxp-migrate — end-to-end phase 1 for one file or a folder

## Steps

1. Run the deterministic pipeline (from the repo root). It takes one or more `.dxp` paths:

   ```sh
   uv run --project dxp2pbi dxp2pbi all "<file.dxp>" ...
   ```

   For each analysis it writes `out/<analysis>/`: `spec.json`, `spec.md`, `translations.json`
   and `<analysis>.SemanticModel/`, then validates the model.

2. For each analysis, apply the **dxp-spec** skill steps 2–4: fill in the narrative and
   assessment blocks of `spec.md`.

3. For each analysis, apply the **dxp-tmdl** skill steps 2–6: translate the `needs_review`
   items, regenerate and validate.

4. Finish with one summary table, one row per analysis:

   | Analysis | Tables | Visuals | Measures ready / total | TODOs | High risks | Validation |
   |---|---|---|---|---|---|---|

   Then list what the team must provide before step 4 of the diagram (project integration).
   Typically that is the data files behind the CSV/Excel paths, SBDF files re-exported as CSV,
   and a decision on each `unsupported` item.

## Rules

- Never edit `.tmdl` files directly. Change `translations.json` and regenerate.
- Stop and ask if validation still fails after two fix attempts on the same item.
- Power BI Desktop is not available on this Mac. Say that the final check (opening the model in
  Power BI Desktop, diagram step 5) is still pending.

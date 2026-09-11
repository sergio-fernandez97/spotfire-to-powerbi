---
name: dxp-spec
description: Extract the Power BI migration reference document (spec.json + spec.md) from a Spotfire .dxp file and write its narrative and assessment sections. Use when the user wants to analyze, document, inventory or assess a .dxp for migration.
---

# dxp-spec — reference document for one Spotfire analysis

The parser is deterministic; your job is only the parts that need judgement: the business
narrative and the migration assessment. Never re-derive structure by reading the XML yourself.

## Steps

1. From the repo root run:

   ```sh
   uv run --project dxp2pbi dxp2pbi spec "<path/to/file.dxp>"
   ```

   It writes `out/<analysis>/spec.json` (source of truth), `spec.md` (reference document) and
   `preview.png` (Spotfire thumbnail, when the file has one).

2. Read `spec.json` and look at `preview.png`.

3. In `spec.md`, replace the text between `<!-- narrative:begin -->` and `<!-- narrative:end -->`
   with 3–6 sentences: what the analysis is for, who likely uses it, which questions it answers.
   Base it only on page titles, visual titles, text-area text, table and column names. When you
   infer, say so ("probably", "appears to").

4. Replace the text between `<!-- assessment:begin -->` and `<!-- assessment:end -->` with:
   - **Effort**: S / M / L, with the reason (tables, visuals, expressions needing review).
   - **Blockers**: every `high` risk, and what is needed to clear it (e.g. "the SBDF files re-exported as CSV").
   - **Automatic vs manual**: what `dxp2pbi` will generate (model, measures) and what stays manual
     (visuals, scripts, map layers).
   - **Recommended order** of work.

5. Edit nothing else in `spec.md`: everything outside the two blocks is regenerated. Re-running
   `dxp2pbi spec` keeps both blocks.

## Rules

- Do not invent data sources, columns or formulas that are not in `spec.json`.
- If `spec.json` has `unparsed` entries, mention them in the assessment.
- Write in the language the user is using.
- Next step is the `dxp-tmdl` skill.

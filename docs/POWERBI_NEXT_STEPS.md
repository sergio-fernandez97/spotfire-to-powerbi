## Software
- Power BI Desktop on Windows, with File → Options → Preview features → Power BI Project (.pbip) turned on. You're on Windows, so you can do this on this machine.

## Files, per analysis
1. The generated model: out/<analysis>/<analysis>.SemanticModel/. The pipeline doesn't create a .pbix.
2. A .pbip wrapper next to it, plus an empty <analysis>.Report folder:
{ "version": "1.0", "artifacts": [{ "report": { "path": "<analysis>.Report" } }] }
   This wrapper has never been tested. If Desktop rejects it, create an empty .pbip project in Desktop and copy the generated definition/ folder into its .SemanticModel.

## Data, depending on the source
- CSV/Excel analyses (Viajes2024 and the other demo files): you need the actual data files. A .dxp only stores a path, such as \\Mac\Home\Downloads\Viajes2024.csv. Any SBDF files have to be re-exported from Spotfire as CSV first.
- Snowflake analyses (Customers, LINEITEM):
  - an overrides.json for each, so the model points at PBI_WH / PBI_READER / SNOWFLAKE_SAMPLE_DATA
  - the PBI_SVC login with the PAT as the password. If Desktop rejects the PAT, sign in with your admin user.
  - your current public IP in the PBI_NP network policy

## In Desktop
1. Open the .pbip.
2. Go to Transform data → Manage parameters and set either:
   - CsvPath / ExcelPath, or
   - SnowflakeServer, SnowflakeWarehouse, SnowflakeDatabase and SnowflakeRole
3. Refresh, and check the row counts. CUSTOMER should have 150,000 rows. LINEITEM runs as DirectQuery.

## The report itself
After the refresh you'll have a model but no report: the visuals aren't migrated automatically yet. You rebuild them by hand from section 5 of spec.md, using preview.png as the target.
# Snowflake path: next steps

Follows [`SNOWFLAKE_SETUP.md`](SNOWFLAKE_SETUP.md), after the connection details are in `~/.zshrc`.

## 1. Restart Claude Code

The `SNOWFLAKE_*` variables are set in your interactive zsh, but a Claude Code session started
before you added them can't see them. Restart it, or open a new terminal and launch it again.

## 2. Connect Snowflake to Claude Code

The project's `.mcp.json` defines a `snowflake` server: a local Snowflake-Labs MCP server that
connects as `PBI_SVC` using the `SNOWFLAKE_*` variables. `.claude/snowflake_mcp.yaml` allows only
`SELECT`, `DESCRIBE` and `SHOW`, and `.claude/settings.json` approves the server and its
`run_snowflake_query` tool. See [setup step 9](SNOWFLAKE_SETUP.md). Restart Claude Code, then check
`/mcp`.

## 3. Give each analysis an `overrides.json`

The `.dxp` files are missing some connection facts:

| Analysis | Current state | What to override |
|---|---|---|
| `Customers_SnowflakeConexion_RefreshData` | Spotfire connected through an ODBC DSN (`Snowflake_ODBC`). The model has **3 TODOs**: server, warehouse and database. | `server`, `warehouse: PBI_WH`, `database: SNOWFLAKE_SAMPLE_DATA`, `role: PBI_READER` |
| `LINEITEM_SnowflakeConexion_LiveData` | The `.dxp` has the full connection details and the model has 0 TODOs, but they point to `COMPUTE_WH` and role `USERADMIN`. | `warehouse: PBI_WH`, `role: PBI_READER`, so the model uses your read-only service user |

For example, `out/Customers_SnowflakeConexion_RefreshData/overrides.json`:

```json
{
  "sources": {"src1": {"server": "<ORGNAME-ACCOUNTNAME>.snowflakecomputing.com",
                       "warehouse": "PBI_WH", "role": "PBI_READER",
                       "database": "SNOWFLAKE_SAMPLE_DATA"}}
}
```

The LINEITEM `.dxp` points at `zqxuaeu-pu21602.snowflakecomputing.com`. If that's your trial
account, use the same server here. Credentials never go in this file.

Once Snowflake is connected, also add `column_types` from `DESCRIBE TABLE`. That way
`NUMBER(p,0)` keys like `C_CUSTKEY` become whole numbers (`int64`) instead of decimals.

## 4. Rebuild and validate both models

```sh
uv run --project dxp2pbi dxp2pbi tmdl "out/Customers_SnowflakeConexion_RefreshData"
uv run --project dxp2pbi dxp2pbi tmdl "out/LINEITEM_SnowflakeConexion_LiveData"
```

You should see `0 TODO` and `OK`. The `/dxp-tmdl out/<analysis>` skill does steps 3 and 4 for
you once Snowflake is connected.

## 5. Open the models in Power BI Desktop on Windows

See README step 4.

- Set the `Snowflake*` parameters.
- Sign in as `PBI_SVC` with the PAT as the password.
- Refresh, and compare the row counts against Snowflake: CUSTOMER should have 150,000 rows.
  LINEITEM will run as DirectQuery.

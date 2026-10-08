# Snowflake setup

1. **Sign up for Snowflake.**
   - Go to [signup.snowflake.com](https://signup.snowflake.com). The trial lasts 30 days, includes about $400 in credits, and does not require a credit card.
   - Choose the Standard edition, Azure, and the region closest to your Power BI tenant (for example, West Europe).
   - Activate your account from the email, create an admin username and password, and set up MFA.

2. **Get your account identifier.**
   - In Snowsight, open the account menu at the bottom left and select **Connect a tool to Snowflake** or **View account details**.
   - Copy the account identifier (`ORGNAME-ACCOUNTNAME`) and server URL (`<identifier>.snowflakecomputing.com`).

3. **Open a SQL worksheet.** All SQL in this guide runs in Snowsight, the web UI you land on after signing in (`https://app.snowflake.com`).
   - In the left navigation, select **+ Create** (top left) → **SQL Worksheet**. Alternatively, go to **Projects → Workspaces** (newer accounts) or **Projects → Worksheets** (older accounts) and select **+** → **SQL File** / **SQL Worksheet**.
   - At the top of the editor, open the context selector (it shows the current role and warehouse) and set:
     - **Role:** `ACCOUNTADMIN` (the default for the trial admin user)
     - **Warehouse:** `COMPUTE_WH` (created with the trial). Steps 4–6 don't need a running warehouse, but the selector requires one.
   - You don't need to pick a database or schema; every statement below uses fully qualified names.
   - Rename the worksheet (click its title), for example to `pbi_setup`, so you can find it again under **Projects**.

4. **Check the sample data.**
   - Go to **Data → Databases** (called **Catalog → Database Explorer** in newer accounts) and look for `SNOWFLAKE_SAMPLE_DATA`.
   - If it is missing, run this in the `pbi_setup` worksheet:

     ```sql
     CREATE DATABASE SNOWFLAKE_SAMPLE_DATA FROM SHARE SFC_SAMPLES.SAMPLE_DATA;
     ```

Steps 4–6 can go in one worksheet with the role set to `ACCOUNTADMIN`. Run them with **Run All** (Cmd+Shift+Enter) only once: the `CREATE` and `ADD PROGRAMMATIC ACCESS TOKEN` statements fail if the objects already exist, so after a partial failure, select and run only the remaining statements.

4. **Create a read-only role, warehouse, and user.** Run this in a worksheet as `ACCOUNTADMIN`:

   ```sql
   CREATE ROLE PBI_READER;
   CREATE WAREHOUSE PBI_WH
     WAREHOUSE_SIZE = XSMALL
     AUTO_SUSPEND = 60
     AUTO_RESUME = TRUE
     INITIALLY_SUSPENDED = TRUE;
   GRANT USAGE ON WAREHOUSE PBI_WH TO ROLE PBI_READER;
   GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE_SAMPLE_DATA TO ROLE PBI_READER;

   CREATE USER PBI_SVC
     TYPE = SERVICE
     DEFAULT_ROLE = PBI_READER
     DEFAULT_WAREHOUSE = PBI_WH;
   GRANT ROLE PBI_READER TO USER PBI_SVC;
   ```

5. **Allow your IP for that user only.** Snowflake requires a network policy for a user to authenticate with a programmatic access token.
   - Find your public IP (for example, at [whatismyip.com](https://www.whatismyip.com)), then run:

     ```sql
     CREATE NETWORK POLICY PBI_NP ALLOWED_IP_LIST = ('<your.public.ip>');
     ALTER USER PBI_SVC SET NETWORK_POLICY = PBI_NP;
     ```

   - Do not set the policy at the account level; you could lock yourself out when your IP changes.

6. **Create a programmatic access token (PAT).** Run:

   ```sql
   ALTER USER PBI_SVC ADD PROGRAMMATIC ACCESS TOKEN MCP_TOKEN
     ROLE_RESTRICTION = 'PBI_READER'
     DAYS_TO_EXPIRY = 30;
   ```

   Copy `token_secret` immediately; it is shown only once. Do not paste it into this chat.

7. **Smoke test.** `PBI_READER` is granted only to `PBI_SVC`, so first grant it to your admin user (still as `ACCOUNTADMIN`):

   ```sql
   GRANT ROLE PBI_READER TO USER <your_admin_username>;
   ```

   Replace `<your_admin_username>` with the user you sign in to Snowsight with (the admin you created in step 1, not `PBI_SVC`). If you're not sure what it is, run `SELECT CURRENT_USER();`. If the name has characters like `@`, `.` or `-`, wrap it in double quotes, for example `"jdoe@example.com"`.

   Then, in a new worksheet using role `PBI_READER` and warehouse `PBI_WH`, run:

   ```sql
   SELECT COUNT(*) FROM SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.CUSTOMER;  -- 150000
   SELECT COUNT(*) FROM SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.LINEITEM;
   ```

8. **Give this project the connection details.** Add these variables to your shell profile (for example, `~/.zshrc`), then restart Claude Code. Keep the PAT private.

   ```sh
   export SNOWFLAKE_ACCOUNT="<ORGNAME-ACCOUNTNAME>"
   export SNOWFLAKE_USER="PBI_SVC"
   export SNOWFLAKE_PAT="<token_secret>"
   export SNOWFLAKE_WAREHOUSE="PBI_WH"
   export SNOWFLAKE_ROLE="PBI_READER"
   ```

   In Power BI Desktop, use the same server and warehouse, `PBI_SVC` as the user, and the PAT as the password. If Desktop rejects the PAT, sign in with your admin user instead.

9. **Connect Claude Code to Snowflake.** The repo's `.mcp.json` starts a local Snowflake MCP server (`uvx snowflake-labs-mcp`) that signs in as `PBI_SVC` with the step 8 variables; the PAT is passed as the password. `.claude/snowflake_mcp.yaml` limits it to one tool, `run_snowflake_query`, which accepts `SELECT`, `DESCRIBE` and `SHOW` only. Everything else is rejected before it reaches Snowflake, and the `PBI_READER` role limits what reaches it. Nothing has to be created in Snowflake.

   You need `uv` on your `PATH`. Restart Claude Code from a shell where the step 8 variables are set and run `/mcp`: `snowflake` should show as connected. The first start downloads the package, so it can take a minute.

   > The Snowflake-managed MCP server (`CREATE MCP SERVER`) is not an option on a trial account: the server can be created, but calling its tools fails with "Access denied for trial accounts". The Snowflake-Labs server is deprecated in favour of it, so switch once the account is upgraded. If you already created `PBI_TOOLS` for it, you can keep it for then, or remove it with `DROP DATABASE PBI_TOOLS;` as `ACCOUNTADMIN`.

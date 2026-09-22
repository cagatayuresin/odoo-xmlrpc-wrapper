# Read-only Odoo examples

Run these scripts from the repository root with Python 3.10+ and this checkout's
`odoo-xmlrpc-wrapper` package installed. If you already installed the 2.0.0rc1 wheel
for the live smoke test, no reinstall is needed for these examples.

```bash
source .venv/bin/activate
python examples/contacts.py --limit 10
```

Each report asks for a host, database name, login/email, and hidden password/API
key. The shared helper also accepts `--host`, `--db`, and `--user`, or these
optional defaults for the current terminal session:

```bash
export ODOO_HOST="odoo.example.com"
export ODOO_DB="your-database"
export ODOO_USERNAME="your-login@example.com"
```

The password is always prompted for; it is not accepted in arguments or saved to
a file. HTTPS is the default. `--http` explicitly selects unencrypted HTTP, and
`--timeout 60` changes the socket timeout. Use `--help` on any script for options.
The original `live_smoke_test.py` keeps its separate interactive prompts.

| Script | What it shows | Wrapper methods | Required Odoo model |
| --- | --- | --- | --- |
| `contacts.py` | Active people/companies, city and country | `count`, `search_read` | `res.partner` |
| `crm_pipeline.py` | Open opportunity counts per stage and selected opportunity details | `count`, `custom(read_group)`, `search_read` | `crm.lead` (CRM) |
| `sales_orders.py` | Recent orders, states, customers and displayed-row subtotals by currency | `count`, `custom(search_read)` | `sale.order` (Sales) |
| `model_fields.py` | Field names, types, labels and relations | `get_fields` | The selected model |

## Contacts and companies

```bash
python examples/contacts.py --limit 10
python examples/contacts.py --query "Acme" --limit 5
python examples/contacts.py --companies --limit 20
```

`--query` searches part of the name. `--companies` selects company contacts; it
does not imply that every result is a customer (vendors can be companies too).
Only selected fields are requested. The report prints both the number of matching
active contacts and the number displayed.

## CRM opportunities and stages

```bash
python examples/crm_pipeline.py --limit 15
python examples/crm_pipeline.py --mine --limit 10
```

The domain selects active opportunities in stages whose `is_won` flag is false.
`--mine` adds the authenticated user as salesperson. Stage counts are calculated
on the server with `read_group` and cover the full matching domain for each shown
stage; at most `--limit` stages are shown. The detail table uses the same limit
and Odoo's default ordering, not necessarily revenue order.

Each opportunity's expected revenue includes its currency. There is no combined
cross-currency revenue total. These queries demonstrate the
[Odoo 16 CRM fields](https://github.com/odoo/odoo/blob/16.0/addons/crm/models/crm_lead.py)
and the read-only public `read_group` method.

## Recent sales orders

```bash
python examples/sales_orders.py --limit 10
python examples/sales_orders.py --state all --limit 20
python examples/sales_orders.py --since 2026-01-01 --state draft --mine --limit 10
```

By default, this selects state `sale` and an order date within the past 30 days,
starting at midnight UTC on the cutoff date. `--since` takes `YYYY-MM-DD` and
includes that date. State choices are `all`, `draft`, `sent`, `sale`, `done`, and
`cancel`; `--mine` limits orders to your salesperson account. The results are
explicitly sorted newest first using `custom(..., "search_read", kwargs=...)`.

Subtotals include tax and apply **only to the displayed orders**. They are grouped
by currency record ID using decimal arithmetic; there is no currency conversion
or grand total. They do not represent posted invoice revenue or a financial
statement. Widen the date/state filter if there are no matches.

## Model field metadata

```bash
python examples/model_fields.py --model crm.lead --query revenue
python examples/model_fields.py --model res.partner --query country
python examples/model_fields.py --model sale.order --limit 50
```

This reads the selected model's accessible field metadata, then filters field
names and labels locally without case sensitivity. It shows technical names,
types, required/readonly flags, and related models. The display limit applies to
the metadata table; `fields_get` itself returns the accessible metadata in one
response. A readonly field flag describes metadata, not a complete permission
check for the current user.

## Reading the results

- The reports use fixed read methods. They never call `create`, `write`, `unlink`,
  or business actions. Authentication may still produce Odoo login/audit records.
- The user's record rules and company context apply. Missing module/field access
  returns a failure, with raw server details omitted from terminal output.
- An empty report is successful if the query matched no visible records.
- Limits must be 1–100. Counts and lists are separate requests, so concurrent
  changes on the server can make their numbers differ slightly.
- Relational fields display their names. Long cells are truncated, and control
  characters are escaped before printing terminal tables.
- These scripts are manual examples. Automated tests replace the connection
  with mocks and verify that only read methods are used.

The maintainer reported a successful `live_smoke_test.py` run against Odoo
`16.0-20250909` on 2026-09-22. The reporting scripts are separate scenarios and
still await live validation.

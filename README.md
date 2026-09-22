# Odoo XMLRPC Wrapper

[![CI](https://github.com/cagatayuresin/odoo-xmlrpc-wrapper/actions/workflows/build.yml/badge.svg)](https://github.com/cagatayuresin/odoo-xmlrpc-wrapper/actions/workflows/build.yml)
[![PyPI](https://img.shields.io/pypi/v/odoo-xmlrpc-wrapper)](https://pypi.org/project/odoo-xmlrpc-wrapper/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A small Python library for connecting to Odoo and working with its XML-RPC API.
Create, read, update, delete, search, and call custom model methods with a reusable
`Bot` instance.

This README describes **2.0.0rc1**, a release candidate for manual testing. It is
not yet published to PyPI; install from your checkout to use it. See the
[changelog and migration notes](CHANGELOG.md) for changes from 1.1.1.

## Compatibility and installation

The current source requires **Python 3.10+**; CI tests Python 3.10–3.14. It uses
Python's XML-RPC client and `defusedxml` for hardened response parsing.

```bash
# Published release (may differ from this checkout)
python -m pip install odoo-xmlrpc-wrapper

# Current source, from the repository directory
python -m pip install .
```

The server must expose `/xmlrpc/2/common` and `/xmlrpc/2/object`. Tests validate
client behavior without a live Odoo server; they do not certify every Odoo
release or hosted plan. Odoo has deprecated these APIs in favor of JSON-2;
see the [official compatibility and migration notice](https://www.odoo.com/documentation/master/developer/reference/external_rpc_api.html).
This library implements XML-RPC.

## Connect

Configure `ODOO_HOST`, `ODOO_DB`, `ODOO_USERNAME`, and `ODOO_PASSWORD` in your
process environment. An Odoo API key can be supplied in place of the password
where the server supports it.

```python
import os

from odoo_xmlrpc_wrapper import Bot

with Bot(
    host=os.environ["ODOO_HOST"],  # e.g. odoo.example.com
    db=os.environ["ODOO_DB"],
    userlogin=os.environ["ODOO_USERNAME"],
    password=os.environ["ODOO_PASSWORD"],
    timeout=30,
) as bot:
    print(bot.status())
    partners = bot.search_read(
        "res.partner",
        constraints=[("is_company", "=", True)],
        fields=["name", "email"],
        limit=20,
    )
```

The legacy import still works:

```python
from odoo_xmlrpc_wrapper import odoo_xmlrpc_wrapper as oxw
```

HTTPS validates certificates and hostnames by default. `host` accepts a hostname,
optional port/base path, or a full URL matching `secured`. Embedded credentials,
query strings, and fragments are rejected. Plain HTTP requires
`secured=False`, for example with `host="localhost:8069"` in local development.

`timeout` must be a finite positive number of seconds and applies to socket
operations. Connections are closed when leaving the `with` block; alternatively,
call `bot.close()`. A closed instance cannot be reused. Construction authenticates
and reads the user's profile but does not print anything.

`Bot(test=True)` provisions an external demo through `https://demo.odoo.com/start`.
It needs internet access, uses the returned HTTPS endpoint, and ignores supplied
credentials. It is a convenience for manual exploration; the test suite does not
use it.

## CRUD operations

These examples assume an open `bot` connection. Each explicit `model` becomes the
active model for later calls. Immediately after login, the active model is
`res.users`. You can also set `bot.model = "res.partner"` directly. Use a separate
instance per thread because the active model and connection are shared state.

```python
# Create returns the server-assigned record ID.
partner_id = bot.create("res.partner", {"name": "John Doe"})

# Read accepts one positive ID or a list/tuple of IDs.
records = bot.read(ids=[partner_id], fields=["name"])

# Update and delete return the server's result (normally True).
updated = bot.update(the_id=partner_id, the_obj={"name": "Jane Doe"})
deleted = bot.delete(ids=[partner_id])
```

No fixed record IDs are assumed. `update()` requires one positive integer ID;
booleans, missing IDs, and invalid values raise `ValueError` before a request.
`create()` and `update()` require a dictionary of field values.

## Search, count, and metadata

```python
ids = bot.search(
    "res.partner",
    constraints=[("is_company", "=", True)],
    offset=0,
    limit=20,
)

records = bot.search_read(
    "res.partner",
    constraints=[("id", "in", ids)],
    fields=["name", "email"],
    limit=20,
)

# Runs Odoo's search_count; does not download all record IDs.
total = bot.count("res.partner", constraints=[("is_company", "=", True)])

fields = bot.get_fields("res.partner", attributes=["string", "type"])
```

Omitting constraints searches the whole active model. `search_read()` defaults to
`fields=["name"]`; `read()` defaults to the fields selected by Odoo. Explicit empty
field/attribute lists and `limit=0`/`offset=0` are forwarded unchanged, so their
meaning follows the server's API. In particular, zero is not a client-side
"return nothing" shortcut. Paginate large reads: individual XML responses are
limited to **30 MiB after decompression**.

## Custom model methods

```python
result = bot.custom(
    "res.partner",
    "name_search",
    att=["Azure"],
    kwargs={"limit": 10},
)
```

`att` supplies positional arguments and `kwargs` supplies keyword arguments to
`execute_kw`. For backward compatibility, omitted `att` becomes `[[]]`; pass `[]`
for a method taking no positional arguments. Private method names are rejected.
The wrapper returns the server result and respects Odoo's access controls.

## Errors and security

- Invalid configuration or method arguments raise `ValueError` locally.
- Failed authentication raises `PermissionError` without including credentials.
- XML-RPC faults, transport errors, and timeouts propagate to the caller. Catch
  `xmlrpc.client.Fault`, `OSError`, or `TimeoutError` as appropriate for your app.
- XML responses containing DTDs, entities, or external references are rejected by
  `defusedxml`. Excessively large responses are rejected before parsing completes.
- Requests are never automatically retried, including on connection resets.
  Check the server state before retrying a timed-out write; it may already have
  succeeded. HTTP error bodies are discarded without reading them into memory.

See [SECURITY.md](SECURITY.md) for the security policy and private reporting channel.

## Manual test against your Odoo server

From your checkout, build and install the candidate as a real pip distribution:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements-dev.txt
python -m build --no-isolation --outdir dist/2.0.0rc1
python -m twine check --strict dist/2.0.0rc1/*
python -m pip install --no-deps --force-reinstall dist/2.0.0rc1/*.whl
python examples/live_smoke_test.py
```

The script prints the installed package version, then prompts for the host,
database name, login/email, and password/API key. Password input is hidden and is
not saved to disk or passed as a command-line argument. Use the exact database
name, not the website name or a URL. HTTPS is the default; use `--http` only when
you explicitly intend to send credentials over an unencrypted connection.

It checks authentication, `read`, `search`, `search_read`, `count`, `get_fields`,
and `custom(search_count)` against your own `res.users` record, then closes the
connection. It does not create, update, or delete business records. Odoo itself
may record login/audit metadata during authentication. The account needs API and
model read access; an access fault alone does not establish a wrapper bug.

Success ends with `SUCCESS: all live read checks passed.` A failure returns a
nonzero exit status and identifies the stage without printing credentials or
raw server fault details. Share the package/server versions and PASS/FAIL lines
when reporting the result. This script is manual and is never run against a
real server by CI. Creation/update/deletion need a separate test using a
dedicated test record after the read checks pass.

These commands install the wheel rather than an editable checkout. To resume
source development afterwards, run
`python -m pip install --no-deps --no-build-isolation -e .`.

### Read-only reporting examples

With the package installed, run these from the repository directory:

```bash
python examples/contacts.py --companies --limit 10
python examples/crm_pipeline.py --limit 15
python examples/sales_orders.py --state all --limit 10
python examples/model_fields.py --model crm.lead --query revenue
```

These examples query contacts, CRM stage counts and opportunities, recent sales
orders, and model metadata. They prompt for connection details and a hidden
password/API key. You can reuse `ODOO_HOST`, `ODOO_DB`, and `ODOO_USERNAME` across
runs; the password is always entered interactively. Lists are limited to 1–100
rows, and sales subtotals cover only displayed rows with currencies kept separate.
CRM and sales examples need the corresponding Odoo modules and read permissions.

The original read smoke test passed on Odoo `16.0-20250909`, as reported by the
maintainer. The new reporting examples await live validation. See
[the examples guide](examples/README.md) for filters, commands, and method mappings.

## Development and checks

```bash
python3 -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --require-hashes -r requirements-dev.txt
python -m pip install --no-deps --no-build-isolation -e .

# Syntax and style
python -m compileall -q src tests examples
python -m ruff check src tests examples
python -m ruff format --check src tests examples

# Offline regression and security tests, with branch coverage (minimum 90%)
python -m coverage run -m unittest discover -s tests -v
python -m coverage report
python -m coverage xml

# Static security, workflow security, and dependency health
python -m bandit -r src
zizmor --offline .github/workflows
python -m pip check
python -m pip_audit --strict --require-hashes -r requirements.txt
python -m pip_audit --strict --require-hashes -r requirements-dev.txt

# Build both distributions; validate package metadata and README rendering
python -m build --no-isolation
python -m twine check --strict dist/*.whl dist/*.tar.gz
```

The tests mock the RPC boundary and use in-memory XML responses. They cover CRUD
arguments/results, authentication, input validation, active models, connection
cleanup, timeouts, certificate verification, and malicious XML. Test execution
does not provision demo servers, access credentials, or modify a real database.
Dependency installation and vulnerability database updates need internet access.

Install [Trivy](https://trivy.dev/latest/getting-started/installation/) separately
(CI pins version 0.74.0), then run:

```bash
trivy fs --scanners vuln,misconfig,secret --severity HIGH,CRITICAL \
  --exit-code 1 --skip-dirs .git,.venv,build,dist,.trivy-cache,.audit-reports \
  --file-patterns 'pip:requirements.*\.txt' .
```

Trivy scans the complete dependency locks and project files, and fails on HIGH or
CRITICAL findings, including unfixed issues. The misconfiguration scanner applies
to supported infrastructure files when present; GitHub Actions are checked by
zizmor. The secret scan covers the current working tree, not full Git history.
pip-audit checks known advisories at all severities. Passing scans are evidence
about the checked files and current databases, not a guarantee of no vulnerabilities.

### Updating dependencies

`pyproject.toml` is the source of runtime requirements; `requirements-dev.in` lists
development tools. Both generated `.txt` files pin the complete dependency graph
and artifact hashes. With [uv](https://docs.astral.sh/uv/) installed:

```bash
uv pip compile pyproject.toml --universal --python-version 3.10 \
  --generate-hashes --upgrade -o requirements.txt
uv pip compile requirements-dev.in --universal --python-version 3.10 \
  --generate-hashes --upgrade -o requirements-dev.txt
```

Review both diffs, reinstall in a fresh environment, and rerun the checks.
Dependabot also opens weekly updates for Python dependencies and GitHub Actions.

### Continuous integration

[GitHub Actions](.github/workflows/build.yml) runs syntax, lint, formatting, tests,
coverage, packaging, and security checks on pushes and pull requests, weekly, and
on manual dispatch. Actions are pinned to full commit SHAs with read-only default
permissions. The packaging job installs the built wheel into a fresh environment
and checks imports and the full offline test suite outside the source tree.

SonarCloud is optional: configure the repository secret `SONAR_TOKEN` for the
existing project in `sonar-project.properties`. Fork pull requests do not receive
that secret. Local checks do not require a SonarCloud account.

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidance and
[CHANGELOG.md](CHANGELOG.md) for release history. Python 3.7–3.9 users need an older
release; the current source intentionally targets maintained Python versions.

## License and support

[MIT](LICENSE) © Cagatay URESIN.

[Buy me a coffee](https://www.buymeacoffee.com/cagatayuresin)

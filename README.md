# Odoo XMLRPC Wrapper

[![CI](https://github.com/cagatayuresin/odoo-xmlrpc-wrapper/actions/workflows/build.yml/badge.svg)](https://github.com/cagatayuresin/odoo-xmlrpc-wrapper/actions/workflows/build.yml)
[![Coverage](https://codecov.io/gh/cagatayuresin/odoo-xmlrpc-wrapper/branch/master/graph/badge.svg)](https://app.codecov.io/gh/cagatayuresin/odoo-xmlrpc-wrapper)
[![PyPI](https://img.shields.io/pypi/v/odoo-xmlrpc-wrapper)](https://pypi.org/project/odoo-xmlrpc-wrapper/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

[![Quality Gate](https://sonarcloud.io/api/project_badges/measure?project=cagatayuresin_odoo-xmlrpc-wrapper&metric=alert_status)](https://sonarcloud.io/dashboard?id=cagatayuresin_odoo-xmlrpc-wrapper)
[![Security Rating](https://sonarcloud.io/api/project_badges/measure?project=cagatayuresin_odoo-xmlrpc-wrapper&metric=security_rating)](https://sonarcloud.io/dashboard?id=cagatayuresin_odoo-xmlrpc-wrapper)
[![Reliability Rating](https://sonarcloud.io/api/project_badges/measure?project=cagatayuresin_odoo-xmlrpc-wrapper&metric=reliability_rating)](https://sonarcloud.io/dashboard?id=cagatayuresin_odoo-xmlrpc-wrapper)

A small Python library for connecting to Odoo and working with its XML-RPC API.
Create, read, update, delete, search, and call custom model methods with a reusable
`Bot` instance.

This README describes **2.0.0**. See the [changelog and migration notes](CHANGELOG.md)
before upgrading from 1.1.1; the minimum Python version and some API behavior
have changed.

## Compatibility and installation

The current source requires **Python 3.10+**; CI tests Python 3.10–3.14. It uses
Python's XML-RPC client and `defusedxml` for hardened response parsing.

```bash
# Install this release from PyPI
python -m pip install --upgrade "odoo-xmlrpc-wrapper==2.0.0"

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

HTTPS uses an explicit verifying TLS context with Python's secure defaults to
validate server certificates and hostnames. `host` accepts a hostname,
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

From your checkout, build and install the package as a real pip distribution:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements-dev.txt
python -m build --no-isolation --outdir dist/2.0.0
python -m twine check --strict dist/2.0.0/*.whl dist/2.0.0/*.tar.gz
python -m pip install --no-deps --force-reinstall dist/2.0.0/*.whl
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

The maintainer reported successful live runs of the read smoke test on Odoo
`16.0-20250909` and all four reporting examples on 2026-09-22. See
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
Routine Dependabot version-update PRs for Python dependencies and GitHub Actions
are paused with `open-pull-requests-limit: 0`. Update them manually using the
commands above and review pinned Action SHAs separately. This setting does not
disable Dependabot alerts or security-update PRs enabled in GitHub repository
settings. It takes effect once the configuration reaches the default branch.
Existing update PRs can be reviewed or closed separately. See the
[Dependabot configuration reference](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference#open-pull-requests-limit).

### Continuous integration

[GitHub Actions](.github/workflows/build.yml) runs syntax, lint, formatting, tests,
coverage, packaging, and security checks on pushes and pull requests, weekly, and
on manual dispatch. Actions are pinned to full commit SHAs with read-only default
permissions. The packaging job installs the built wheel into a fresh environment
and checks imports and the full offline test suite outside the source tree.

GitHub CodeQL also scans Python and GitHub Actions. Dependabot alerts, secret
scanning, push protection, and private vulnerability reporting are enabled.
See [SECURITY.md](SECURITY.md) for reporting instructions and scan limitations.

### Coverage on Codecov

[Codecov](https://app.codecov.io/gh/cagatayuresin/odoo-xmlrpc-wrapper) displays
coverage history and file/line details. The README coverage badge follows
`master`. A separate Python 3.13 job runs the tests, enforces the 90% coverage
minimum, and uploads `coverage.xml` using GitHub OIDC authentication. It needs
no `CODECOV_TOKEN`; only this job receives `id-token: write` permission.

Before the first upload, sign in to Codecov with GitHub, open **Configure / Setup
repo** for `cagatayuresin/odoo-xmlrpc-wrapper`, and select **GitHub Actions**.
Ensure the [Codecov GitHub App](https://github.com/apps/codecov) is installed and
has access to this repository. The checked-in workflow uses OIDC rather than
the upload token shown in the onboarding example. Commit and push the workflow
changes, then check the coverage job and the Codecov report for that commit.
The badge may display an unknown value until the first successful report is
processed. If the dashboard remains empty afterward, check that Codecov's
**Configuration → General → Default branch** is `master`.

Uploads run for pushes, scheduled/manual runs, and pull requests from this
repository. Fork pull requests and Dependabot runs still execute the test matrix,
but skip the Codecov job. Upload failures fail the coverage job so a missing
report is visible. [codecov.yml](codecov.yml) disables bot comments and makes
Codecov's project/patch status checks informational; GitHub Actions continues
to enforce the 90% minimum independently on every tested Python version.

See the [official Codecov action's OIDC setup](https://github.com/codecov/codecov-action#using-oidc).

### SonarCloud Automatic Analysis

SonarQube Cloud (SonarCloud) analyzes this repository through its GitHub
integration. In the SonarCloud project, select **Administration → Analysis Method**
and turn **Automatic Analysis** on. Source paths, test paths, encoding, and Python
versions are configured in [.sonarcloud.properties](.sonarcloud.properties).

Commit the configuration and workflow changes together and push them to `master`.
Then check the SonarCloud result for that commit. A green GitHub Actions **CI**
run alone does not confirm the separate SonarCloud analysis passed. Do not rerun
an older workflow containing the Sonar scanner after enabling automatic analysis;
CI-based and automatic Sonar analyses cannot run together for the same project.

The GitHub Actions workflow does not run a Sonar scanner and does not need
`SONAR_TOKEN`. An existing repository secret with that name can be removed from
GitHub settings if nothing else uses it. Local checks require no SonarCloud account.

Automatic Analysis does not import coverage reports. GitHub Actions still runs
the full test suite with branch coverage on Python 3.10–3.14 and enforces a 90%
minimum. Read coverage results in the **Python** jobs' test step. Syntax, lint,
packaging, Bandit, pip-audit, Trivy, and workflow security checks also run in CI.

See the official [Automatic Analysis documentation](https://docs.sonarsource.com/sonarqube-cloud/analyzing-source-code/automatic-analysis)
for supported configuration and limitations.

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidance and
[CHANGELOG.md](CHANGELOG.md) for release history. Python 3.7–3.9 users need an older
release; the current source intentionally targets maintained Python versions.
Maintainers can follow [RELEASING.md](RELEASING.md) to publish a verified package
through GitHub Actions and PyPI Trusted Publishing. The release workflow builds
and tests the tagged source, then publishes with OIDC authentication. Build
outputs stay out of Git; the same distributions are available on PyPI and as
GitHub Release assets.

## License and support

[MIT](LICENSE) © Cagatay URESIN.

[Buy me a coffee](https://www.buymeacoffee.com/cagatayuresin)

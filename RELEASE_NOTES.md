# Odoo XMLRPC Wrapper 2.0.0

This release fixes record updates and return values, hardens XML-RPC connections,
and adds read-only examples for exploring a real Odoo installation.

## Upgrading from 1.1.1

- Python **3.10+** is required. `defusedxml` is installed as a runtime dependency.
- `create()` returns the new record ID; `update()` and `delete()` return the
  server result instead of `None`.
- Invalid arguments raise `ValueError`; rejected authentication raises
  `PermissionError`. Construction is silent; use `print(bot.status())`.
- The default socket timeout is 30 seconds and responses are limited to 30 MiB.
  Requests are not automatically retried after a disconnect; check server state
  before repeating a write whose outcome is unknown.
- Explicit empty field lists and zero pagination values now reach Odoo unchanged.

## Changes

- Fix `update()` ID validation and use `search_count` for efficient counts.
- Retain verified HTTPS and add per-connection timeouts, strict URL validation,
  local XML/DTD/entity protection, bounded gzip responses, and safe cleanup.
- Add context managers, `close()`, direct `Bot` imports, and custom keyword args.
- Add read-only contacts, CRM pipeline, sales order, and field metadata examples.
- Consolidate packaging and add hash-locked dependencies, Python 3.10–3.14 CI,
  security scanning, and installed-wheel tests.
- Add Codecov coverage reporting using GitHub OIDC authentication and dynamic
  SonarCloud Quality Gate, Security Rating, and Reliability Rating badges.
- Add a PyPI Trusted Publishing workflow using GitHub OIDC authentication.
- Enable GitHub private vulnerability reporting, Dependabot alerts, CodeQL for
  Python and GitHub Actions, secret scanning, and push protection.

## Validation

- 80 offline tests pass, including read-only example and security regressions.
- Package code coverage is 95% with branch coverage enabled.
- The maintainer reported successful authentication/read smoke tests against
  Odoo `16.0-20250909` and successful live runs of all four reporting examples.
- Create/update/delete behavior is covered by offline tests; it has not been
  tested on that live deployment.

Install with `python -m pip install --upgrade odoo-xmlrpc-wrapper==2.0.0`.

See the [full changelog](https://github.com/cagatayuresin/odoo-xmlrpc-wrapper/blob/v2.0.0/CHANGELOG.md)
and [examples](https://github.com/cagatayuresin/odoo-xmlrpc-wrapper/tree/v2.0.0/examples).

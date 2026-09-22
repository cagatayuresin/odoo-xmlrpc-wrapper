# Changelog

## Unreleased — 2.0.0rc1

Release candidate for manual testing. Not yet published to PyPI. The next stable
version is planned as 2.0.0 because the
Python requirement and some public behavior have changed.

### Live validation

- On 2026-09-22, the maintainer reported that the read smoke test passed against
  Odoo `16.0-20250909`: authentication, `read`, `search`, `search_read`, `count`,
  `get_fields`, `custom(search_count)`, and connection cleanup.
- The reporting examples below still need manual validation on their respective
  models. Create/update/delete operations have not been validated on that server.

### Migration from 1.1.1

- Python **3.10+** is required; Python 3.7–3.9 support is removed.
- `defusedxml>=0.7.1,<0.8` is now a runtime dependency; install with pip.
- `create()` returns the created record ID. `update()` and `delete()` return the
  server's result instead of `None`. Update callers that relied on a falsy return.
- Invalid URLs, credentials, models, IDs, and argument containers raise
  `ValueError` before RPC. Authentication rejection raises `PermissionError`.
- Construction no longer prints connection details. Use `print(bot.status())`.
- Explicit empty field/attribute lists and zero pagination values are forwarded
  to Odoo rather than silently omitted.
- Connections have a 30-second socket timeout by default. Set `timeout=` to a
  different finite positive value when necessary.
- XML responses are capped at 30 MiB after decompression; paginate large reads.
  DTDs and entities are rejected. HTTP error bodies are discarded.
- Requests are not automatically retried after a disconnect. Check server state
  before retrying a write whose result is unknown.
- The old `from odoo_xmlrpc_wrapper import odoo_xmlrpc_wrapper as oxw` import and
  active-model reuse are retained. `custom()` still defaults to `att=[[]]`.

### Added

- Direct `from odoo_xmlrpc_wrapper import Bot` import.
- `close()` and context manager support, including cleanup on failed login.
- `custom(..., kwargs=...)` for keyword arguments to public model methods.
- Per-connection HTTP/HTTPS timeouts and strict URL validation.
- Interactive `examples/live_smoke_test.py` for manually checking a real server
  without creating, updating, or deleting business records.
- Read-only examples for contacts, CRM stage counts/opportunities, recent sales
  orders with separate currency subtotals, and searchable field metadata.
- Shared example connection prompts, hidden password entry, bounded result lists,
  optional non-secret environment defaults, and terminal-safe table output.
- Security policy, contribution guide, and instructions for testing pip builds.

### Fixed

- `update()` validates `the_id` instead of the built-in `id` function.
- `count()` uses Odoo's `search_count` instead of fetching every matching ID.
- Each `custom()` call receives its own default argument list.
- Demo URLs are parsed properly and cannot silently downgrade to HTTP.
- Initialization and context-manager cleanup preserve the original exception.
- Dropped connections cannot silently replay create/update/custom operations.
- Both plain and gzip responses are bounded; XML hardening is local to this
  client and does not monkey-patch the process-wide XML-RPC parser.

### Packaging and checks

- Package metadata and version are defined in `pyproject.toml`; legacy duplicate
  setup files and checked-in distributions have been removed.
- Runtime and development dependencies are locked with artifact hashes.
- Offline CRUD/security tests replace live-demo tests with fixed record IDs.
- CI tests Python 3.10–3.14 with a minimum 90% combined statement/branch coverage.
- Syntax, Ruff, Bandit, pip-audit, Trivy, zizmor, build, and installed-wheel checks
  run in CI. Dependabot updates Python packages and pinned GitHub Actions.

## 1.1.1 — 2023-05-15

- Added `custom()` for remotely calling model methods.
- Added `status()` for connection information.

The [PyPI release](https://pypi.org/project/odoo-xmlrpc-wrapper/1.1.1/) was published
on May 15; the original repository notes were dated May 10.

## 1.0.1 — 2023-03-23

- Initial release.

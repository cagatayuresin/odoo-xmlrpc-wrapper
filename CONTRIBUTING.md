# Contributing

Use Python 3.10 or newer and an isolated virtual environment. Follow
[the development setup and checks](README.md#development-and-checks) before
opening a pull request.

- Preserve the documented API and add an offline regression test for bug fixes.
- Tests must not contact the Odoo demo service or alter a real database. Mock the
  RPC boundary; test malformed XML with in-memory responses.
- Keep credentials, generated distributions, caches, and virtual environments out
  of commits. Build artifacts belong in releases, not the source tree.
- Put package metadata in `pyproject.toml`. Update `CHANGELOG.md` under Unreleased
  when behavior changes. The maintainer chooses the release version before
  publication.
- Regenerate both lock files when changing dependencies, then run pip-audit and
  Trivy. Do not hand-edit hashes or suppress a finding merely to pass CI.
- Describe what changed and which checks ran in your pull request. Report any
  unavailable integration checks explicitly.

For vulnerability reports, follow [SECURITY.md](SECURITY.md).

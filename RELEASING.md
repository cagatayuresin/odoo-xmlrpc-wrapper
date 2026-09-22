# Publishing 2.0.0

Publish a normal GitHub release for the tested tag to start
[the publishing workflow](.github/workflows/publish.yml). GitHub Actions builds
and tests the distributions from that exact commit, then a separate job uploads
them to PyPI using Trusted Publishing. Attach those same distributions to the
GitHub release after the workflow succeeds.

## Configure Trusted Publishing once

The existing PyPI project uses these publisher settings under
[Manage → Publishing](https://pypi.org/manage/project/odoo-xmlrpc-wrapper/settings/publishing/):

| Field | Value |
| --- | --- |
| Repository owner | `cagatayuresin` |
| Repository name | `odoo-xmlrpc-wrapper` |
| Workflow filename | `publish.yml` |
| Environment name | `pypi` |

The GitHub `pypi` environment allows deployment from `v*` tags. Keep its name
identical to the PyPI publisher configuration. No PyPI API token or GitHub
repository secret is required. See
[PyPI's Trusted Publisher setup](https://docs.pypi.org/trusted-publishers/adding-a-publisher/).

The workflow accepts stable `vMAJOR.MINOR.PATCH` tags matching the version in
`pyproject.toml`; prerelease release events are excluded. It checks out the
triggering commit, installs hash-locked dependencies, builds and validates the
wheel and source archive, and runs the offline tests against the installed wheel
outside the checkout. The publishing job downloads the verified `distributions`
artifact and has `id-token: write` permission; it does not check out or execute
the project source.

## Prepare and validate the package

From the repository root on `master`, with Python 3.10+:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements.txt -r requirements-dev.txt
python -m pip install --no-deps --no-build-isolation -e .
python -c 'import odoo_xmlrpc_wrapper; print(odoo_xmlrpc_wrapper.__version__)'

python -m compileall -q src tests examples
python -m ruff check .
python -m ruff format --check .
python -m coverage run -m unittest discover -s tests
python -m coverage report
python -m pip check
python -m bandit -r src
python -m pip_audit --strict --require-hashes -r requirements.txt
python -m pip_audit --strict --require-hashes -r requirements-dev.txt
zizmor --offline .github/workflows
python -m build --no-isolation --outdir dist/2.0.0
python -m twine check --strict dist/2.0.0/*.whl dist/2.0.0/*.tar.gz
```

The version must print `2.0.0`. These local builds validate the package; the
publishing workflow creates the final upload files. Generated `build/`, `dist/`,
and `*.egg-info/` directories are ignored by Git and must stay outside commits.

## Commit, push, and check the release commit

Review `git diff`. Commit any pending source, CI, or dependency changes
separately, then commit the release preparation files:

```bash
git add .github/workflows/publish.yml pyproject.toml CHANGELOG.md CHANGES.txt README.md examples/README.md MANIFEST.in RELEASE_NOTES.md RELEASING.md SECURITY.md
git commit -m "chore(release): prepare 2.0.0 with trusted publishing"
git push origin master
```

Wait for **CI**, **CodeQL**, and **SonarCloud Automatic Analysis** to succeed on
this exact commit. Check the commit SHA in
[GitHub Actions](https://github.com/cagatayuresin/odoo-xmlrpc-wrapper/actions)
and SonarCloud. CI includes syntax, formatting, Python 3.10–3.14 tests, coverage,
packaging, Bandit, pip-audit, Trivy, and workflow security checks. SonarCloud does
not import coverage in automatic mode; CI enforces the coverage threshold.
If fixes are needed, commit and validate them before choosing the release tag.

Confirm the working tree is clean, then tag that tested commit:

```bash
git status --short
git tag -a v2.0.0 -m "Release 2.0.0"
git push origin v2.0.0
```

Pushing the tag alone does not publish to PyPI. The workflow must already be
included in the tagged commit and on the default branch.

## Publish the GitHub release and wait for PyPI

With [GitHub CLI](https://cli.github.com/) authenticated (`gh auth status`;
use `gh auth login` if needed), publish a normal release without local assets:

```bash
gh release create v2.0.0 \
  --verify-tag --title "Odoo XMLRPC Wrapper 2.0.0" \
  --notes-file RELEASE_NOTES.md --latest
```

`--verify-tag` requires the existing tag. Publishing this release triggers
**Publish to PyPI** automatically. Do not also dispatch the workflow manually.
List its runs and identify the one for `v2.0.0` and the tested commit:

```bash
gh run list --workflow publish.yml --limit 5 \
  --json databaseId,headBranch,headSha,status,conclusion,url
```

Copy that run's numeric `databaseId`. Enter it when the first command below
waits for input, then follow the run to completion:

```bash
read -r PUBLISH_RUN_ID
gh run watch "$PUBLISH_RUN_ID" --exit-status
```

Both build and publish jobs must succeed. Confirm that the wheel and source
archive appear on the [2.0.0 PyPI page](https://pypi.org/project/odoo-xmlrpc-wrapper/2.0.0/).

For an authentication failure before upload, correct the Trusted Publisher
settings and rerun only the failed job so it reuses the verified artifact:

```bash
gh run rerun "$PUBLISH_RUN_ID" --failed
gh run watch "$PUBLISH_RUN_ID" --exit-status
```

Manual dispatch is a fallback only when no publishing run was triggered:
`gh workflow run publish.yml --ref v2.0.0`. Do not dispatch alongside an existing
run or after a successful upload. Concurrency queues duplicate runs; it does
not deduplicate uploads. If an upload partially succeeds, inspect PyPI before
retrying and retain the original artifact. Uploaded filenames cannot be
replaced; code changes require a new version.

## Attach the published distributions to GitHub

Download `distributions` from the successful publishing run. These are the exact
files used by the PyPI job; do not rebuild or substitute the local test builds.

```bash
RELEASE_ASSET_DIR=$(mktemp -d)
gh run download "$PUBLISH_RUN_ID" --name distributions --dir "$RELEASE_ASSET_DIR"

gh release upload v2.0.0 \
  "$RELEASE_ASSET_DIR/odoo_xmlrpc_wrapper-2.0.0-py3-none-any.whl" \
  "$RELEASE_ASSET_DIR/odoo_xmlrpc_wrapper-2.0.0.tar.gz"
```

Confirm both assets are listed on the GitHub release. Immutable releases are
currently disabled for this repository, allowing assets to be attached after
publication. If that setting changes, update this process before publishing.

## Verify the published package

Use a fresh temporary environment so the editable checkout or cached candidate
cannot satisfy installation. This check only imports the package; it does not
contact Odoo.

```bash
RELEASE_VERIFY_DIR=$(mktemp -d)
python3 -m venv "$RELEASE_VERIFY_DIR/venv"
"$RELEASE_VERIFY_DIR/venv/bin/python" -m pip install --no-cache-dir --index-url https://pypi.org/simple "odoo-xmlrpc-wrapper==2.0.0"
"$RELEASE_VERIFY_DIR/venv/bin/python" -m pip check
"$RELEASE_VERIFY_DIR/venv/bin/python" -I -c 'from odoo_xmlrpc_wrapper import Bot, __version__; assert __version__ == "2.0.0"; print(__version__, Bot.__name__)'
```

Expected output from the final command: `2.0.0 Bot`.

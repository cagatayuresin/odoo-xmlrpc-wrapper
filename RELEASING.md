# Publishing 2.0.0

These are manual maintainer commands. Building a wheel, pushing Git commits,
creating a GitHub release, and uploading to PyPI are separate steps. Run each
section only after the preceding checks pass.

## Prepare and validate the package

From the repository root on `master`, with Python 3.10+:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements-dev.txt
python -m pip install --no-deps --no-build-isolation -e .
python -c 'import odoo_xmlrpc_wrapper; print(odoo_xmlrpc_wrapper.__version__)'

python -m compileall -q src tests examples
python -m ruff check .
python -m ruff format --check .
python -m coverage run -m unittest discover -s tests
python -m coverage report
python -m pip check
python -m build --no-isolation --outdir dist/2.0.0
python -m twine check --strict dist/2.0.0/*.whl dist/2.0.0/*.tar.gz
```

The version must print `2.0.0`. The build creates exactly the versioned wheel
and source archive below. Keep these artifacts for the upload; use the same
commit for the tag. The separate `dist/2.0.0` directory avoids including older
release-candidate files in uploads.

## Commit, push, and check CI

Review `git diff`. Commit any pending CI or dependency-automation changes
separately, then commit the release preparation files:

```bash
git add pyproject.toml CHANGELOG.md CHANGES.txt README.md examples/README.md MANIFEST.in RELEASE_NOTES.md RELEASING.md
git commit -m "chore(release): prepare 2.0.0"
git push origin master
```

Wait for the **CI** workflow on this exact commit to succeed in
[GitHub Actions](https://github.com/cagatayuresin/odoo-xmlrpc-wrapper/actions/workflows/build.yml).
CI includes syntax, formatting, Python 3.10–3.14 tests, coverage, packaging,
Bandit, pip-audit, Trivy, and workflow security checks. Also check the separate
SonarCloud Automatic Analysis result for the same commit. SonarCloud does not
import coverage in this mode; GitHub Actions enforces the coverage threshold.
If fixes are needed, rebuild and validate the artifacts from the final commit
before continuing.

Confirm the working tree is clean, then tag that tested commit:

```bash
git status --short
git tag -a v2.0.0 -m "Release 2.0.0"
git push origin v2.0.0
```

## Upload the package to PyPI

Create a token scoped to the existing `odoo-xmlrpc-wrapper` project in your
[PyPI account settings](https://pypi.org/manage/account/token/). Enter that token
at Twine's hidden password prompt, including its `pypi-` prefix. The username is
the literal `__token__`. See [PyPI's token instructions](https://pypi.org/help/#apitoken).

```bash
python -m twine upload --repository-url https://upload.pypi.org/legacy/ --username __token__ \
  dist/2.0.0/odoo_xmlrpc_wrapper-2.0.0-py3-none-any.whl \
  dist/2.0.0/odoo_xmlrpc_wrapper-2.0.0.tar.gz
```

Confirm both files appear on the
[2.0.0 PyPI page](https://pypi.org/project/odoo-xmlrpc-wrapper/2.0.0/).
PyPI does not allow replacing an uploaded distribution filename. If an upload is
interrupted, inspect the release page and retry only a missing file using the
same verified artifact; code changes require a new version.

## Create the GitHub release

With [GitHub CLI](https://cli.github.com/) installed and authenticated
(`gh auth status`; use `gh auth login` if needed):

```bash
gh release create v2.0.0 \
  dist/2.0.0/odoo_xmlrpc_wrapper-2.0.0-py3-none-any.whl \
  dist/2.0.0/odoo_xmlrpc_wrapper-2.0.0.tar.gz \
  --verify-tag --title "Odoo XMLRPC Wrapper 2.0.0" \
  --notes-file RELEASE_NOTES.md --latest
```

This publishes a normal release using the existing tag and the same artifacts
uploaded to PyPI. `--verify-tag` requires the tag to exist on GitHub instead of
letting this command create one. See the
[GitHub CLI documentation](https://cli.github.com/manual/gh_release_create).

## Verify the published package

Use a fresh temporary environment so the editable checkout or cached candidate
cannot satisfy the installation. This check only imports the package; it does
not contact Odoo.

```bash
VERIFY_DIR=$(mktemp -d)
python3 -m venv "$VERIFY_DIR/venv"
"$VERIFY_DIR/venv/bin/python" -m pip install --no-cache-dir --index-url https://pypi.org/simple "odoo-xmlrpc-wrapper==2.0.0"
"$VERIFY_DIR/venv/bin/python" -m pip check
"$VERIFY_DIR/venv/bin/python" -I -c 'from odoo_xmlrpc_wrapper import Bot, __version__; assert __version__ == "2.0.0"; print(__version__, Bot.__name__)'
```

Expected output from the final command: `2.0.0 Bot`.

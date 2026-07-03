# Release Checklist — v1.1.0

Ordered, exact commands for a human to ship v1.1.0. Each step has a
done-condition; do not proceed to the next step until the current one's
done-condition is true. This checklist supersedes the generic
`RELEASE_CHECKLIST.md` at the repo root for this specific release — that
file remains the reference for repo-wide, one-time setup (making the repo
public, GitHub Pages, etc.) that doesn't need repeating per-release.

**Read this whole preamble before running anything.** Two things about this
release are not routine:

1. **The working tree has uncommitted changes that are not part of this
   task.** This session (release-prep) only wrote/edited
   `CHANGELOG.md`, `js/package.json`, `py/pyproject.toml`,
   `docs/RELEASE_NOTES_v1.1.0.md`, and this file. Every other modified file
   listed by `git status` — the base-fingerprint enforcement, `Diff()`
   ports, GS1 Python doc fixes, README rewrite, attic README fixes, and the
   doc-example fixes — was written by other sessions/agents and is still
   **uncommitted**. Someone who owns those files needs to review and commit
   them (Step 1) before this release can be tagged; nothing in this
   checklist commits on your behalf.
2. **This branch (`fix/industry-gaps-go-pkg-py-gs1`) is ahead of
   `origin/main`.** `origin/main` is currently at `76e8fe3`, which still has
   the broken Go module path (the exact bug this release fixes) and the
   stale docs this release corrects. Tagging from a feature branch would
   technically make `go get module@v1.1.0` resolve correctly (Git tags are
   refs, not branch-bound), but would leave `main` — what anyone browsing
   the repo sees by default, and what `go get module@latest` falls back to
   once no better-tagged commit exists on it — still broken. **Merge this
   branch into `main` before tagging**, not just before publishing.

---

## Step 0 — Preconditions

- [ ] Every file listed under "Files changed" by `git status --short` other
      than the five this task owns has been reviewed and committed by its
      owning agent/session. Confirm with:
      ```bash
      cd /home/omen/Documents/Project/cogs/glyph
      git status --short
      ```
      Done when: `git status --short` shows nothing outside files you are
      about to commit in Step 1.

- [ ] `py/glyph/__init__.py`'s hand-maintained `__version__ = "1.0.1"`
      constant is bumped to `"1.1.0"` to match `py/pyproject.toml`. This is
      **not** done by this task (outside its file-ownership scope) and is
      **not** read by the packaging pipeline (setuptools reads
      `pyproject.toml`), but a published package whose own `__version__`
      disagrees with its PyPI version is a real, user-visible bug the first
      time someone runs `python -c "import glyph; print(glyph.__version__)"`
      after `pip install`.
      Done when:
      ```bash
      grep '__version__' py/glyph/__init__.py   # must print "1.1.0"
      ```

- [ ] Full test suites and the cross-language conformance suite are green
      on the exact commit you're about to tag:
      ```bash
      cd /home/omen/Documents/Project/cogs/glyph/go && go build ./... && go vet ./... && go test ./... -count=1
      cd /home/omen/Documents/Project/cogs/glyph/py && python -m pytest tests/ -q
      cd /home/omen/Documents/Project/cogs/glyph/js && npm test
      cd /home/omen/Documents/Project/cogs/glyph && bash conformance/run_conformance.sh
      ```
      Done when: Go both packages `ok`, Python all passed, JS 8/8 suites
      passed, conformance `ALL PASS (51 cases x 3 impls)`. (These exact
      counts passed during release prep on 2026-07-02; re-run — don't trust
      the number if anything landed since.)

---

## Step 1 — Commit

Stage and commit the release-prep files plus whatever else Step 0 confirmed
is ready. Do this as (at minimum) two commits so the version bump has a
clean, revertable message — but the exact split is a judgment call for
whoever runs this; the important part is that CI's `release-meta` job reads
`py/pyproject.toml` and `js/package.json` verbatim from the tagged commit,
so both files' `version` fields must be `1.1.0` in the commit you tag.

```bash
cd /home/omen/Documents/Project/cogs/glyph
git add CHANGELOG.md js/package.json py/pyproject.toml \
        docs/RELEASE_NOTES_v1.1.0.md docs/RELEASE_CHECKLIST_v1.1.0.md
git commit -m "release: v1.1.0 — changelog, version bump, release notes"
```

Done when: `git log -1 --stat` shows exactly these files, and
`git status --short` is clean except for whatever other files Step 0 already
committed separately.

---

## Step 2 — Merge to `main`

```bash
git fetch origin
git checkout main
git merge --ff-only fix/industry-gaps-go-pkg-py-gs1   # or open/merge a PR, per your normal review process
```

If `--ff-only` fails (main has diverged further since this checklist was
written), stop and reconcile manually — do not force-push over `main`.

Done when: `git log -1 --oneline main` shows the release commit from Step 1,
and:
```bash
grep 'module ' go/go.mod        # must print: module github.com/Neumenon/glyph/go
```
on `main` (not just on the feature branch).

---

## Step 3 — Tag

Two tags are needed, for two different consumers:

- `v1.1.0` — the repo-wide release marker. **This is also the tag CI's
  `release-meta` job watches** (`.github/workflows/ci.yml`, trigger
  `tags: ['v*']`): pushing it runs the full test matrix, and — only if that
  passes AND the tag's version string matches `py/pyproject.toml` /
  `js/package.json` exactly — automatically publishes to PyPI and npm (see
  Step 4). Since both files are `1.1.0`, pushing `v1.1.0` will publish
  **both** packages.
- `go/v1.1.0` — required separately for the Go module proxy. Go's
  multi-module-in-one-repo convention requires a version tag prefixed with
  the module's subdirectory (`go/`) for `go get module@v1.1.0` to resolve to
  an explicit tagged version instead of a pseudo-version. This tag does
  **not** match `tags: ['v*']` (it starts with `go/`, not `v`), so pushing it
  does not trigger CI or the publish jobs — it is Go-proxy-only and safe to
  push independently.

```bash
git tag -a v1.1.0 -m "v1.1.0"
git tag -a go/v1.1.0 -m "go/v1.1.0"
git push origin main
git push origin v1.1.0
git push origin go/v1.1.0
```

Done when: `git ls-remote --tags origin | grep v1.1.0` shows both tags on
the remote.

---

## Step 4 — Watch CI, confirm automated publish

Open the Actions run triggered by the `v1.1.0` tag push
(`https://github.com/Neumenon/glyph/actions`). It runs the full language
matrix (`go`, `python`, `js`, `rust`, `c`, `fixtures`), then `publish-gate`,
then `release-meta`, then — gated on both passing — `publish-pypi` and
`publish-npm` in parallel.

- `publish-pypi` builds with `python -m build` and publishes via
  `pypa/gh-action-pypi-publish` using **PyPI Trusted Publishing** (OIDC,
  `id-token: write` — no stored token/secret needed for this path).
- `publish-npm` builds with `npm ci && npm run build` and publishes via
  `npm publish --access public`, authenticated by the `NPM_TOKEN` repo
  secret.

Done when: both `publish-pypi` and `publish-npm` jobs show green in the
Actions run for the `v1.1.0` tag.

**If either job is red or was skipped when it shouldn't have been**, do not
re-run blindly — read why first (`release-meta`'s log line
`Tag=... py=... js=...` shows exactly what it compared). Common causes: the
tag doesn't match a `version` field verbatim (e.g. a `v` prefix mismatch,
or someone bumped a manifest after this checklist was written but before
tagging), or a registry-side failure (expired trusted-publisher config,
name conflict, network). Fix the root cause, then either re-run the failed
job from the Actions UI (safe — `npm publish`/PyPI publish are idempotent
against a version that hasn't been published yet, and will error clearly
if it has) or fall back to Step 5.

---

## Step 5 — Manual publish fallback (only if Step 4's automation fails)

Skip this step entirely if Step 4 went green — do not double-publish.

```bash
# PyPI — requires a PyPI API token with upload scope for glyph-py in your
# local ~/.pypirc or PYPI_API_TOKEN env var. Trusted Publishing (Step 4) does
# not require this; only use it if the automated path is broken.
cd /home/omen/Documents/Project/cogs/glyph/py
python -m build
twine check dist/*
twine upload dist/*

# npm — requires `npm login` (or NPM_TOKEN) for an account with publish
# rights on cowrie-glyph.
cd /home/omen/Documents/Project/cogs/glyph/js
npm ci
npm run build
npm publish --access public
```

Done when: `pip index versions glyph-py` / `npm view cowrie-glyph versions`
list `1.1.0`.

---

## Step 6 — Go proxy verification

The Go module proxy (`proxy.golang.org`) needs to independently fetch and
cache the tagged commit; there is no publish step to run — verify instead.

```bash
GOPATH=$(mktemp -d) go get github.com/Neumenon/glyph/go@v1.1.0
GOPATH=$(mktemp -d) go get github.com/Neumenon/glyph/go@latest
```

Also confirm pkg.go.dev has re-indexed (may take a few minutes after the
first proxy fetch above):
```
open https://pkg.go.dev/github.com/Neumenon/glyph/go@v1.1.0
```

Done when: both `go get` invocations succeed from a scratch `GOPATH` with no
local copy of the repo, and pkg.go.dev renders the `v1.1.0` docs page.

---

## Step 7 — Publish the GitHub Release

```bash
tar -czf glyph-corpus-v2.2.1-loose.tar.gz conformance/corpus/
```

- [ ] Draft a GitHub Release for tag `v1.1.0`
- [ ] Body: paste `docs/RELEASE_NOTES_v1.1.0.md` verbatim
- [ ] Attach `glyph-corpus-v2.2.1-loose.tar.gz` (corpus version from
      `conformance/corpus/manifest.json`; independent of the code semver —
      only re-cut it if canonicalization rules actually changed, which they
      did not in v1.1.0)
- [ ] Publish (not draft)

Done when: the Release page for `v1.1.0` is live, its body matches the
release notes, and the corpus tarball is downloadable from it.

---

## Step 8 — Clean-environment smoke verification

Confirm the three published packages actually install and run, from
scratch, with no reference to this local checkout:

```bash
# Python
python -m venv /tmp/glyph-smoke-py && /tmp/glyph-smoke-py/bin/pip install glyph-py==1.1.0
/tmp/glyph-smoke-py/bin/python -c "import glyph; print(glyph.__version__); print(glyph.fingerprint_loose(glyph.parse('{a=1 b=2}')))"

# JS
mkdir -p /tmp/glyph-smoke-js && cd /tmp/glyph-smoke-js && npm init -y >/dev/null && npm install cowrie-glyph@1.1.0
node -e "const {fingerprintLoose, parseLoose} = require('cowrie-glyph'); console.log(fingerprintLoose(parseLoose('{a=1 b=2}')))"

# Go (already covered by Step 6, repeated here for the fingerprint check)
```

Done when: the Python and JS commands print the same
`f35719430d98a2fe1336b584d828e31c0e2182c1b4c8464f75a03b38418ec9a7`
fingerprint shown in the README, from freshly installed packages —
i.e. the cross-language identity claim this release is built on actually
holds for what got published, not just for the working tree.

---

## Step 9 — Announce

- [ ] Confirm `README.md`'s install table/badges (if any) point at `1.1.0`
- [ ] Post to relevant channels, if any (per the repo-root
      `RELEASE_CHECKLIST.md` § 8)

---

## Known follow-ups (do not block this release, but don't let them silently drop)

- `py/README.md`, `js/README.md`, `docs/GS1_SPEC.md`, `docs/API_REFERENCE.md`
  still say GS1 is Go/JS-only; stale as of the Python GS1 port in this
  release. Not in this task's file-ownership scope — file an issue or
  hand off explicitly.
- The dot-path-segment struct-vs-map divergence between Go/JS and Python's
  patch applier (documented in the README's Example 3 caveat) is a real,
  pre-existing behavioral gap, not something this release fixes. It doesn't
  affect `diff()`-generated patches or anything in the conformance corpus,
  so it's not release-blocking, but it should get its own follow-up issue
  rather than staying only as a README footnote.

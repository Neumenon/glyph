# GLYPH Release Checklist

Pre-release in-repo steps (automated by CI) are tracked in the conformance runner and existing
test suites. This document covers the **external** steps a maintainer must perform to make a
spec + implementation release consumable by the public.

Work through these in order. Each step has a clear done-condition.

---

## 0. Pre-flight (in-repo)

- [ ] All tests pass: `go test ./...` in `go/`, `pytest py/tests/`, and `cd js && npm test`
- [ ] Conformance suite passes: `bash conformance/run_conformance.sh`
- [ ] `SPEC_GOVERNANCE.md`, `CANONICAL_FORMS.md`, `LOOSE_MODE_SPEC.md`, `GS1_SPEC.md` headers
      all carry consistent Spec ID + Version + Status + Date
- [ ] `conformance/corpus/` is up-to-date: `bash conformance/materialize_corpus.sh`

---

## 1. Make the repo public

- [ ] On GitHub: **Settings → Danger Zone → Change repository visibility → Public**
- [ ] Remove any `.gitignore` entries blocking docs or conformance/ from being indexed
- [ ] Verify `GOPRIVATE` is not set in any CI environment that will run `go get`; or set it to
      something that excludes `github.com/Neumenon/glyph`
- [ ] Confirm the repo URL resolves: `go get github.com/Neumenon/glyph/go/glyph@latest`

Done when: a clean machine can run the above `go get` and get the package.

---

## 2. Tag the Go module

The Go module path is `github.com/Neumenon/glyph/go`.  The package lives in the `go/` subdirectory
of this repo.  For `go get` to resolve a tagged version, the tag must be prefixed with `go/`:

```bash
git tag go/v0.1.0          # or whatever the release semver is
git push origin go/v0.1.0
```

Then verify:

```bash
GOPATH=$(mktemp -d) go get github.com/Neumenon/glyph/go/glyph@v0.1.0
```

Done when: `go get <module>@<tag>` succeeds on a machine that has no local copy.

---

## 3. Publish a GitHub Release with corpus asset

- [ ] Draft a GitHub Release for the same tag (`go/v0.1.0` or a separate top-level `v0.1.0`)
- [ ] Bundle `conformance/corpus/` as a release asset:
      ```bash
      tar -czf glyph-corpus-v2.2.1-loose.tar.gz conformance/corpus/
      # Attach glyph-corpus-v2.2.1-loose.tar.gz to the GitHub Release
      ```
- [ ] Include the corpus version (`v2.2.1-loose`, from `corpus/manifest.json`) in the release notes
- [ ] Copy the SPEC_GOVERNANCE.md § "Claiming conformance" blurb into the release description

Done when: the .tar.gz asset is downloadable from the release page.

---

## 4. Publish canonical-form + GS1 specs to a stable URL

External implementers need a URL that will not disappear.  Options (pick one):

**Option A — GitHub Pages (simplest):**
- Enable GitHub Pages on this repo (Settings → Pages → Deploy from `main`, `/ (root)` or `docs/`)
- The specs will be accessible at `https://neumenon.github.io/glyph/docs/CANONICAL_FORMS.html`
  (or `.md` if raw rendering is sufficient)
- Add the stable URL to the header block of each spec document

**Option B — IETF Internet-Draft (if standardization is the goal):**
- Install `xml2rfc`: `pip install xml2rfc`
- Author an I-D in kramdown-rfc2629 format wrapping `CANONICAL_FORMS.md` content
- Submit via `https://authors.ietf.org/` as `draft-adeniran-glyph-canonical-forms-00`
- Note: IETF I-Ds expire after 6 months; must be re-submitted or adopted by a WG to persist
- This step is optional for a pre-1.0 project; GitHub Pages is sufficient initially

Done when: the canonical URL in each spec header resolves and serves the current spec text.

---

## 5. Publish Python package (glyph-py) to PyPI

```bash
cd py/
python -m build
# Check the dist/ output
twine check dist/*
# Upload (requires PyPI credentials / API token)
twine upload dist/*
```

- [ ] Bump `version` in `py/pyproject.toml` before building
- [ ] Tag the Python release: `git tag py/v0.x.y && git push origin py/v0.x.y`
- [ ] Verify: `pip install glyph-py==0.x.y` on a clean virtualenv

Done when: `pip install glyph-py` resolves to the new version.

---

## 6. Publish JavaScript package (cowrie-glyph) to npm

```bash
cd js/
npm version 0.x.y        # bumps package.json and creates a git tag
npm run build            # rebuild dist/
npm publish --access public
```

- [ ] Confirm `package.json` name is `cowrie-glyph` (check before publishing)
- [ ] Verify: `npm install cowrie-glyph@0.x.y` in a clean project

Done when: `npm install cowrie-glyph` resolves to the new version.

---

## 7. Confirm cowrie/cogs bridge (H1)

This step is external to this repo — verify it before closing the release.

- [ ] The cowrie/cogs bridge (`cowrie` repo) has been updated to import the now-public
      `github.com/Neumenon/glyph/go/glyph` module (not a local replace directive)
- [ ] The cowrie repo's CI passes against the published module tag

Done when: `go mod tidy` in the cowrie repo removes any `replace` directive pointing at a
local path for the glyph module.

---

## 8. Announce

- [ ] Update `README.md` to include the stable spec URL, PyPI badge, and npm badge
- [ ] Post to relevant channels (if any)

---

## Notes

- There is no `GOPATH`-style vendor tarball needed; Go modules handle this automatically once
  the repo is public and the tag exists.
- The conformance corpus version (`v2.2.1-loose`) is independent of the code semver. Update
  `conformance/corpus/manifest.json` (via the source in `go/glyph/testdata/loose_json/manifest.json`)
  only when the canonical rules change.
- Rust and C ports (`attic/`) are not published as packages at this time.

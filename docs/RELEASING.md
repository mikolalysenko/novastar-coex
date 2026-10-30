# Releasing to GitHub and HACS

The public repository is `mikolalysenko/novastar-coex`. It contains only the
integration, client, sanitized fixtures, tests and public documentation. Keep
installation-specific configuration and its history outside this repository.

## Validate a release

1. Set the same version in `pyproject.toml`, the integration's `manifest.json`
   and `coex/__init__.py`. Update `CHANGELOG.md` and the release notes.
2. Run `make check`, `make test-ha`, and
   `make test-ha HA_REQUIREMENTS=requirements/ha-min.txt`.
3. Run `make build`. Confirm the wheel imports outside the checkout and the ZIP
   contains `custom_components/novastar_coex/` with its bundled client, translations,
   license and icons. Rebuild the wheel from the source distribution when packaging changes.
4. Review the staged diff, fixture identifiers and archive contents. Commit only
   the intended public files. Do not push a private repository's branches or tags.

## First GitHub publication

Run from this clean public checkout, authenticated as the repository owner:

```bash
gh repo create mikolalysenko/novastar-coex --public --source . --remote origin \
  --description 'Local Home Assistant integration for NovaStar COEX LED controllers, tested on MX40 Pro'
gh repo edit mikolalysenko/novastar-coex --enable-issues \
  --add-topic home-assistant --add-topic hacs --add-topic novastar \
  --add-topic coex --add-topic mx40-pro --add-topic custom-integration
git push -u origin main
```

GitHub CI must pass on the exact commit being released. This includes the client,
Home Assistant and packaging jobs, **hassfest**, and **HACS validation with no
ignored checks**. The HACS validator needs a public GitHub repository with a
description, topics, issues and an open-source license, so it cannot be fully
validated from an unpublished local checkout.

The integration supplies `brand/icon.png` and `brand/icon@2x.png` locally, supported
since Home Assistant 2026.3. See the official [brand-image requirements](https://contributors.home-assistant.io/core/integrations/brands/)
and [HACS integration requirements](https://www.hacs.xyz/docs/publish/integration/).

## Publish the release

After all GitHub checks pass, update the release date/status in the changelog and
remove any pre-publication wording from the README. Validate and commit those
changes, then wait for their checks before tagging:

```bash
git tag -a v0.2.0 -m 'NovaStar COEX 0.2.0'
git push origin v0.2.0
make build
gh release create v0.2.0 --verify-tag --title 'NovaStar COEX 0.2.0' \
  --notes-file docs/RELEASE_NOTES.md \
  dist/novastar_coex-v0.2.0.zip dist/novastar_coex-0.2.0-py3-none-any.whl \
  dist/novastar_coex-0.2.0.tar.gz dist/SHA256SUMS
```

Substitute the version for future releases. A published GitHub **release**, not
just a Git tag, is needed for the HACS default-list submission. HACS installs from
the component directory in the repository; the ZIP is for manual installation.
The wheel is the standalone client and does not install the HA integration.
No PyPI upload is performed by the workflows.

## Submit to the default HACS catalog

Users can install the public repository through HACS custom repositories before
catalog inclusion. Inclusion itself requires review by HACS maintainers; it is
not automatic when a release is published.

After the public repository installs successfully, both validators pass, and a
release is published, follow the [official submission procedure](https://www.hacs.xyz/docs/publish/include/).
Fork `hacs/default` as the owner/major contributor, create a branch from `master`,
add `mikolalysenko/novastar-coex` alphabetically to the `integration` JSON list,
and complete its current PR template. Leave maintainer edits enabled. Do not claim
catalog availability until the submission is accepted.

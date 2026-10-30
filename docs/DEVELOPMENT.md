# Development

The standalone client supports Python 3.12+. The Home Assistant tests use Python
3.14 and the pinned environments in `requirements/ha-min.txt` (2026.3.1) and
`requirements/ha-latest.txt` (2026.10.4). Install [uv](https://docs.astral.sh/uv/)
and run:

```bash
make sync
make check          # Ruff, mypy, client tests and release metadata validation
make test-ha        # Home Assistant setup, entities, writes and failure handling
make test-ha HA_REQUIREMENTS=requirements/ha-min.txt
make build          # Python wheel + source distribution + manual-install ZIP
```

`make test-ha` uses a separate `.venv-ha` and installs the selected pinned test
harness. All tests use a loopback fake controller or mocked data; they do not
connect to a physical wall. The client suite also runs without Home Assistant.
GitHub Actions tests the client on Python 3.12 and 3.14 and both Home Assistant
versions. HACS validation and hassfest run separately.

## Layout

| Path | Purpose |
| --- | --- |
| `custom_components/novastar_coex/` | Home Assistant integration and bundled brand images |
| `custom_components/novastar_coex/coex/` | HA-independent client, models and CLI |
| `dev/novastar_coex` | Relative symlink for editable client installs |
| `tests/` | Fake HTTP controller, client/CLI tests and sanitized hardware fixtures |
| `tests/ha/` | Tests using real Home Assistant config flows and entity platforms |
| `scripts/` | Release metadata validation and deterministic integration archive |

The wheel maps the nested `coex/` package to the import name `novastar_coex`.
Home Assistant imports it relatively, so `manifest.json` has no pip requirements.
Never import Home Assistant from the bundled client.

## Making changes

Add protocol behavior to the client and fake controller together. Preserve tests
for hardware response shapes, especially empty lists when cabinets are off, screen
and canvas IDs, and brightness units. Label unverified protocol assumptions in
`API.md` and `HARDWARE-VERIFICATION.md`.

The coordinator reads `CoexClient.get_status()` every 10 seconds and monitoring
every sixth poll. Entity writes go through `async_write()` for error reporting and
refresh. Use Home Assistant's shared HTTP session without closing it on unload.
Entity IDs use the config entry and screen IDs; preserve them across upgrades.

Keep `strings.json` and `translations/en.json` synchronized. New translations go
in `translations/<language>.json`. Run `make fmt` to apply formatting.

Do not check in deployment backups, access tokens, private hostnames, or raw
controller identifiers. The hardware fixtures preserve protocol shapes but replace
screen UUIDs, cabinet IDs and identifying names with synthetic values. To reproduce
the icon, run `uv run --with pillow python scripts/build_icon.py`.

Build from a clean checkout and install the wheel in an isolated environment when
changing packaging. The source distribution includes the development symlink and
support files so it can be rebuilt independently.

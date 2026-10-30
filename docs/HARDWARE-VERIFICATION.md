# Hardware verification

The existing hardware observations were recorded on an **MX40 Pro, V1.5.0**, in
September 2026. Release preparation adds automated tests; it does not represent a
new physical test of every control or of other controller models.

| Feature | Evidence |
| --- | --- |
| Screen list, layers and input sources | Captured MX40 Pro replies; parser regression tests |
| Working mode | Send-Only ↔ All-in-One changed the active screen mode |
| Input routing | Screen/layer request accepted; source group read back |
| Display mode | Readback agrees with writes: 0 normal, 1 blackout, 2 freeze |
| Brightness | With cabinets powered, 0.37 read back as 37%; wire unit is 0–1 |
| Cabinets off | Empty cabinet/display-parameter lists; brightness writes can be acknowledged without effect |
| Monitoring | Captured temperature, fan speed and runtime responses |
| Preset application | Simulated tests only; no saved presets in the hardware capture |
| Color-temperature / gamma writes | Simulated tests only |
| Cabinet mapping / identify | Request format tested in simulation; visual behavior needs confirmation |
| VMP lock and recovery | Error handling tested in simulation; a complete hardware lock/recovery session remains outstanding |
| Multiple screens / other COEX models | Simulated behavior or parser support only; physical verification needed |

The JSON fixtures in `tests/fixtures/` are sanitized captures. Screen UUIDs,
cabinet identifiers and identifying names have been replaced consistently;
response shapes, timing, dimensions, enum values and numeric measurements remain.

## Testing your controller

Start with a configured screen, working video, known controller address and VMP
closed. Record the model, firmware and current settings. Keep the wall visible and
restore its original settings after testing. Choose a brightness suitable for the
installation; API success alone does not prove a visible change.

```bash
uv run coex --host 192.0.2.10 status
uv run coex --host 192.0.2.10 screens
uv run coex --host 192.0.2.10 sources
uv run coex --host 192.0.2.10 params
uv run coex --host 192.0.2.10 monitor
```

Substitute the real address. Capture reads before and after each change. Verify
brightness with cabinets powered; confirm that blackout and freeze both restore
correctly with `normal`. Test processing modes only with a source timing suitable
for each mode, then select an input using the exact name returned by `sources`.
Apply presets only after saving a known preset in VMP. Open VMP to test the lock,
then close it and confirm recovery.

Do not overwrite the reference fixtures with raw captures. Sanitize addresses,
identifiers, names and other installation data before attaching evidence to an
issue. A contribution should describe both API readback and the visible result.

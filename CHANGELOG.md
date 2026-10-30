# Changelog

## 0.2.0 — 2026-10-30

- Local Home Assistant integration for NovaStar COEX, hardware-tested on MX40 Pro
  V1.5.0, with UI setup and controls for display, freeze, brightness, processing
  mode, input, presets, color temperature, gamma and cabinet mapping.
- Controller temperature, runtime and cabinet-count sensors.
- Bundled async client and CLI; no external Python package needed by HACS.
- Clear setup errors for invalid hosts, unavailable/locked controllers and missing
  screens; normalized hostnames and IPv6 URL handling.
- Reject malformed API envelopes and clear stale monitoring values after a failed read.
- Public installation, automation, troubleshooting, API and hardware-verification
  documentation, sanitized fixtures, MIT licensing and integration icons.
- Client and Home Assistant tests, GitHub CI, HACS/hassfest validation, aligned
  version metadata and reproducible release archives.

Other controller models, preset application, color-temperature/gamma writes and
multi-screen hardware behavior still need independent verification. See the
[verification matrix](docs/HARDWARE-VERIFICATION.md).

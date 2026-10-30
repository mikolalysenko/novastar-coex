# Contributing

Please use the [issue tracker](https://github.com/mikolalysenko/novastar-coex/issues)
for reproducible bugs and support for additional COEX models. Include the model,
firmware, integration and Home Assistant versions, reproduction steps, expected
behavior and sanitized logs. State whether the result was observed on hardware or
only in a simulator. Do not post tokens, private addresses, serial numbers, or
deployment backups.

For code changes, follow [development instructions](docs/DEVELOPMENT.md), add a
regression test for changed behavior, and run `make check` and `make test-ha`.
Update the docs for user-visible changes. Keep protocol changes separate from
unrelated cleanup where practical. Contributions use the repository's MIT license.

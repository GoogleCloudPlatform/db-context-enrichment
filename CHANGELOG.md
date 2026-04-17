# Changelog

## [0.4.3](https://github.com/GoogleCloudPlatform/db-context-enrichment/compare/v0.4.2...v0.4.3) (2026-04-02)


### Features

* add Spanner and CloudSQL support to value search generation ([#50](https://github.com/GoogleCloudPlatform/db-context-enrichment/issues/50)) ([5a56582](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/5a565825292bc0c8ecab82b30a9dbc9f021d6a63))
* **value-search:** extend support to Spanner, MySQL, and Postgres ([5a56582](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/5a565825292bc0c8ecab82b30a9dbc9f021d6a63))


### Bug Fixes

* **build:** disable strip and upx to resolve windows pyinstaller crash ([#52](https://github.com/GoogleCloudPlatform/db-context-enrichment/issues/52)) ([e07c52b](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/e07c52bd353c0b1f7c9fe15c4ffd2da1c2dc3a5f))

## [0.4.2](https://github.com/GoogleCloudPlatform/db-context-enrichment/compare/v0.4.1...v0.4.2) (2026-03-25)


### Bug Fixes

* **build:** bundle lupa and fakeredis in PyInstaller executable ([#45](https://github.com/GoogleCloudPlatform/db-context-enrichment/issues/45)) ([b4202d0](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/b4202d076066bbb2cce4c8972c6c2d8447a13ef2))

## [0.4.1](https://github.com/GoogleCloudPlatform/db-context-enrichment/compare/v0.4.0...v0.4.1) (2026-03-25)


### Features

* add value index generation functionality ([#42](https://github.com/GoogleCloudPlatform/db-context-enrichment/issues/42)) ([e3784ae](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/e3784ae3bbe4da8c24c4735568b6bc983f3b120d))

## [0.4.0](https://github.com/GoogleCloudPlatform/db-context-enrichment/compare/v0.3.0...v0.4.0) (2026-03-06)


### Features

* bundle genai-toolbox binary to streamline extension installation ([#27](https://github.com/GoogleCloudPlatform/db-context-enrichment/issues/27)) ([5090d68](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/5090d68e3937b3e2d303626145c2d205162f735d))
* **skill:** skill for authoring tools.yaml ([#28](https://github.com/GoogleCloudPlatform/db-context-enrichment/issues/28)) ([f69ca39](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/f69ca397d7d6649a363576da4214fc12e80bb8b6))


### Bug Fixes

* **ci:** add required github app config to trigger release please ([#35](https://github.com/GoogleCloudPlatform/db-context-enrichment/issues/35)) ([f641fbd](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/f641fbd2c9862fd5f77032571bce1a50efa96654))
* **ci:** remove component from release please config to use root tag ([#30](https://github.com/GoogleCloudPlatform/db-context-enrichment/issues/30)) ([9cc7205](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/9cc7205652b52552dd3ee25f34c2a6dfdc23124e))
* **ci:** remove unsupported toml config from release please ([#33](https://github.com/GoogleCloudPlatform/db-context-enrichment/issues/33)) ([edc30a5](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/edc30a57f7bfbcba4ee2beaeeb1035cdb3d75035))
* **ci:** strictly align release-please config with mcp-toolbox and add debug workflow ([#34](https://github.com/GoogleCloudPlatform/db-context-enrichment/issues/34)) ([27bbbf0](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/27bbbf08767e37d18c8a27c776dded600e3bdd64))


### Miscellaneous Chores

* force 0.4.0 release via footer ([#32](https://github.com/GoogleCloudPlatform/db-context-enrichment/issues/32)) ([c133b9b](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/c133b9b7347c23a74126054f73b2895714948c85))

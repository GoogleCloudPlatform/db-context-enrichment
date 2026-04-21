# Changelog

## [0.5.0](https://github.com/GoogleCloudPlatform/db-context-enrichment/compare/v0.4.3...v0.5.0) (2026-04-21)


### Features

* **autoctx:** introduce automated context generation ([#95](https://github.com/GoogleCloudPlatform/db-context-enrichment/issues/95)) ([57f8aa7](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/57f8aa7b4f0d957cbbcd46b5bdd3f5cc8e8a4a82))
* **bootstrap:** enrich workflow with user-provided docs and code ([#70](https://github.com/GoogleCloudPlatform/db-context-enrichment/issues/70)) ([04c8455](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/04c8455ead11cd9abfa93a01bc7fab3b4dbbb157))
* **bootstrap:** enrich workflow with user-provided docs and code ([#72](https://github.com/GoogleCloudPlatform/db-context-enrichment/issues/72)) ([bd04743](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/bd047438adbe21157f53c0ed613ae8e63d5f3ca3))
* **evaluate:** add custom runner configs to lower evalbench parallelism ([#65](https://github.com/GoogleCloudPlatform/db-context-enrichment/issues/65)) ([f0758fa](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/f0758fae4e8fc529f726537551f102894d038d7c))
* **evaluate:** populate gcp_project_id in llmrater config ([#90](https://github.com/GoogleCloudPlatform/db-context-enrichment/issues/90)) ([016af70](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/016af70725ebbea413dfb114513837ab63bdbeb2))
* **evaluate:** simplify golden dataset format and write configs dire… ([#68](https://github.com/GoogleCloudPlatform/db-context-enrichment/issues/68)) ([a76b4bb](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/a76b4bbf16e8ea646af87bba28361e6b4a4686f8))
* **evaluate:** support llm rater configuration in evalbench generator ([#64](https://github.com/GoogleCloudPlatform/db-context-enrichment/issues/64)) ([d181b82](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/d181b82f4582c0d906600581e424cdc0bf4a3d86))
* **evaluate:** unify failure reporting and add execution errors ([#80](https://github.com/GoogleCloudPlatform/db-context-enrichment/issues/80)) ([c11ff47](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/c11ff4787f6229c70f9b5eb4dd8599da75fd0819))
* **evaluate:** use gemini-2.5-pro for evaluation rater ([#67](https://github.com/GoogleCloudPlatform/db-context-enrichment/issues/67)) ([5c8f92d](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/5c8f92d5c41c4c322fc2af71b41f753576837f84))
* **facet:** enforce qualified table names in prompts ([#85](https://github.com/GoogleCloudPlatform/db-context-enrichment/issues/85)) ([b37480f](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/b37480f2a6db32d76f10f04ade46f24a2e55908c))
* **hillclimb:** support eval result reading tool ([#69](https://github.com/GoogleCloudPlatform/db-context-enrichment/issues/69)) ([bb5a249](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/bb5a249afc075eb98826c9ae25711d3a258124aa))
* **mcp:** add autoctx-hillclimb workflow skill and tools ([#59](https://github.com/GoogleCloudPlatform/db-context-enrichment/issues/59)) ([2236964](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/2236964f90198d7ea8ad047449e9c8769405dca1))
* **mcp:** adopt ADC support for Cloud SQL and AlloyDB ([#78](https://github.com/GoogleCloudPlatform/db-context-enrichment/issues/78)) ([f4091fa](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/f4091fa15df50aa055d9efce766cfeacda22ce9b))
* **mcp:** centralize Gemini model configuration ([#73](https://github.com/GoogleCloudPlatform/db-context-enrichment/issues/73)) ([97c5c25](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/97c5c253d71a2a5818eaf466f9d5f196fdc3ba39))
* **mcp:** migrate autoctx infrastructure to autoctx/ folder ([#92](https://github.com/GoogleCloudPlatform/db-context-enrichment/issues/92)) ([0b4f52d](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/0b4f52df743ccfce6037bcb783932f499bb69554))
* **mcp:** switch default model to gemini-2.5-flash ([#93](https://github.com/GoogleCloudPlatform/db-context-enrichment/issues/93)) ([60800e5](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/60800e55ee30f5fa4773de1ace76dd238ea4ca46))
* **mcp:** update evalbench version to 1.4.0 ([#83](https://github.com/GoogleCloudPlatform/db-context-enrichment/issues/83)) ([0b4ffb3](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/0b4ffb322e644b6d38c33ccecf4cef8f2582cfb4))
* **skills:** update bootstrap skill to include upload URL ([#77](https://github.com/GoogleCloudPlatform/db-context-enrichment/issues/77)) ([fd65bff](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/fd65bff761ac65056e4f5a8d3161ec003e0f9378))


### Miscellaneous Chores

* force release version 0.5.0 ([da04e7c](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/da04e7c990d6ef7b94a56779d6f1b312bcc3f59d))
* force release version 0.5.0 ([#97](https://github.com/GoogleCloudPlatform/db-context-enrichment/issues/97)) ([82364d6](https://github.com/GoogleCloudPlatform/db-context-enrichment/commit/82364d613c2b27d0b105302de8503afeac60a842))

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

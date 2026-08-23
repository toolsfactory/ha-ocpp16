# Changelog

## [0.2.0](https://github.com/toolsfactory/ha-ocpp16/compare/v0.1.0...v0.2.0) (2026-08-23)


### ⚠ BREAKING CHANGES

* every config entry created under the ocpp domain (including this project's own dev instance) is orphaned and must be deleted and re-added under ocpp16 -- Home Assistant cannot migrate a config entry across a domain-string change. See docs/development/DECISIONS.md for the full rationale and the same property in the first occp -> ocpp rename.
* the integration's domain changes from occp to ocpp. Unlike every other breaking change made this session, this one has no migration path at all - a config entry belongs permanently to the domain that created it. Every entry loaded under occp (including every entry in the development instance used throughout this session) is now attached to an integration Home Assistant can no longer find, and must be deleted and re-added under ocpp from scratch after upgrading.
* **services:** occp.set_power_limit and occp.clear_power_limit no longer return a rejected/not_supported/unknown status as response data - they raise ServiceValidationError instead. A caller that branched on result["status"] to detect failure must now catch the exception instead; a caller that only checked for a raised error needs no changes.
* device identifiers, entity unique_ids, and current_power_w availability semantics all change shape. Existing entities and devices need manual removal and will be recreated under the new scheme; no migration is provided (pre-1.0).
* migration path is provided.

### Features

* add an Active Phases sensor ([a260513](https://github.com/toolsfactory/ha-ocpp16/commit/a2605135de32a96f5d6deef59e4ba123e2f2fbe4))
* add direct TLS (wss://) support, no reverse proxy needed ([6b08aaa](https://github.com/toolsfactory/ha-ocpp16/commit/6b08aaa7ecd0e9973ed8864d9d6643f4bb5eba24))
* add heartbeat sensor, reset/unlock buttons, trigger_message ([95d550b](https://github.com/toolsfactory/ha-ocpp16/commit/95d550b00a01ee8c66bbce718b783c3c79369eda))
* add power-limit number entity and get_diagnostics service ([1baea80](https://github.com/toolsfactory/ha-ocpp16/commit/1baea802d4d71e477533dfb1a2a6d3f46d2730da))
* add session/connection diagnostics, restore power limit ([d6b9e84](https://github.com/toolsfactory/ha-ocpp16/commit/d6b9e84f2937b01e3267bdfae8d1cff2d2509a4c))
* **config-flow:** add a reconfigure flow for host/port ([deb8ec8](https://github.com/toolsfactory/ha-ocpp16/commit/deb8ec8c221e3738faed534e598678c7abedf94b))
* **diagnostics:** add config entry diagnostics ([76c913b](https://github.com/toolsfactory/ha-ocpp16/commit/76c913bfbc3ccbe6aab3a636ffa8e4f3bb90853d))
* enforce the 90% coverage floor locally via pyproject.toml ([3109542](https://github.com/toolsfactory/ha-ocpp16/commit/31095423ac4cbaf05cb93f915c0870e0f10d9675))
* get the imported OCCP integration to a working, tested state ([e526dc5](https://github.com/toolsfactory/ha-ocpp16/commit/e526dc5c7cda859ff3b5258e5d53663c01c7acfd))
* import OCCP's Home Assistant layer and standalone core (unstructured) ([fb8295a](https://github.com/toolsfactory/ha-ocpp16/commit/fb8295a67b003c95b3e67f86b17a4e4bf1d6b02e))
* quality-review fixes, four new services, and a push coordinator ([151ad3f](https://github.com/toolsfactory/ha-ocpp16/commit/151ad3faeb246fcda3005ed3d746912211d5eee1))
* rename domain ocpp to ocpp16, drop LBBRHZN doc, clean up docs ([1a2469e](https://github.com/toolsfactory/ha-ocpp16/commit/1a2469e02c422e4672fd23e522aeb351587989ca))
* rename project identity from OCCP to OCPP ([698b9b7](https://github.com/toolsfactory/ha-ocpp16/commit/698b9b7166b392463526aab77955c7c3211ce2ef))
* restore Phase-3 diagnostic sensors across a HA restart ([775ac57](https://github.com/toolsfactory/ha-ocpp16/commit/775ac57c343c3585d13bcc263f0eb98d02ae9dd7))
* **sensor:** disable unmapped measurand sensors by default ([86e730c](https://github.com/toolsfactory/ha-ocpp16/commit/86e730c67d4f6f973ca2dd5d2b69e0ed9d52d4ff))
* **services:** add optional device_id to authorize_id_token ([26b49fa](https://github.com/toolsfactory/ha-ocpp16/commit/26b49fa4a188ce723cd108ac260de937457f5919))
* **services:** raise on rejected set_power_limit/clear_power_limit ([1acdcb1](https://github.com/toolsfactory/ha-ocpp16/commit/1acdcb174c21f8fd51cb09dee64fa0075c38d76e))
* **translations:** translate en.json to English, add icons.json ([1810bc1](https://github.com/toolsfactory/ha-ocpp16/commit/1810bc15a134fdaca2d16aa7f781bd59bdf00eb1))


### Bug Fixes

* add entity name translations, fixing duplicate entity names ([627ff20](https://github.com/toolsfactory/ha-ocpp16/commit/627ff2065b7a243196eb4f3981046bfa81c9561f))
* **config-flow:** validate authorization file and default idTag ([60a25e4](https://github.com/toolsfactory/ha-ocpp16/commit/60a25e44f32a98cf31295f45920db340cfaabdbd))
* **core:** mask idTag values in INFO-level logs ([79c5404](https://github.com/toolsfactory/ha-ocpp16/commit/79c5404d54487d02aaabfbf889dd9470c1c9616e))
* correct unit handling in power calculations ([da300de](https://github.com/toolsfactory/ha-ocpp16/commit/da300de2a8e3169cbcf447c72e710a519ad883e0))
* entity-scoped identifiers, current_power_w unknown not unavailable ([8761f3c](https://github.com/toolsfactory/ha-ocpp16/commit/8761f3c1e125ac916dd321abec3c237c874fb408))
* **entity:** translate measurand names, use English device names ([259859b](https://github.com/toolsfactory/ha-ocpp16/commit/259859b0b6d5c700c4b54133d6892965a555cb07))
* index meter values by (measurand, phase), not measurand alone ([95c0b22](https://github.com/toolsfactory/ha-ocpp16/commit/95c0b22491965955056b4cfbec88749cc4931b3a))
* **init:** keep services registered across entry reload/unload ([36888ad](https://github.com/toolsfactory/ha-ocpp16/commit/36888addcb11e665b83c4133f87bb56e0bb84776))
* **init:** translate setup errors, stop leaking raw error text ([f913793](https://github.com/toolsfactory/ha-ocpp16/commit/f9137938d65d8e73aa7d1500ed279c5eb6544471))
* parse numeric measurand values instead of returning raw strings ([a8919c0](https://github.com/toolsfactory/ha-ocpp16/commit/a8919c0471256c0c6e4060b4a3aaacf632920fb8))
* resolve service actions to the device's own entry ([4a2282c](https://github.com/toolsfactory/ha-ocpp16/commit/4a2282cc21b0b13ae05bc5ea0f606ce2d52f4125))
* scope GetCompositeSchedule refresh to the right charge point ([1bfb4cf](https://github.com/toolsfactory/ha-ocpp16/commit/1bfb4cf6c6b8dc37b4265240fcb1d19d1a34caba))
* **scripts:** activate_venv trusts a stale VIRTUAL_ENV blindly ([1726a9a](https://github.com/toolsfactory/ha-ocpp16/commit/1726a9a06aee7532cf9ba04394bc367dbe9d3956))
* **scripts:** fix script/test's broken pytest fallback and cleanup ([8d80bfa](https://github.com/toolsfactory/ha-ocpp16/commit/8d80bfaa7a00a73fee3183d8e2f86c990d783013))
* **sensor:** coalesce concurrent GetCompositeSchedule refreshes ([86435f0](https://github.com/toolsfactory/ha-ocpp16/commit/86435f05980f727faaf78d1bac76b9beaee29a42))
* **sensor:** narrow effective_power_limit's blanket except Exception ([3bcede5](https://github.com/toolsfactory/ha-ocpp16/commit/3bcede5b68856dcc7102d76974e09cff0e81e230))
* **services:** raise on rejected reset/unlock/change_configuration ([c76eca2](https://github.com/toolsfactory/ha-ocpp16/commit/c76eca2c1c7e7346af343198293bf8259ae1b3d9))
* validate the authorization file, clean error on setup failure ([e2dc7bf](https://github.com/toolsfactory/ha-ocpp16/commit/e2dc7bff1bdddf275f8ab3abcd0e6679bd19150e))

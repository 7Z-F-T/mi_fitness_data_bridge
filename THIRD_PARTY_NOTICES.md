# Third-party notices and provenance

## Fork lineage

This repository (`7Z-F-T/mi_fitness_data_bridge`) is a fork of
[`shkyyy18/mi_fitness_data_bridge`](https://github.com/shkyyy18/mi_fitness_data_bridge),
with subsequent development by the fork maintainer. The upstream project was
extracted from the MIT-licensed [`binglua/mi-fitness-mcp-cn`](https://github.com/binglua/mi-fitness-mcp-cn)
code used by the local Health Assistant. That project states that it is based on
[`kubulashvili/mi-fitness-mcp`](https://github.com/kubulashvili/mi-fitness-mcp)
and adds China-region Mi Fitness cloud support.

The original MIT copyright notice for Aleksej Kubulashvili and the upstream
project's copyright line are preserved in `LICENSE`.

The upstream repository's license history includes an AGPL-3.0-only period after
2026-08-03. This fork is distributed under **AGPL-3.0-only** and preserves the
upstream attribution and notices. The original MIT text for the pre-2026-08-03
upstream code remains in `LICENSE`.

## Changes in this fork

- Positioned the package as a reusable local health-data bridge.
- Added portable JSON and CSV exports.
- Added a local Vue web dashboard (`frontend/`) and a read-only FastAPI API with
  an explicit local sync action.
- Added per-dataset sync history, incremental sync by default, and `--full`
  re-sync.
- Added the optional `coach` extension for local goals, training profiles and
  plans, with opt-in LLM suggestions.
- Added FDS per-second workout-detail parsing, including the v9 running and v7
  no-step channel tables.
- Added public-project security, contribution, CI, privacy and deployment
  documentation.

## Workout-detail protocol

The FDS workout-detail protocol module (`src/mi_fitness_mcp/adapters/fds.py`) is
an independent implementation informed by the decompiled-APK protocol notes and
MIT-licensed reference code of
[kevinkwee/Mi-Fitness-Sync](https://github.com/kevinkwee/Mi-Fitness-Sync)
(suffix construction, AES-CBC parameters, per-second record channel tables and
GPS record layout). That project's MIT license terms are acknowledged here; no
code was copied verbatim beyond protocol constants required for interoperability.

## Optional dependencies and trademarks

The optional `.[coach]` extra installs the
[Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python), which
is distributed under the MIT license. Anthropic, Claude, OpenAI, DeepSeek, Qwen,
Kimi, Ollama, Xiaomi, Mi Home, and Mi Fitness are trademarks of their respective
owners; this project is not affiliated with or endorsed by them.

`server.json` and `glama.json` retain upstream registry/listing identifiers for
provenance. They are not a claim that this fork is the upstream publisher.

No Xiaomi source code, logo, or official SDK is included. The cloud adapter is an
unofficial community implementation.

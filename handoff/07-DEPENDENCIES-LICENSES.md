# Pinned dependencies, downloads and license boundaries

Prepared 2026-10-25. This is an engineering inventory and review checklist, not a legal clearance or a complete transitive SBOM. Check company policy and the **exact distributed versions'** terms before production. Do not infer a model's commercial-use rights from its being available locally.

## Exact container identities

Authoritative pins are in `company/render.py`:

```text
ghcr.io/berriai/litellm-database@sha256:87a881738240d0458a47588dd45cd819b00966ae3565786a7818e6d17d837921
postgres@sha256:f4610795587492cd4fb887c2dc3de301b813278bb6f616992061141b5f15ac36
caddy@sha256:eb4d35b7452d1ab6171fbdbe8d9275b2301dad6dad92115d91e19fb9b24d510f
```

The pinned gateway image is also reused for the lightweight Python portal process; it receives a separate restricted environment, not the gateway master secret. Home recorded LiteLLM 1.105.5 and Caddy 2.11.7. Treat image digests as the deployment identifiers; do not guess a PostgreSQL tag/version from its name. Inspect approved image metadata locally if needed. Images and their complete dependencies are not inside this ZIP.

## Native publisher downloads

Authoritative metadata, including sizes, is in `company/components.json`. No hosted inference subscription/key is included.

| Artifact | Version | Official URL |
|---|---|---|
| OpenCode Windows x64 ZIP | 1.18.21 | https://github.com/anomalyco/opencode/releases/download/v1.18.21/opencode-windows-x64.zip |
| Claude Code Windows x64 EXE | 2.1.240 | https://downloads.claude.ai/claude-code-releases/2.1.240/win32-x64/claude.exe |

Use `components.json` as the machine-readable source of truth for every checksum; all three relevant actual hashes are:

```text
OpenCode ZIP: f8cc5477f478fa129ece99b550d508363ceff612f99d859042e526b13b951542
OpenCode EXE: ea4f4d4bec95cd41baf0fc53adc4e34b31e1c8676dc5b2507c8797ab1884af18
Claude EXE:   f7ee87c58d315bedbd38fc8923ce7b955dbbab2afe50d9d15c059463a70869da
```

The helper can reuse an already present binary only when its exact hash matches. Otherwise it downloads the approved pinned artifact and verifies size/hash/member constraints. Original download sizes are 60,622,013 bytes for the OpenCode ZIP and 337,745,568 bytes for Claude EXE; extracted size/cache footprint is additional. These native third-party binaries are **not** redistributed in the administrator ZIP; only our helper is included.

First-time setup needs approved egress to the container registries and native publisher download/redirect hosts. PyPI is needed only if IT runs the local Python development tests without an existing environment. Model calls do not require a cloud LLM API. Fully air-gapped deployment/mirroring and proxy-specific installation are not implemented; do not replace these URLs with arbitrary mirrors or disable hash/TLS checks.

## Python and Windows build prerequisites

`server/requirements.txt` pins FastAPI 0.136.3, Uvicorn 0.51.0, HTTPX 0.28.1, cryptography 50.0.0, Starlette 1.3.1 and Pydantic 2.13.4. This is a direct dependency list, not a hash-locked inventory of every transitive wheel. Container deployment uses the exact pinned image already validated for imports. If an approved registry/image is unavailable or incompatible, stop and plan a bounded version change; do not substitute `latest` silently.

The Windows helper uses .NET Framework libraries and the x64 Framework compiler for rebuilds. Normal users do not need a C# development environment. Project-specific Git/SDK/compiler tools are not installed by MiniPC Connect. The helper is unsigned until IT signs/approves it; SHA-256 integrity does not prove publisher identity.

## License/source review

Official public license pages checked for this handoff; these links refer to the maintained upstream sources and do not replace inspection of notices within the pinned artifacts:

- **LiteLLM:** upstream distinguishes MIT-covered content from `enterprise/`, which has its own license. This deployment uses the account/API-key core, not a claim of Enterprise SSO entitlement. [Official license](https://github.com/BerriAI/litellm/blob/main/LICENSE).
- **OpenCode:** upstream publishes an MIT license. Preserve required notices if redistributing modified/bundled copies. The OpenCode application and any separately offered hosted model services are different licensing/billing questions. [Official license](https://github.com/anomalyco/opencode/blob/dev/LICENSE).
- **Caddy:** upstream Apache-2.0 terms apply to its source; inspect image dependencies/notices as part of release approval. [Official license](https://github.com/caddyserver/caddy/blob/master/LICENSE).
- **PostgreSQL:** upstream PostgreSQL License is permissive subject to its notices and conditions. [Official license](https://www.postgresql.org/about/licence/).
- **Claude Code:** its official repository points to Anthropic Commercial Terms, not an MIT grant. Technical local-model compatibility is experimental and is **not** a declaration that any company may use or redistribute it without conditions/entitlement. Obtain company legal/vendor-policy clearance; leave its UI checkbox off if unresolved. [Official license reference](https://github.com/anthropics/claude-code/blob/main/LICENSE.md).
- **Model weights/runtime:** entirely separate from the gateway. Record exact company model ID/version, weight license, runtime license, commercial/internal-use conditions and redistribution restrictions. The home model's terms do not transfer automatically.
- **Docker/OS/Python/.NET and other transitive packages:** already installed tooling and container contents retain their respective licenses. Use IT's approved inventory/scanning process; no enterprise-wide license assurance or complete SBOM is claimed by this handoff.

No paid provider, Enterprise subscription or billing purchase is enabled by the package. That fact does not itself certify every third-party usage right. If Claude is not approved, the system can be evaluated with OpenCode alone; do not buy or activate another service automatically. Preserve authorship/license notices of all third-party components; this bundle does not relicense them.

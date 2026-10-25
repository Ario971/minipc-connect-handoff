# Architecture and security boundaries

## Request paths

```text
Windows browser / local helper / local Harness
              |
              | verified HTTPS, approved LAN address:port
              v
Linux MiniPC: Caddy
    /connect/         -> static portal + public per-site download
    /connect/api/*    -> portal service on loopback (default 18401)
    /ui/, /v1/*, ...  -> LiteLLM on loopback (default 18400)
                            |                     |
                            v                     v
                    existing model API     PostgreSQL loopback
                    supplied by admin      (default 15432)
```

The Compose services use host networking on Linux, with explicit binds. Only the selected HTTPS address/port is intended for laptop access. The backend model is not installed or exposed by this package. HTTP loopback is used inside MiniPC; the laptop-to-MiniPC connection remains HTTPS. An upstream on another private host would be a separate network trust decision.

## Responsibilities

| Component | Responsibility | Not responsible for |
|---|---|---|
| Existing model runtime | Weights, inference, context/KV cache, actual concurrent slots | Users, Windows installations, HTTPS portal |
| LiteLLM | Account/role authority, model alias, inference keys, rate/admission limits | Model hosting or laptop tools |
| PostgreSQL | LiteLLM accounts/keys/models/state | Windows profile storage |
| Caddy | TLS, LAN scope, static download, reverse routing | User identity |
| Portal Python service | Same-user device approval, pairing, encrypted recovery journal | Independent passwords or unrestricted master-key administration |
| Windows helper | Verify downloads, retrieve scoped keys, DPAPI profiles, test and launch | Hosting a model, silently trusting a CA or overriding IT restrictions |
| OpenCode / Claude Code | Interact with model, request local tool execution | Guarantee the model's quality or parallel throughput |

## Account and device lifecycle

1. Admin creates a LiteLLM account/invitation. User chooses a gateway password. Email is the gateway login identifier, not proof of Google/Microsoft SSO.
2. Helper starts a pending request with a random device ID. Server returns a public ten-character code plus a private high-entropy device token.
3. Browser URL carries only `#pair=PUBLICCODE`. The helper keeps its private token in its protected local recovery state. A public code alone cannot retrieve inference keys.
4. Browser login uses LiteLLM. The portal checks identity/role against LiteLLM rather than trusting only decoded token fields. Browser session lives in memory, not localStorage.
5. User approves their device and one or both harnesses. The service uses that user's session to issue separate inference-only keys. No master key is supplied to the portal container.
6. Helper stages independent profiles and runs an actual bounded Read-tool test with a random local marker for each selected harness. No ordinary Ready state is published before these pass and final server acknowledgement is recorded.
7. Renewal stages and verifies replacement keys before revoking old keys. Failed tests preserve prior usable profiles. Interrupted finalization retains checkpoints for retry; do not delete them.
8. Own-device revocation removes the device's associated keys. It does not uninstall the harness, erase local projects or clear unrelated profiles.

### Current implementation limits

| Setting | Current value |
|---|---|
| Public alias | `local-coder` |
| New per-harness key | 30 days, 1 parallel request, 30 RPM, 60,000 TPM |
| Gateway global concurrency | 5; backend capacity must still be measured |
| Gateway inference timeout | 180 seconds, no provider fallback/retries |
| Helper per-harness test | 150 seconds; both tests run sequentially |
| Pending code / approved request | 10 minutes / 30 minutes |
| Completed receipt recovery | 7 days |
| Model discovery | One supplied service, 8-second HTTP timeout, 1 MiB response, at most 256 model IDs |
| Portal API body | 16 KiB; Caddy general body ceiling 2 MB |
| Portal workers | 1; encrypted SQLite + process lock |

These are not SLAs or guarantees. Two keys on one laptop can compete for global capacity; one per-key limit is not a per-person total. Other model consumers, including existing bots, consume the same runtime resources outside this gateway's accounting. Current contexts are configured explicitly; a maximum advertised by model training is not proof the running server has that context available per slot.

## Configuration/data ownership

`company/setup.py init` creates new random database credentials, LiteLLM master/salt keys and a portal encryption key. It does not import home users, sessions or model routes. Admin model selection creates/updates a database route with ID `minipc-<site_id>-model`. The portal reports `tool_use_verified: false` after discovery/selection: compatibility must be tested.

Server secret paths are root-restricted. Portal pending credentials/recovery payloads are encrypted with Fernet in `data/portal/state.sqlite`; index metadata remains visible to an authorized filesystem reader. LiteLLM's encryption/key-management state depends on its own database and salt/master material. Back up state and secrets together under company controls.

Windows inference keys use DPAPI CurrentUser with restrictive ACLs. This protects at rest from other ordinary accounts; it is not protection against malware running as the same user, an administrator or a compromised laptop. Keys appear in the launched process environment as required by each harness, not in public download configuration.

Prompt logging/telemetry are reduced by supplied config. This does not prove every third-party component has zero egress or zero local history. Apply company egress policy and inspect dependencies. Harness tool permissions remain manual in normal use; the helper's smoke test is limited to its own generated fixture. The model is not an isolation boundary for sensitive projects.

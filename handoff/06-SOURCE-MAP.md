# Source map, API contracts and reproducible builds

Paths here are relative to the extracted release root, not the original home workspace. The exported layout intentionally contains no personal workspace, caches, SSH files, credentials or installed model. All runtime source required by this deployment is included.

## File map

| Path | Purpose / important callers |
|---|---|
| `company/setup.py` | Linux CLI: `wizard`, `init`, `start`, `activate-owner`, `status`, `publish` |
| `company/site.py` | Validates site identity/origin/CIDRs/email/context; imported explicitly to avoid Python's stdlib `site` name collision |
| `company/render.py` | Generates Compose, Caddy, LiteLLM and portal config; immutable container digests |
| `company/components.json` | Pinned native artifact URLs/hashes/sizes and baseline gateway limits; empty initial model list |
| `company/discovery.py` | Bounded explicit private/loopback `/v1/models` discovery; imported by portal |
| `company/test_site.py`, `test_deployment.py`, `test_package.py` | Offline configuration/discovery/template/archive checks |
| `company/check_package.py` | Read-only ZIP manifest/completeness/private-path guard |
| `company/build-package.ps1` | Builds a new non-overwriting handoff ZIP from original OR exported layout; includes manifest and external archive checksum |
| `server/config.py` | Loads `MINIPC_PORTAL_CONFIG`, `MINIPC_PORTAL_STATE`, `MINIPC_PORTAL_KEY`; validates HTTPS public origin + loopback gateway |
| `server/app.py` | FastAPI factory, bounded same-origin API, role checks, cleanup lifecycle, admin model discovery/selection |
| `server/gateway.py` | Bounded LiteLLM client; identities, keys, sessions, model CRUD; no cloud fallback |
| `server/pairing.py` | Account-owned enrollment/renewal/recovery state machine and safe cleanup |
| `server/store.py` | Fernet encrypted payloads in SQLite; connections always closed |
| `server/requirements.txt` | Pinned direct development/runtime requirements; generated deployment reuses the pinned gateway image |
| `server/tests/` | Fake-gateway API/pairing tests; not proof of real inference |
| `portal/index.html`, `style.css`, `app.js` | Persian RTL central browser UI, public downloads, in-memory login, device approval/revoke/admin model controls |
| `source/windows/Deployment.cs` | Public deployment/CA/hash validation; CurrentUser DPAPI/ACL helpers |
| `source/windows/Artifacts.cs` | Download or verified reuse of exact native releases |
| `source/windows/Gateway.cs` | Narrow legacy client/key checks reused by native flow |
| `source/windows/Client.cs` | Isolated process environments/config, actual Read-marker acceptance and launches |
| `source/windows/Portal.cs` | Browser pairing, private checkpoint, atomic profile promotion/rollback, Start entries |
| `source/windows/Wizard.cs` | Program entry; browser pairing default, project picker; explicit `--classic` retains legacy GUI |
| `source/windows/Tests.cs`, `UITests.cs` | Native contracts and legacy offscreen GUI test source |
| `windows/MiniPCConnect.exe` | Prebuilt helper; unchanged from the clean successful home enrollment |
| `windows/build-helper.ps1` | Rebuilds helper with installed Windows Framework compiler; does not install or enroll it |
| `handoff/` | Documentation, non-secret input worksheet, sanitized historical evidence/report template |
| `MANIFEST.sha256` | SHA-256 of every archived payload file; does not list itself |

## Portal API surface

All routes below have prefix `/connect/api`. JSON request fields are checked by `server/app.py`. Browser session authorization is `Authorization: Bearer <LiteLLM UI session>`. Helper authorization is the **private device token**, not the public code, except `/pair/start`. Do not put either token into a URL, report or shared config.

| Method / suffix | Caller | Request / intent |
|---|---|---|
| GET `/info` | Public | Public site info, `ManagedModels` flag |
| POST `/login` | Browser | `email`, `password`; returns session and validated user |
| GET `/me` | Browser session | Current validated identity |
| POST `/logout` | Browser session | Cancels that session's unfinished approvals, then LiteLLM `/session/logout` |
| POST `/pair/start` | Helper/public bounded endpoint | `device_id` = 32 lowercase hex; `label` <=64 chars; returns code/private token |
| GET `/pair/{code}` | Browser session | View request for approval; public code matches `[A-Z2-9]{10}` |
| POST `/pair/approve` | Browser session | `code`, `harnesses` = one/both of `opencode`, `claude` |
| GET `/poll` | Private helper token | Enrollment state/approved scoped material |
| POST `/progress` | Private helper token | `phase`, optional `harness`; update test phase |
| POST `/complete` | Private helper token | `receipts` for selected harnesses; idempotent final acknowledgement |
| POST `/fail` | Private helper token | Sanitized bounded `reason`; scoped rollback/cleanup |
| GET `/devices` | Browser session | Own devices; refreshes deferred cleanup authorization for same owner |
| POST `/device/revoke` | Browser session | `device_id`; only own device |
| GET `/admin/models` | `proxy_admin` | Existing alias/ID list, managed flag |
| POST `/admin/discover` | `proxy_admin` | `base_url`, optional secret `api_key`; explicit upstream model listing |
| POST `/admin/select` | `proxy_admin` | Same plus `model_id`; create/update managed route, not model process |

The exact state schema/receipts are implemented in `server/pairing.py` and `source/windows/Portal.cs`; do not reimplement a client using guessed status values. FastAPI interactive docs/OpenAPI are intentionally disabled. Browser same-origin/body guards and Caddy's overwritten client-address header depend on the portal staying loopback-only. One worker is required by the current locking/rate design.

## Native behavior and supported invocation

Normal use is `MiniPCConnect.exe` beside its per-site `pilot.json` and public root. `--launch opencode` / `--launch claude` opens the project selector and launches the existing isolated profile. `--config PATH` and `--root PATH` are explicit administrative/testing overrides; ordinary users should not need them.

`--pair-acceptance` is a diagnostic mode for test automation. `--acceptance` and `--classic` are legacy flows. Do not tell company users to enter passwords through command arguments/stdin automation or use legacy GUI just to bypass portal/trust failures. Use the documented normal browser flow.

## Rebuild and package a company-reviewed change

Work from a copy of the extracted bundle. Review/test source changes before running:

```powershell
& '.\windows\build-helper.ps1'
```

IT may then sign the exact helper. Rebuilding/signing changes its hash, so the original MANIFEST no longer applies to this working copy. Run source/native checks, retain the original release for comparison, then create a **new** archive:

```powershell
& '.\company\build-package.ps1' -SkipBuild -OutputName 'MiniPC-Connect-Company-Reviewed-v2.zip'
py -3 '.\company\check_package.py' '.\releases\MiniPC-Connect-Company-Reviewed-v2.zip'
Get-FileHash -LiteralPath '.\releases\MiniPC-Connect-Company-Reviewed-v2.zip' -Algorithm SHA256
```

`-SkipBuild` intentionally packages the already tested/signed helper. Omitting it rebuilds first and would replace a previous signature. The packager refuses to overwrite an existing release; choose a new name. It creates `<archive>.zip.sha256` beside the ZIP. ZIP timestamps can differ between builds; compare MANIFEST payload hashes for content identity rather than expecting byte-identical ZIP hashes.

Transfer the newly approved release to Linux, verify its manifest, and run `publish` from that release to publish its helper. For server source changes, follow the explicit deployment/rollback plan in `04-OPERATIONS.md`; publish alone is not a server updater. Keep secrets/site worksheets outside the source release before repackaging. Do not create a ZIP by blindly archiving the working directory: it can contain test environments, site settings and private state.

## Provenance and intentionally omitted files

This package carries the central-portal implementation and home-tested native binary, not a Git history or forensic backup. The earlier home-only provisioning/acceptance runners referenced private SSH aliases, absolute host paths and temporary credentials; they are deliberately omitted. Source-level checks, fresh-site CLI and company acceptance procedure are included instead. No Codex account, plugin installation, model weights or personal conversation history is needed to interpret the package.

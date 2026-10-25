# Operation, recovery and security administration

This runbook operates only the approved new MiniPC Connect site. It does not authorize changes to the existing model runtime, Hermes, another gateway, old profiles or unrelated caches.

## State that must be preserved

| Path relative to installation destination | Meaning / handling |
|---|---|
| `installation.json` | Restricted site settings and certificate source paths; not a public download |
| `compose.json`, `litellm.config.json`, `Caddyfile` | Generated service/runtime configuration |
| `secrets/database.env` | PostgreSQL credential; root only |
| `secrets/proxy.env` | LiteLLM master key, salt and DB URL; never print/publish |
| `secrets/portal.env` | Fernet key needed to recover encrypted portal state |
| `secrets/owner-invitation.json` | Temporary private first-owner invitation until activated |
| `secrets/owner-activated` | Marker preventing owner bootstrap from being repeated |
| `secrets/tls/` | Company TLS key/cert/root in company mode; private key stays on Linux |
| `data/postgres/` | LiteLLM accounts, keys, DB model route and usage metadata |
| `data/portal/state.sqlite` | Encrypted pending pairing and device/recovery records; preserve key with DB |
| `data/caddy/`, `data/caddy-config/` | Caddy state, including private test CA when internal mode is used |
| `portal-service/` | Deployed Python sources and `config.json` |
| `connect-public/` | Only static portal, public site client ZIP and checksum; never put secrets here |

The publisher includes only public per-site files. The release ZIP is not a server backup. Do not call encrypted journals or CA state “temporary junk” and delete them. The service has its own pairing expiration/cleanup logic; filesystem cleanup is a different operation.

## Health checks and diagnosis

From the extracted, verified source release:

```sh
sudo python3 company/setup.py status --dest /srv/minipc-connect
sudo docker compose -f /srv/minipc-connect/compose.json ps
sudo docker compose -f /srv/minipc-connect/compose.json logs --tail 60 portal
```

Inspect logs locally; redact tokens, credentials, invitations, project content and private file paths before sharing. The service intentionally sanitizes some errors. A generic error may require authorized inspection of the relevant server log, not disabling validation. Avoid dumping the complete DB, env files or expanded Compose configuration into a ticket. Do not use `docker compose down -v` or `docker system prune` as troubleshooting.

Public `/connect/api/info` should return the site's `SiteId`, `BaseUrl`, `Model`, `ContextTokens`, `OutputTokens` and `ManagedModels`; it is not evidence of working inference. Test verified HTTPS using the approved root/OS trust, not an insecure request flag. Default loopback gateway readiness is `/health/readiness` on port 18400; use the configured port, not an assumed one if changed.

| Symptom | Inspect first | Do not do |
|---|---|---|
| Address/port unavailable during init | `ss -ltn`, chosen bind, approved alternative port | Kill the model or another service |
| Container cannot read bind mounts | Exact owner/mode, UID 70 for DB and 1000 for portal/Caddy, distro security policy | `chmod -R 777` or disable SELinux/AppArmor globally |
| Gateway startup/readiness failure | New project's DB health, resource limits, image availability, pinned API compatibility | Reinitialize/delete database blindly |
| Fresh owner activation fails | Private invitation state, user ID/email, gateway status, installed LiteLLM API behavior | Print invitation/token or create duplicate owners |
| Portal login 401/403 | Activated gateway account, correct password, allowed role | Use email-provider password/master key on laptop |
| Public model discovery fails | Supplied URL from Linux, `/v1/models`, API credential, runtime TLS trust | Scan the LAN or add a public provider |
| Model route saved but tools fail | Actual selected model, streaming/tool-call format, chat template and configured context | Treat `supports_function_calling` metadata as proof |
| 429 or long latency | Per-key limits, global 5 admission cap, real backend slots/KV cache, other consumers | Promise concurrency based on an HTTP connection count |
| Download/hash failure | Exact pinned version, official redirect path, proxy/allowlist/signature policy | Disable hash checks or silently substitute latest |
| Final helper acknowledgement interrupted | Same Windows user/site root, `private/pairing.json`, server receipt age | Delete checkpoints or issue a new unrelated identity |

The current helper clears inherited cloud/provider credentials and generic proxy settings for harness sessions. Corporate proxy/TLS-inspection support is therefore a **staging check**, not assumed. Downloads still need the relevant Windows/system network path. Custom mirrors and fully offline installs are not built in; any addition must preserve exact artifact verification.

## Key and account operations

- Each browser account owns its own devices. A normal user can revoke their device in the portal; admin policy/incident response uses LiteLLM identity/key management. A key must be revoked explicitly when a laptop is lost or the user leaves.
- New keys last 30 days. Manual same-device renewal is supported, not automatic scheduled fleet rotation. New keys are tested before old ones are revoked. If cleanup was interrupted, re-login as the same owner and refresh the device list to allow deferred old-key cleanup.
- If a pending key cannot be cleaned because the original session expired, the admin must reconcile the user's exact key aliases/hashes in LiteLLM. Do not bulk-delete unrelated user keys. Treat unresolved cleanup as an incident/task, not successful rotation.
- Test revocation by checking both old credentials are refused (expected 401), then verify another user's credential still works. Do this through a private test harness; never print a decrypted key to obtain evidence.
- Changing `site_id`, origin or Windows account creates an identity/configuration migration. It is not an ordinary key renewal. Plan client re-enrollment and old-key cleanup; do not edit only `pilot.json` and claim the fleet migrated.
- Losing the portal Fernet key prevents recovery of encrypted records. Losing Windows DPAPI access prevents use of that laptop's saved keys. Neither is solved by copying plaintext secrets to the public site.

## Backups and restoration

Choose a company-approved **encrypted** backup location and owner before production. A directory named `backups` is not encryption. Include installation config, all secrets, DB files, portal state, Caddy state and the exact source release/checksum. Keep backups off public web paths and outside the working source bundle.

A simple consistent filesystem backup requires an approved maintenance window:

1. Notify users; confirm the absolute installation path and Compose project name.
2. Stop **only this project's** generated services. This interrupts gateway users but must not stop the existing separately managed model:

```sh
sudo docker compose -f /srv/minipc-connect/compose.json stop
```

3. Snapshot/archive the full installation directory to the already-provisioned encrypted destination, preserving numeric ownership, modes and any relevant ACLs/xattrs. No copy command is prefilled because the approved encryption destination/backup system is site-specific. Do not copy a running Postgres data directory and call it a consistent backup.
4. Restart the same existing deployment, without invoking `init`:

```sh
sudo docker compose -f /srv/minipc-connect/compose.json start
sudo docker compose -f /srv/minipc-connect/compose.json ps
```

5. Verify health and a bounded disposable request. Record backup time/hash/location privately and test restore into an isolated, non-conflicting staging environment.

Restore configuration, secrets, databases and certificate identity as a consistent set. Avoid two live copies of the same site identity using duplicated keys. Encrypted backup/restore and restore drills are operational procedures to be validated by IT; v2 does not provide a one-click backup daemon or HA cluster.

## Updates, certificates and rollback

- Do not run `init` over a live directory. It intentionally refuses overwriting it.
- Preserve old source release and consistent state snapshot before an approved update. Validate/test new source offline, then replace only this site's deployed files. Restart only components actually changed.
- `publish` rebuilds the public **client** archive from the currently executing release. It does not deploy changed Python or frontend sources. Match server and helper versions deliberately.
- Rebuilding/signing a helper changes its bytes; publish a new client ZIP/checksum. SHA-256 is not Authenticode. Let IT sign/allowlist the exact tested binary; do not disable Windows controls.
- Leaf certificate renewal with the same trusted CA still needs chain/hostname verification. A new root requires explicit trust distribution and fresh public client configuration; never swap a root silently.
- Roll back application/config and any matching DB/schema changes together. This release provides no general database migration/downgrade engine. If a future dependency upgrade migrates data, restoring only the old executable may be unsafe.
- For permanent removal, revoke keys and back up first. Stop the exact project and agree a separate inventory-based removal plan; no automatic deletion of model data, user projects or certificate trust is included.

## Production boundaries

This is a single-host staging design, not externally audited security software, a public Internet service or guaranteed multi-tenant sandbox. Organisational SSO, password reset/email delivery, automatic key renewal, full audit retention, quotas per department, HA, automatic resource scheduling and air-gapped artifact mirroring are not supplied. Do not label any of these complete based on the presence of a UI link or an upstream Enterprise feature.

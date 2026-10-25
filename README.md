# MiniPC Connect v2 — Linux server, Windows clients

For the complete company handoff, start with [00-START-HERE-FA.md](00-START-HERE-FA.md) and [CODEX-HANDOFF.md](CODEX-HANDOFF.md). The numbered `handoff/` guides define exact inputs, installation, Windows onboarding, operations, tests, source/build paths and remaining acceptance gates. This overview is not a substitute for that ordered runbook.

This is a portable, self-hosted deployment, not a model installer. It uses a central browser portal, LiteLLM identity and per-device API keys, Caddy HTTPS and a small Windows helper. Inference remains on the Linux MiniPC; harnesses execute tools on their Windows laptop with manual permissions. Project text needed for inference is sent to the MiniPC. No automatic cloud fallback.

## Acceptance boundaries

Read ACCEPTANCE.md for exact passed checks and remaining staging gates.

See the accompanying release evidence for checks actually run. A second physical Windows laptop, the company's different model, corporate PKI, software signing, firewall policy and performance under that workload require on-site acceptance. A successful model listing does not prove tool calling or capacity. Claude Code with a non-Claude model is an experimental compatibility route, not a claim of Anthropic support. Do not treat this as a production security certification.

## Requirements

- Linux x86_64 MiniPC; Python 3.10+ and an IT-approved Docker Engine with Compose V2 already installed. The setup does not install Docker or change the model runtime.
- Existing local OpenAI-compatible model endpoint. Supply its exact URL/port and optional API key in the portal. It must support chat/completions and tool calls for these harnesses. No network scanning.
- A fixed LAN IPv4 or internal DNS name; an explicit list of permitted client CIDRs; an approved HTTPS port (default example 9443). Same subnet makes routing simpler but does not override the firewall or VLAN policy.
- Company-issued TLS certificate/key and its public root, recommended. An isolated internal Caddy CA is available for home testing. Private CA keys never go to laptops. IT distributes/trusts the public root; never disable TLS validation.
- Windows 10/11 x64. IT must permit the helper and selected harness. First-time artifact downloads use official GitHub / downloads.claude.ai endpoints; no opaque remote install scripts. Project SDKs and compiler tools are separate prerequisites.

## Administrator installation on the Linux MiniPC

Transfer this ZIP through an approved channel. Verify the outer SHA-256 against the sender's trusted checksum, extract it into a directory accessible only to the administrator, then verify contents:

```sh
sha256sum -c MANIFEST.sha256
python3 company/setup.py wizard --settings settings.json
sudo python3 company/setup.py init --settings settings.json --dest /srv/minipc-connect
sudo python3 company/setup.py start --dest /srv/minipc-connect
sudo python3 company/setup.py activate-owner --dest /srv/minipc-connect
```

The wizard asks for your own site ID, name, HTTPS origin, LAN bind address, permitted CIDRs, administrator email, context/output limits and TLS mode. There is no home IP, home account, home private certificate or pre-issued API key in this package. `init` refuses an existing destination and busy ports; it never stops other services. Adjust the three internal ports in settings.json before initialization if occupied.

`start` pulls pinned service images if absent and starts only this Compose project. The first run can take several minutes for downloads/database initialization. `activate-owner` asks for a private gateway password in the terminal without displaying it; this is not the email provider password. It claims a LiteLLM invitation. No password is placed in shell arguments, a shared ZIP or the helper. Existing deployments must use their own account recovery process; do not rerun initialization over them.

Open `https://YOUR-MINIPC:PORT/connect/` after the certificate is trusted. Sign in with the email/password just created. In **central model settings**, enter the exact local API URL, optional upstream key, discover models and explicitly select one. The API alias stays `local-coder`; laptops do not need the original model ID. This changes only this site's LiteLLM model route, not the model process. Changing context limits also requires regenerating the public helper configuration; do not guess a context larger than the runtime can serve.

Use the linked LiteLLM account panel for user invitations. Give each person a separate internal-user account, not the owner account. Their password is set through the invitation. Use the browser portal for device approval and own-device revocation. Enterprise SSO is not required or included.

## Each Windows user

1. Open the central HTTPS portal; sign in with their gateway account.
2. Download the helper ZIP, select **Extract all**, run `MiniPCConnect.exe`. Keep the public config and root certificate beside it.
3. The helper opens the portal with a public ten-character device code. If it opens another browser, copy only that public code into the already signed-in portal. Never approve an unknown device.
4. Select OpenCode, Claude Code or both; approve that device. Keys are issued separately, inference-only, currently 30 days, one parallel request per key, 30 RPM and 60,000 TPM. Shared runtime capacity may still queue or reject requests.
5. The helper verifies artifact hashes, encrypts keys with Windows CurrentUser DPAPI, creates isolated profiles and runs a bounded real file-read check. Only then does the portal say Ready.
6. Start the chosen harness from **Start > MiniPC Connect - SITE** and choose a project folder. Existing global harness settings and other sites' profiles are not overwritten. V2 uses its own `%LOCALAPPDATA%\MiniPCConnect\SITE-portal-v2` directory, so earlier GUI-only profiles remain separate and unchanged.

For renewal, run the same helper again on that device and explicitly approve. Failed verification restores prior credentials. Successful replacement revokes old keys. If the network is lost at the final confirmation, recovery state is retained; run the helper again rather than deleting private state. Recovery receipts remain available server-side for seven days. After that, ask the administrator to reconcile device keys before creating another enrollment.

Closing the browser does not cancel an already approved helper; the helper continues with its private token. Signing out explicitly cancels unfinished approvals from that session. Disabling a user's key in LiteLLM blocks that credential. Portal-owned device records do not import pre-existing legacy installations automatically.

## Operation, backup and rollback

```sh
sudo python3 company/setup.py status --dest /srv/minipc-connect
sudo docker compose -f /srv/minipc-connect/compose.json logs --tail 50 portal
```

Do not paste secrets or raw model logs into tickets. Access logs are disabled for the pairing API, passwords are never logged by the portal, and shared downloads contain only public config/CA. Pairing credentials awaiting installation/cleanup are encrypted in SQLite; its encryption key is in root-owned `secrets/portal.env`. Preserve that key with its database for recovery. LiteLLM owns identity and inference-key records in Postgres.

Back up the installation configuration, secrets, Caddy CA/certificates and Postgres with company-approved encrypted backup controls. For a simple consistent backup, stop only this Compose project during a planned maintenance window, snapshot its installation directory, then start it again. Never delete or clean up an existing model, Hermes, unrelated cache or another project's data. A filesystem copy of a running Postgres data directory is not a valid consistent backup.

Updates are explicit: keep a snapshot and the previous release, rebuild/test the helper, validate service config, then replace only this project's source/public files. Do not run `init` over a live directory. Roll back code/config and any matching database migration together. This release adds its own new portal database, not a migration of an older application's user database. For service shutdown use `docker compose -f /srv/minipc-connect/compose.json stop`; do not use `down -v` when preserving state.

The included source lives in `server/`, `company/`, `portal/` and `source/windows/`. Rebuild the native helper on Windows with `windows/build-helper.ps1`. The helper is unsigned unless IT signs it; a SHA-256 checksum is not a publisher signature. After approval, run `publish` on Linux to produce the per-site download ZIP and checksum. Do not publish administrator configuration or `secrets/` as web content.

## Company handoff checklist

- Review the pinned dependencies, their applicable licenses and the chosen model's separate commercial-use terms. Do not assume all models or paid LiteLLM Enterprise features are included.
- Approve LAN access, DNS/address reservation, certificate lifecycle, helper signing and official artifact download access.
- Test each chosen harness with the actual company model: valid tool calls, file-read correctness, time to first response and realistic context size.
- Test one additional physical laptop, account separation, key revocation, renewal, restart recovery, and 4–5 simultaneous users. Shared model slots are hardware/runtime capacity, not a gateway promise.
- Choose an owner for backup, credential expiry, dependency/security updates and incident response before production use.

# Linux administrator runbook

All commands below run from the **extracted release root** unless a working directory is explicitly stated. The example installation directory is `/srv/minipc-connect`; use the same approved destination consistently. Examples are not permission to connect to an unknown host.

## 1. Integrity, access and prerequisites

On the Windows receiving laptop, compare the ZIP hash with the trusted sender's handoff before executing any code:

```powershell
Get-FileHash -LiteralPath '.\MiniPC-Connect-Company-Handoff-v2-20261025.zip' -Algorithm SHA256
```

Use Explorer **Extract All** into a new folder. Do not run directly inside Explorer's ZIP preview. On Linux, use an approved file-transfer channel (for example authorized `scp`) and extract into a new release directory, separate from installation state. Then:

```sh
sha256sum --check --strict MANIFEST.sha256
python3 --version
uname -m
docker compose version
```

Required: Linux `x86_64`, Python >=3.10, authorized root/sudo, Docker Engine and Compose V2 already approved/installed. Do not substitute Docker Desktop licensing assumptions for Linux Engine policy. Do not install Docker through a remote `curl | sh` script. If Python/Docker/Compose is missing, stop for IT provisioning.

Bounded read-only preflight on the target:

```sh
ip -brief address
ss -ltn
free -h
df -h /srv
sudo docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}'
sudo docker info --format '{{.ServerVersion}}'
```

Record only the relevant existing model service/container/PID; do not dump process environments, unrestricted `docker inspect`, credentials or model prompts. Confirm which other programs use the model. The four generated services have memory ceilings totalling about 3 GiB, in addition to the model and OS; this is not a measured minimum. Establish actual headroom before starting them.

The installer checks chosen bind/ports before creating state. Busy ports or an existing destination are stop conditions. Resolve a different **approved** internal port/destination; never kill another listener or delete a deployment to satisfy setup.

## 2. Resolve site inputs

Complete a private working copy of `handoff/SITE-INPUTS.example.json`. It is an intake worksheet only. The public HTTPS origin must be reachable from every client and covered by the TLS certificate. Use a fixed address/DHCP reservation or approved internal DNS. Same subnet does not override host firewall, VLAN ACLs or company policy.

Current layout:

| Purpose | Default/example | Exposure |
|---|---|---|
| Client HTTPS | explicit MiniPC LAN IPv4, TCP 9443 | Only approved client CIDRs |
| PostgreSQL | 127.0.0.1:15432 | Host loopback only |
| LiteLLM | 127.0.0.1:18400 | Host loopback only |
| Portal service | 127.0.0.1:18401 | Host loopback only |
| Existing model | Explicit existing URL/port | Not created/changed by this release |

Internal ports must be distinct integers 1024–65535 and must not equal HTTPS port. Use an approved unprivileged HTTPS port such as 9443 for these non-root containers; do not assume port 443 can bind on this host. IPv4 is the supported deployment scope. Do not use `0.0.0.0/0`, wildcard bind, public Internet exposure, port forwarding or an unapproved tunnel.

## 3. Generate actual settings

```sh
python3 company/setup.py wizard --settings site-settings.json
```

The wizard asks site ID/display name, Linux bind IPv4, public HTTPS origin, permitted CIDRs, owner email, per-request context/output and TLS mode. It writes a new file and refuses to overwrite an existing one. Site IDs use lowercase letters, digits and hyphens, length 1–49. Context is 4096–131072; output is at least 128 and at most one quarter of context. Pick values supported by the running server, not model marketing limits.

The exact generated settings schema looks like this **illustrative, not deployable company configuration**:

```json
{
  "site": {
    "site_id": "company-pilot",
    "name": "Company MiniPC",
    "origin": "https://minipc.company.example:9443",
    "bind": "10.20.30.40",
    "networks": ["10.20.30.0/24"],
    "email": "administrator@example.invalid",
    "context": 8192,
    "output": 1024
  },
  "ports": {"database": 15432, "gateway": 18400, "portal": 18401},
  "tls": "company",
  "tls_files": {
    "server.crt": "/approved/tls/server.crt",
    "server.key": "/approved/tls/server.key",
    "root.crt": "/approved/tls/root.crt"
  }
}
```

Do not copy example addresses/email into the actual deployment. Use `tls: "internal"` without `tls_files` only for an explicitly approved private-CA pilot. `site-settings.json` contains certificate **paths**, not certificate keys or API passwords; nonetheless treat it as restricted site configuration, not a web download.

### Company TLS prerequisites

- `server.crt`: PEM leaf certificate with needed intermediate chain, valid SAN for the chosen origin hostname/IP.
- `server.key`: matching unencrypted PEM private key accessible only through the approved server provisioning process; never send it to a laptop or chat.
- `root.crt`: exactly **one** public PEM root CA certificate, not a chain bundle and not a private key. It is included in public client downloads. Have IT verify this is the intended root.
- Check validity dates, matching key/certificate, chain and renewal ownership before initialization. File presence alone does not validate the complete PKI deployment.
- IT distributes the public root via approved enterprise policy, or explicitly approves CurrentUser installation. No `curl -k`, insecure browser exception or global trust bypass.
- Caddy can issue the test certificate in `internal` mode. Its CA private key remains on MiniPC; publish only the public root through a trusted onboarding channel before users trust HTTPS.

## 4. Initialize a new site (authorized write)

```sh
sudo python3 company/setup.py init --settings site-settings.json --dest /srv/minipc-connect
```

This creates a fresh deployment with Compose project name `minipc-<site_id>`, new secrets, empty identity/model database state and copied portal sources. It does not start or modify the existing model. It refuses a pre-existing destination, symlink destination or conflicting ports. If interrupted after creating a directory, do not blindly rerun/remove it: inspect this new site's partial state and agree recovery with the admin.

Validate the generated configurations without printing expanded secrets:

```sh
sudo docker compose -f /srv/minipc-connect/compose.json config --quiet
```

Validate with the pinned Caddy image and mounts already selected by the generated Compose file. This starts only a short-lived config-validation container, not the gateway/model:

```sh
sudo docker compose -f /srv/minipc-connect/compose.json run --rm --no-deps --entrypoint caddy https adapt --config /etc/caddy/Caddyfile --adapter caddyfile --validate > /dev/null
```

Do not use a different latest image just for validation. A full `docker compose config` dump may reveal env-file values; prefer `--quiet`.

## 5. Start and activate the first owner

```sh
sudo python3 company/setup.py start --dest /srv/minipc-connect
sudo python3 company/setup.py status --dest /srv/minipc-connect
sudo python3 company/setup.py activate-owner --dest /srv/minipc-connect
```

`start` pulls missing pinned images, starts only this Compose project, waits for gateway readiness, creates the owner invitation and publishes the client ZIP. Downloads/database initialization may take several minutes. `activate-owner` requires an interactive private terminal; the user chooses and repeats a gateway password of at least 12 characters. It is **not** their email-provider password. Do not pipe the password through Codex messages or shell arguments.

The owner is `minipc-<site_id>-owner` with the configured email and `proxy_admin` role. Its pending invitation is protected in `secrets/owner-invitation.json`; successful activation replaces it with `secrets/owner-activated`. Do not print the invitation or recreate a live owner to recover a forgotten password.

**Unverified gate:** full startup + first-owner activation on a completely new four-service stack was not run end-to-end at home. Generated initialization/configuration/publication and live account flows on the existing home stack were tested separately. Record the fresh company result honestly.

## 6. Publish trust and reach the portal

`start`/`publish` prints the portal URL and public root DER SHA-256 fingerprint. Deliver the root and fingerprint through an already-trusted channel (IT management, approved file transfer, in-person verification). A root downloaded over an untrusted connection is not its own proof of authenticity.

After IT trust installation, browse `https://APPROVED-HOST:PORT/connect/`. Sign in using the configured owner email and the private gateway password. Verify the exact host/certificate and that clients outside the approved scope are refused. Do not publish internal loopback ports to make it work.

## 7. Discover and select the existing model

In the portal's administrator section **تنظیم مدل مرکزی**:

1. Enter the exact existing **OpenAI-compatible API base URL as seen from Linux MiniPC**, not the browser URL or Windows loopback. `http://127.0.0.1:<existing-port>/v1` is valid for a host-local runtime. If upstream requires a key, the admin enters it privately in the password field.
2. Click **پیداکردن مدل‌های این سرویس**. Discovery sends only `GET .../v1/models` to the supplied local/private endpoint; it does not scan the network, start/download a model or perform inference. Bare host bases get `/v1` appended. Do not enter the `/models` resource itself.
3. Choose an exact returned model ID and click **ثبت مدل برای این سایت**. This creates/updates the DB-managed route `minipc-<site_id>-model`, alias `local-coder`.
4. Test chat streaming AND tool calling with a disposable project. The company model must support the OpenAI-compatible chat/completions/tool semantics; listing its name is insufficient. Claude Code additionally depends on gateway protocol translation and its own separate smoke test.

Discovery rejects public/link-local/multicast/unspecified endpoints, embedded credentials, redirects and proxy routing. An upstream private HTTPS service must be trusted by **both portal and gateway runtimes**; custom upstream CA injection is not automated by this wizard. Resolve it with IT rather than bypassing TLS. If only a vendor-specific API exists, report a compatibility prerequisite instead of pretending discovery can adapt it.

Context/output metadata are shared between server public config, model route and helper manifest. Do not change only a laptop field or only one JSON. After a later approved limits change, update these consistently, publish fresh client configuration and verify/re-enroll affected profiles; there is no automatic fleet-wide context migration in v2.

## 8. Create normal user accounts

Use the portal link **حساب و دعوت‌نامه** / **مدیریت کاربران و دعوت‌نامه‌ها**, which opens LiteLLM `/ui/`. Manage users there with the owner account. Each user needs their own email and `internal_user` role, not `proxy_admin`, an invitation and a privately chosen gateway password. Ordinary user enrollment does not create arbitrary public accounts and does not require Enterprise SSO. Email delivery is not configured by this bundle; securely deliver the invitation using your approved internal process.

UI labels depend on the pinned LiteLLM build. If the screen is unclear, use these verified upstream API contracts as the inspection reference; do not guess a form submission or expose bearer tokens:

| Operation | Contract used by the home implementation |
|---|---|
| Create user | `POST /user/new`: `user_id`, `user_email`, `user_role: internal_user`, `auto_create_key: false`, `models: [local-coder]`; optional per-user limits |
| Create invitation | `POST /invitation/new`: `user_id`, under an authorized admin context; home used an admin-owned short-lived key limited to this route |
| Begin claim | `GET /onboarding/get_token?invite_link=<private invitation id>` |
| Claim | `POST /onboarding/claim_token`: `invitation_link`, `user_id`, `password`, using the returned onboarding key |
| Login | `POST /v2/login`: `username` (email), `password`; portal wraps this as `/connect/api/login` |

The shipped `setup.py` implements this workflow only for the first owner. It is not a general user-management CLI. Protect invitation links like credentials; do not paste request/response bodies into logs. Do not mint permanent master/admin keys for normal laptops.

## 9. Client download and end of staging

Open `/connect/` on the first authorized Windows laptop and follow `03-WINDOWS-USERS.md`. The per-site download `MiniPCConnect-Windows-x64.zip` contains exactly `MiniPCConnect.exe`, `pilot.json`, `site-root.crt`, `START-HERE.txt`. It contains no pre-issued user key.

After rebuilding/signing the helper, publish from the verified release root containing that exact helper:

```sh
sudo python3 company/setup.py publish --dest /srv/minipc-connect
```

`publish` does not automatically install modified Python/JS server code into a live site. It creates the public client ZIP/config/root and SHA256SUMS using the release currently executing it. Keep release and state paths distinct. Proceed through `05-VALIDATION.md` before general rollout.

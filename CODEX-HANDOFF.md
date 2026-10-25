# Receiving Codex: implementation and deployment contract

Release: MiniPC Connect v2, company handoff, 2026-10-25.

## Objective and scope

Deploy the included system to an authorized Linux x86_64 MiniPC, then onboard Windows 10/11 x64 laptops through a central HTTPS portal. Reuse the company's existing local model service. This is a portable source/build handoff, not a backup of the home installation and not an air-gapped installer. Do not recreate the original game-building project: that earlier project is unrelated to this gateway deliverable.

The supplied implementation is the baseline. Do not redesign it, replace the model, add a paid provider, enable cloud fallback, or silently upgrade pinned components. Any new implementation change needs a specific demonstrated need and an explicitly scoped test. Deployment authorization does not authorize unrelated filesystem cleanup or service restarts.

## Read first, in this order

1. [Persian start guide](00-START-HERE-FA.md), [README](README.md), [original acceptance record](ACCEPTANCE.md).
2. [Architecture](handoff/01-ARCHITECTURE.md) and [site input checklist](handoff/SITE-INPUTS.example.json).
3. [Linux runbook](handoff/02-LINUX-INSTALL.md), [Windows runbook](handoff/03-WINDOWS-USERS.md).
4. [Operations](handoff/04-OPERATIONS.md), [validation](handoff/05-VALIDATION.md).
5. [Source/build map](handoff/06-SOURCE-MAP.md), [dependency/license boundaries](handoff/07-DEPENDENCIES-LICENSES.md).

Verify MANIFEST.sha256 before executing included code. Read the actual setup/render/discovery and helper sources before privileged installation. No original chat history, Codex plugins, personal skills, home SSH aliases or home credentials are required. Use tools available in the receiving environment; never invent an unavailable tool or claim a check that was not run.

## Inputs you must not infer

The file `handoff/SITE-INPUTS.example.json` is a checklist, NOT a `setup.py --settings` file. Copy it outside the read-only release as a site worksheet. Resolve every relevant null with the user/IT. Use the wizard to generate actual settings. The exact schema is in the Linux runbook.

Ask only for missing non-secret facts: approved SSH identity/host, Linux architecture, installed Docker/Compose, model URL/runtime/ID/context/slots, approved hostname/IP/port/CIDRs, owner email, TLS mode and certificate locations, outbound access, signing policy and chosen harnesses. Have the user enter credentials privately in the terminal/browser. Do not ask them to paste passwords or keys into chat, source, shell arguments or reports.

## Execution gates

1. **Intake / no writes to server:** verify archive; inventory only authorized paths/ports/services; record existing model PID/service/container identity without exposing its environment or command-line secrets. Check free resources. Summarize resolved inputs and blockers.
2. **Staging approval:** identify exact new installation directory, Compose project name, public bind/CIDRs, internal ports and cert plan. Obtain authorization for these mutations and any Windows trust change. Do not bypass IT policy because approval is inconvenient.
3. **Fresh initialization:** run the documented CLI. Keep source bundle separate from installation state. Existing destination is a stop condition, not permission to remove it. No port stealing, no `docker system prune`, no model restart.
4. **Fresh-stack gate:** start the four generated services; activate the owner through private terminal input; verify TLS and intended LAN scope. This full fresh-stack/owner sequence was not exercised end-to-end on a second home stack. Diagnose failures within this new site; never present home tests as proof.
5. **Model route gate:** administrator discovers the explicitly supplied local endpoint and chooses an actual returned model. The route alias must remain `local-coder`. Listing/saving does not prove tools work. Test the company's model before inviting users.
6. **One Windows client:** use the site-specific ZIP from `/connect/`; no global client settings changes. Start with OpenCode. Enable Claude Code only after licensing/policy approval and a separate compatibility result. Preserve manual tool permissions.
7. **Lifecycle:** verify successful re-enrollment/rotation, old-key rejection, same-owner recovery, own-device revocation and no access to another account's devices. Use disposable accounts/projects, not real private work.
8. **Second physical laptop, then 4–5 users:** measure genuine overlapping inference, first-token latency, total time and resource use; include competing consumers of the model. Admission limits are not proof of parallel inference. Report actual results; do not increase context or slots blindly.
9. **Handoff:** complete a working copy of `handoff/DEPLOYMENT-REPORT.template.md`; include sanitized evidence, exact versions/addresses, backup/restore ownership and remaining failures. Mark production ready only after company acceptance and security/licensing review.

## Non-negotiable boundaries

- Model weights stay on MiniPC; prompts and selected project content travel to MiniPC over HTTPS. Tools, shell/file operations and project builds run on the user's laptop. This is not a sandbox for untrusted users or code.
- No TLS bypass (`-k`, `verify=False`, `NODE_TLS_REJECT_UNAUTHORIZED=0`), no globally disabled permissions/antivirus, no hidden paid route and no borrowed home master key.
- Public downloads contain only the helper, public config, public root certificate and instructions. Never publish `installation.json`, `secrets/`, model keys, invitation links, pairing tokens, DPAPI files or databases.
- LiteLLM owns identities, account roles and inference keys. The portal does not receive the master key and does not implement a parallel password database.
- One portal worker is intentional; in-memory locks/rate limits and the encrypted SQLite workflow are not a multi-worker/HA design. Do not scale workers without redesign and tests.
- Corporate addresses, certs, model limits and license rights are not derivable from the home pilot. A `null` or a placeholder means stop and resolve it, not assume.
- No automatic company deployment has occurred. No source artifact authorizes touching an unspecified host.

## Evidence and reporting discipline

`ACCEPTANCE.md` and `handoff/HOME-ACCEPTANCE.json` are historical home results, not fresh company evidence. `MANIFEST.sha256` covers file integrity, not publisher authenticity. The native helper is unsigned unless IT signs it. Full-stack staging, second laptop and company model capacity remain open gates.

Keep status updates short; run focused offline checks before real inference. Stop repeated tests when the same external prerequisite is missing. Record exact sanitized error/status/phase and the next required decision. Do not turn this handoff into an unbounded architecture/security audit.

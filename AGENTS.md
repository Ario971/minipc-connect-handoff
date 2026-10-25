# MiniPC Connect: receiving-agent entry point

This private repository contains the expanded, verified company-handoff package.
Do not start a new implementation from scratch. A GitHub link is enough to locate
the source, but private-repository authentication and authorized Linux access are
still required. Do not interpret this file as permission to access an unspecified
host or perform privileged deployment without the user's approval.

## Required reading order

1. `00-START-HERE-FA.md` and `CODEX-HANDOFF.md`.
2. `ACCEPTANCE.md` and `handoff/HOME-ACCEPTANCE.json` for actual tested scope.
3. `handoff/01-ARCHITECTURE.md`, `handoff/02-LINUX-INSTALL.md` and
   `handoff/SITE-INPUTS.example.json`.
4. `handoff/03-WINDOWS-USERS.md`, `handoff/04-OPERATIONS.md`,
   `handoff/05-VALIDATION.md`, `handoff/06-SOURCE-MAP.md` and
   `handoff/07-DEPENDENCIES-LICENSES.md`.

Verify the payload files against `MANIFEST.sha256`. The 48 original release files,
including that manifest, are unchanged. This AGENTS.md, .gitignore and
.gitattributes are additional repository onboarding/hygiene files; they are not
part of the original ZIP manifest. Git attributes preserve exact payload bytes
across Windows and Linux checkouts. The original ZIP remains in release
`handoff-v2-20261025`, SHA-256:

`1dcf208816202a949405f88abe874ca19421b0db94c83ef6071efa60971c3776`

## First actions when the user asks to install

Read before running setup. Inventory missing non-secret site inputs and perform
only authorized read-only preflight. Ask only for unresolved facts such as Linux
SSH/sudo access, model API endpoint, actual context/slots, approved LAN scope,
TLS certificate policy and owner email. Never ask for passwords or keys in chat.
Keep the existing model and unrelated services unchanged. Use a fresh staging
destination and the included installer only after authorization.

No cloud/paid fallback, TLS bypass, global permission bypass or destructive cleanup.
The model stays on Linux; local tools execute on each Windows laptop. Do not mark
company production ready from historical home tests. Fresh-stack bootstrap,
company model/tool compatibility, a second physical laptop and actual 4-5-user
capacity remain company acceptance gates. Record progress and sanitized evidence
in a working copy of `handoff/DEPLOYMENT-REPORT.template.md`, outside this release.

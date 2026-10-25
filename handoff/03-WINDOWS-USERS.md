# Windows laptop onboarding and daily use

## What every laptop needs

- Windows 10/11 x64 and a working .NET Framework v4 runtime; supported corporate Windows builds normally provide this, but verify policy/version first.
- A normal gateway account/invitation, the approved portal HTTPS address, a trusted public root certificate and LAN reachability to that address/port.
- Permission to run MiniPC Connect and the selected pinned Harness. Downloads require approved access to the official publishers and their download redirect hosts.
- Enough disk for the native executables and project files; normal SDKs/Git/compilers needed by the user's project are separate prerequisites. If Claude asks for Git Bash, provide an IT-approved installation; the helper does not install Git or project toolchains.
- No local model, GPU, Docker, Python or Node installation is required just to use the supplied native helper/harness binaries. Company Codex is an installation assistant, not a mandatory runtime component on every laptop.

## Establish certificate trust before login

Prefer IT-distributed machine trust. For an explicitly approved per-user pilot only, verify the **public root** and its SHA-256 fingerprint via a trusted channel. In Windows PowerShell, where `$certPath` points to the public root supplied by IT:

```powershell
$certPath = (Resolve-Path -LiteralPath '.\site-root.crt').Path
$cert = [Security.Cryptography.X509Certificates.X509Certificate2]::new($certPath)
$sha = [Security.Cryptography.SHA256]::Create()
try {
    $derSha256 = ([BitConverter]::ToString($sha.ComputeHash($cert.RawData))).Replace('-','').ToLowerInvariant()
    $derSha256
    $cert | Select-Object Subject, Issuer, NotBefore, NotAfter
} finally { $sha.Dispose() }
```

Compare DER SHA-256 to the separately provided fingerprint. `Get-FileHash` of the PEM file is a **different** hash. Confirm the certificate is the intended CA, its validity and permissions. Only after explicit approval:

```powershell
Import-Certificate -FilePath $certPath -CertStoreLocation Cert:\CurrentUser\Root
```

This trusts certificates issued by that CA for the current Windows account, not just one web page. Do not import an unknown root, use LocalMachine without approval, turn off verification, or bypass corporate execution policy/SmartScreen. If IT blocks it, request approved signing/allowlisting.

## First connection: exact browser flow

1. Open the approved `https://HOST:PORT/connect/`. No browser certificate warning should remain.
2. Under **با حساب خودت وارد شو**, enter your **gateway** email/password and click **ورود امن**. This is neither Gmail login nor an Anthropic account. If you have no gateway account, get an invitation from the administrator.
3. Click **دانلود کمک‌نصاب ویندوز**. The adjacent **هش SHA-256** points to the published archive checksum. Verify the download through the trusted HTTPS site/IT release process.
4. In Explorer choose **Extract All**. Keep these together: `MiniPCConnect.exe`, `pilot.json`, `site-root.crt`, `START-HERE.txt`. Run `MiniPCConnect.exe` as your normal Windows user, not Administrator.
5. The helper opens the portal with a ten-character device code. If it opens a different browser, sign in there or copy **only that public code** into the already logged-in page's **کد کمک‌نصاب** field and click **نمایش درخواست اتصال**. Do not approve an unsolicited code/device. Pending codes expire after ten minutes.
6. Select **OpenCode**. Select **Claude Code — سبک و آزمایشی** only if the administrator approved it; the current page initially checks both, so uncheck Claude when it is not approved. Click **تأیید دستگاه و شروع نصب**.
7. Leave the helper running. It downloads/verifies or reuses exact verified executables, obtains distinct scoped keys, creates separate profiles and executes a generated local file-read test. Each selected harness test is bounded to 150 seconds; first-time downloads add time. If the limit fails, record the failure rather than waiting indefinitely.
8. When the portal/helper reports Ready, open Windows **Start > MiniPC Connect - SITE** and choose **Start-opencode** or **Start-claude**. Choose an approved project folder when prompted.

The API key is passed securely to the helper and DPAPI-protected. Users do not need to copy it into a config file or chat. The helper is still necessary: a normal browser cannot silently install native programs or write Windows credentials.

## Daily usage and boundaries

Always use the site's generated Start entry/launcher, not a global `claude` or `opencode` shortcut that might use a different provider/profile. Both harnesses use the same server alias `local-coder` but separate local homes and per-harness keys. Normal tool permissions remain manual. Approve only necessary file/shell actions in the selected project; do not enable a global skip-permissions mode.

Model inference remains on MiniPC. Project tools run on the laptop and selected project content can be sent to MiniPC. The launcher does not guarantee a malicious prompt cannot affect a locally approved tool, nor provide a hard filesystem sandbox. Do not use confidential projects until policy and tests pass.

## Local file layout

```text
%LOCALAPPDATA%\MiniPCConnect\<SiteId>-portal-v2\
  MiniPCConnect.exe, pilot.json, site-root.crt
  Start-opencode.cmd, Start-claude.cmd
  profiles\<harness>\       isolated homes/config/history and protected key
  private\pairing.json      private enrollment/recovery checkpoint
  workspace\               default empty work location
  enroll.lock              exclusive enrollment lock
```

Exact additional staging/backup files are managed by the helper. The `-portal-v2` root is separate from earlier GUI-only installs. Do not copy DPAPI credentials to another Windows account or laptop; re-enroll that laptop instead. Do not rename the root mid-enrollment or delete pending recovery files to force a retry.

## Renewal, sign-out and removal

- Keys expire after 30 days; renewal is **manual in v2**. Run the same site's helper on the same Windows account and approve again. Existing old keys remain until replacements pass verification. Changing to another owner in an existing profile is refused; use a separate approved account/root instead of overwriting someone else's profile.
- Browser refresh may require login again because session is not persistent browser storage. Closing a tab is not cancellation of an already approved installation. **خروج از حساب** cancels unfinished approvals associated with that session; do not sign out while intentionally waiting for enrollment.
- For removal, first log in to `/connect/`, open **دستگاه‌های من**, choose the intended device and confirm revocation. This disables access, not local project deletion or harness uninstallation. Any subsequent removal of profiles/shortcuts requires a separate approved cleanup scope.
- If the network drops during final confirmation, rerun the same helper promptly; completed server receipts remain available seven days. After that, have the admin reconcile existing keys/device records before creating another enrollment.

## Common user errors

| Symptom | Next action |
|---|---|
| Missing `pilot.json` | You ran the administrator-bundle EXE; download the **per-site** client ZIP after server setup |
| 401 on login | Use your own activated gateway account/password, not Google password; ask admin about invitation/role/reset |
| HTTPS warning | Stop; verify host, time, chain and approved root; never bypass |
| Download blocked/hash mismatch | Stop; check approved publisher access/version; do not remove hash verification |
| Code expired | Let current helper report its state; restart enrollment as documented rather than approving a different device |
| Existing enrollment is busy | One helper per site/root at a time; do not delete a live lock or kill unrelated processes |
| Test fails/150-second limit | Capture the harness/phase/error and ask admin to check model tools, context, resource load and network |
| Later 401/429 | Check expiry/revocation or per-key/global capacity; do not switch to a cloud account |

Use a new disposable project for initial tests. A response to “hi” alone does not validate a coding harness's tool interface.

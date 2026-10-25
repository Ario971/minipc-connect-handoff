# Verification commands and staged acceptance

Use a working copy of the extracted release. Keep the original archive and MANIFEST unchanged. These tests do not grant permission to modify the existing model or load private company projects.

## 1. Archive and offline Python checks

Linux standard-library checks, no model/network required:

```sh
sha256sum --check --strict MANIFEST.sha256
python3 company/check_package.py /absolute/path/to/MiniPC-Connect-Company-Handoff-v2-20261025.zip
python3 -m unittest discover -s company -p 'test_*.py' -v
```

The package checker expects this **new handoff's** required documents; older minimal v2 archives will not meet its completeness contract. Its private-path filter is a packaging guard, not a general secret detector or signature verifier. Build uses explicit source categories and no home state directory.

Portal tests use an isolated environment, not system Python packages:

```sh
python3 -m venv .venv-tests
.venv-tests/bin/python -m pip install -r server/requirements.txt
.venv-tests/bin/python -m unittest discover -s server/tests -p 'test_*.py' -v
```

Package installation uses network unless dependencies are pre-provisioned by IT. Do not assume standalone pytest includes project dependencies. The portal suite currently contains 10 tests; company source tests contain 4 configuration/discovery tests plus 4 archive-contract tests. A successful count is not a substitute for reading failures/status. Tests may create/remove only their own temporary fixtures, not a deployment database.

The current pinned test environment emits `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.` The ten tests passed with that warning. Record it; do not silently upgrade dependencies or claim warning-free output. Run from the **exported root** containing `server/` and `company/`; running the same discovery command from the original home workspace's parent layout causes `ModuleNotFoundError: No module named 'server'` and is not a model/server failure.

Windows equivalent using an approved Python launcher:

```powershell
py -3 -m venv .venv-tests
& '.\.venv-tests\Scripts\python.exe' -m pip install -r '.\server\requirements.txt'
& '.\.venv-tests\Scripts\python.exe' -m unittest discover -s company -p 'test_*.py' -v
& '.\.venv-tests\Scripts\python.exe' -m unittest discover -s server/tests -p 'test_*.py' -v
```

Python is a development/test prerequisite, not a normal laptop user's runtime dependency. If Windows sandbox policy denies a test access to its own temporary directory, record the exact error and use an explicitly approved local test context; do not change production ACLs to make a test pass.

## 2. Native build and contract checks

Build only the helper (no enrollment/trust/network):

```powershell
& '.\windows\build-helper.ps1'
```

Requires the existing x64 .NET Framework compiler at `C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe`; do not install an unrelated compiler silently. The build replaces the helper in the **working copy**, so the original manifest no longer describes that modified working tree. Keep the original release immutable; repack approved changes with a new filename.

The included `source/windows/Tests.cs` expects a **public synthetic fixture** with ContextTokens 16384. It exercises DPAPI, hash rejection, isolated environment, ownership, credential rollback and atomic writes, not live inference. After a per-site public client ZIP has been generated and verified, create a separate test directory and use its **public** config/root as a fixture. Never copy a real profile/key into this directory:

```powershell
$ErrorActionPreference = 'Stop'
$clientZip = Read-Host 'Absolute path to the VERIFIED public per-site client ZIP'
$testDir = Join-Path (Get-Location).Path '.native-contract-check'
if (Test-Path -LiteralPath $testDir) { throw 'Choose a new empty test directory; do not overwrite one.' }
Expand-Archive -LiteralPath $clientZip -DestinationPath $testDir
$fixturePath = Join-Path $testDir 'pilot.json'
$fixture = Get-Content -Raw -LiteralPath $fixturePath | ConvertFrom-Json
$fixture.ContextTokens = 16384
$fixture.OutputTokens = 1024
$fixture | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $fixturePath -Encoding UTF8
$compiler = 'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$sources = @('Deployment.cs','Gateway.cs','Artifacts.cs','Client.cs','Portal.cs','Tests.cs') |
    ForEach-Object { Join-Path '.\source\windows' $_ }
$testExe = Join-Path $testDir 'Tests.exe'
& $compiler /nologo /codepage:65001 /target:exe /platform:x64 /r:System.Net.Http.dll /r:System.Web.Extensions.dll /r:System.Security.dll /r:System.IO.Compression.dll /r:System.IO.Compression.FileSystem.dll "/out:$testExe" @sources
if ($LASTEXITCODE -ne 0) { throw 'Native contract compilation failed' }
& $testExe
if ($LASTEXITCODE -ne 0) { throw 'Native contract checks failed' }
```

The fixture context does **not** change server configuration or test a 16384-token request. The test root is separate and carries only public configuration; the suite generates its own disposable synthetic keys. Expected historical result is 32 assertions. The original legacy GUI offscreen test source is included for reference; central browser pairing is the supported default onboarding path.

## 3. Company acceptance matrix

Record each gate as PASS / FAIL / NOT RUN with timestamp, exact component versions, sanitized evidence and operator. Do not turn “not run” into “pass.”

| Gate | Procedure / evidence required |
|---|---|
| Fresh install | New directory/secrets; Compose validation; repeat init refuses without changing existing files |
| Full startup | Four generated services healthy; existing model identity/start time unchanged; no unintended listeners |
| Owner bootstrap | Private terminal activation; real owner browser login; no placeholder account |
| HTTPS/LAN boundary | Correct SAN/chain/trust; intended clients connect; unapproved scope refused where testable |
| DB model CRUD | Discover exact existing model; select route; reselect/update it; verify no duplicate alias routes and no model restart |
| One real client | Browser login + public device approval + actual Read marker test through OpenCode; Ready recorded |
| Optional Claude | Separate real Read marker test and acceptable latency; approved terms/policy; no cloud fallback |
| Renewal | Same owner/device; verify new keys, old keys rejected, local project/history preserved |
| Recovery | In disposable profile, controlled interruption at final acknowledgement; retry same helper; no duplicate active keys |
| Isolation | Account B cannot view/approve/revoke account A's device; inference key cannot call management endpoints |
| Revocation | Normal user revokes own device; its prior keys return 401; other account still works |
| Second laptop | A **different physical Windows laptop**, own account/profile, same per-site portal; not just a second folder |
| 4–5 simultaneous users | Controlled overlapping real workloads; backend proves overlapping inference, not only queued HTTP requests |
| Backup/restore | Approved encrypted consistent backup; isolated restore checked without duplicating live keys/site |

Use disposable test accounts/projects and generated random marker files. Do not stress-test a busy production model. Ask the owner for acceptable latency/error thresholds before judging performance. Start with two users, then four/five if resources remain safe. Record time to first token, total time, failures/429s, CPU/RAM/VRAM and concurrent backend slots. Gateway max_parallel_requests=5 is an admission setting, not proof of throughput. A runtime with one slot queues/serializes unless its own implementation/configuration is deliberately changed; this handoff does not make that change automatically.

For key refusal, read protected credentials only inside a local private verification process and output **only** status/boolean evidence. Never print DPAPI plaintext or full request headers. Keep the test's affected-user/key inventory so cleanup cannot delete real accounts.

## 4. Known historical results vs open work

See `../ACCEPTANCE.md` and `HOME-ACCEPTANCE.json`. Home achieved one clean two-harness enrollment in 112.123 seconds (OpenCode 87.316, Claude 19.418) and successful revocation with both old keys returning 401. These were one-laptop observations, not company benchmarks or an SLA.

The home host did not run a second full fresh gateway stack because free RAM was about 3.58 GiB. Fresh init/template validation/import/publication were tested; fresh full startup, initial owner activation and model CRUD remain separate gates. Synthetic browser fixtures checked UI states; do not claim they typed/logged in a real company user. No second physical laptop or company-specific model/network/license was validated at home.

The 19 earlier gateway and 2 earlier GUI-installer regression checks mentioned in ACCEPTANCE.md were run in the original home workspace. Those old home-only test drivers depend on private home configuration and are not needed by, or bundled with, this portable deployment. The portable source/API/native tests above are included and reproducible.

## 5. Report and stop conditions

Copy `DEPLOYMENT-REPORT.template.md` outside the immutable release and complete it. Stop and report a missing prerequisite when: Linux access is not authorized, model lacks required tool API, CA/policy is not approved, resources are unsafe, required signing/downloads are blocked, or a fresh-stack gate fails. Do not loop for hours, guess credentials, disable checks or change the model runtime without new approval.

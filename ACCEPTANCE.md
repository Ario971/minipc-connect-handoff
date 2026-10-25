# Release acceptance — 2026-10-25

## Passed

- Central portal running on the existing home Linux MiniPC over verified HTTPS.
- 10 portal API/pairing tests passed on Windows and inside the exact pinned Linux gateway image, without networking in the test container.
- 4 portable configuration/model-discovery/deployment-template tests passed.
- 32 native Windows contract assertions passed, including CurrentUser DPAPI, ownership, credential rollback and repeated atomic checkpoint replacement. Compatibility GUI offscreen checks passed; browser pairing is the default entry point.
- Existing gateway regression suite: 19 tests passed. Existing installer contracts: 2 tests passed.
- Clean real enrollment of one disposable internal-user account and two isolated harness profiles completed in 112.123 seconds. OpenCode's read-tool job took 87.316 seconds; Claude Code's took 19.418 seconds. These are smoke-test observations, not capacity benchmarks.
- Both programs actually read a randomly generated local marker through their tool interface and returned it. Helper and server recorded Ready. Normal-user session logout and own-device revocation succeeded. Each revoked inference key subsequently returned HTTP 401; test-account deletion left zero keys.
- A prior interrupted final-save attempt was recovered from its saved checkpoint without rerunning inference. The Windows atomic-save issue was corrected, followed by the clean enrollment above.
- Browser checks: deployed page/HTTPS/CSP, helper download/checksum, desktop/mobile layout and synthetic UI fixtures for login, approval, harness selection and revocation. Browser credentials were fake; real authentication/approval was tested through the same portal API, not by typing an owner's password in browser automation.
- Portable ZIP extracted and manifest verified on Linux. Fresh initialization produced separate configuration/secrets; existing destinations were refused without changing credentials. Generated Compose and Caddy validated. Portal app imported in the pinned image under its non-root account. Publication produced a site-specific Windows ZIP containing only helper, public settings, public root certificate and instructions.
- Existing home model PID, LiteLLM start time and Postgres start time stayed unchanged. No model was installed on a laptop and no cloud fallback was enabled.

## Not yet accepted

- A second physical Windows laptop. Separate profiles on one laptop do not substitute for it.
- Full startup of a fresh four-service stack, initial owner activation on its new database, and live model creation/update through that fresh stack. Linux initialization, configuration and publication were tested; a second full stack was deliberately not started with about 3.58 GiB free RAM on the home host. The existing home stack validated live account/key flows.
- The company's actual model, tool calling, context size, separate commercial-use license and real 4–5-user capacity.
- Corporate DNS/firewall policy, organizational certificates, helper signing/allowlisting and installation behind a company proxy.

This release is for a controlled staging handoff, not a claim that company production deployment has passed. Run the remaining gates on company staging before general rollout. Source, pinned components and administrator instructions are included in README.md.

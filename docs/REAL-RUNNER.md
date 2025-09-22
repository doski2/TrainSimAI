# Real-runner (self-hosted) runbook

This document explains how to prepare a Windows self-hosted runner for running tests marked `real`.

Prerequisites
- Windows Server 2019/2022 or Windows 10/11 (latest updates).
- Administrative access to install services and drivers.
- The GitHub Actions runner installed and registered with labels: `self-hosted`, `windows`, `real`.

Runner setup
1. Download and install the GitHub Actions runner and register it with the repository. When registering, add the labels:
   - `self-hosted`
   - `windows`
   - `real`

2. Install runner as a service (recommended) so it survives reboots.

Validation script
- We provide `scripts/validate_real_runner.ps1` which checks OS, available disk, required environment variables, and whether native DLLs needed by `RailDriver` are present. Run it as Administrator:

```powershell
.\scripts\validate_real_runner.ps1 -Verbose
```

Security and safety checklist
- Ensure the runner is in an isolated network or VLAN when interacting with real hardware.
- Create a dedicated service account for the runner with least privilege.
- Disable automatic updates for components that could break tests during CI runs.

Running `real` tests
- In your workflow, ensure the job contains `runs-on: [self-hosted, windows, real]` and includes an initial validation step that runs `scripts/validate_real_runner.ps1`.
- Run `pytest -m real` only after validation passes.

Troubleshooting
- If tests fail due to driver/DLL load errors, check the output of `scripts/validate_real_runner.ps1` and the Windows Event Log.
- Ensure the `RailDriver` production DLLs are installed only on the runner and not present in hosted CI.

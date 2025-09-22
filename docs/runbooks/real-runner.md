# Runbook: Preparing a self-hosted Windows runner for 'real' tests

This runbook lists the minimum steps and checks to prepare a Windows machine that can run tests marked `real` (those that require the RailDriver / RailWorks integration).

Prerequisites
- Windows 10/11 or Windows Server with access to install Steam and RailWorks.
- Python 3.11 installed and on `PATH`.
- `git` installed and configured with the user that will run CI.
- For self-hosted runner: GitHub Actions runner installed and registered as a service or run interactively.

Steps
1. Install Steam and RailWorks
   - Install Steam for the user account that will run tests.
   - Install RailWorks (Train Simulator) and confirm it runs.

2. Locate the RailDriver DLLs
   - Typical locations:
     - `C:\Program Files (x86)\RailWorks\raildriver.dll`
     - `C:\Program Files\RailWorks\raildriver.dll`
   - Alternatively set environment variable `TSC_RD_DLL_DIR` pointing to the directory that contains the DLL(s).

3. Configure environment variables (recommended)
   - Set `TSC_RD_DLL_DIR` or `RAILWORKS_PLUGINS` to the folder with RailDriver DLLs.
   - Ensure the GitHub runner service account has read access to that folder.

4. Validate the environment
   - Run `scripts\validate_real_runner.ps1` as the account that will run the tests.
   - Expected exit code `0` on success.

5. Run real tests
   - From the repository root run:
     ```powershell
     python -m pip install -r requirements.txt
     python -m pytest -m real
     ```

6. Troubleshooting
   - If `py-raildriver` fails looking up Steam in the registry, ensure the user running tests is the same user who installed Steam and that Steam appears under `HKCU:\Software\Valve\Steam`.
   - If DLL missing, verify `TSC_RD_DLL_DIR` and file permissions.

Notes
- Only run `pytest -m real` on trusted self-hosted runners. Hosted GitHub Actions runners will not have the necessary Steam/RailWorks installation and will fail.
- Prefer to run real tests as a dedicated job that does not mix with hosted `not-real` CI.

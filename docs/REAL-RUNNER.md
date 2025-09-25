# Runbook: configurar Self-hosted runner para tests reales (hardware RD)

Este documento describe pasos para preparar una máquina Windows que ejecute tests reales que usan `py-raildriver` y DLLs del juego.

Requisitos mínimos
- Windows Server / Windows 10/11 x64
- Python 3.11 (64-bit)
- Visual C++ Redistributable (última versión)
- Acceso al directorio `RailWorks/plugins` con `RailDriver64.dll` o `RailDriver.dll`

Variables de entorno importantes
- `RAILWORKS_PLUGINS` o `TSC_RD_DLL_DIR`: carpeta donde está la DLL `RailDriver*.dll`.
- `TSC_RD` (opcional): especifica el proveedor/objeto RailDriver a usar.

Protección y etiqueta del runner
- Registrar el runner self-hosted con GitHub y añadir la label `real-hw`.
- En los workflows que ejecuten tests reales, usar `runs-on: self-hosted` y `labels: [real-hw]`.
- No registrar el runner en una red pública ni abrir puertos innecesarios.

Pruebas de smoke

1) Comprobar detección de DLL:

```powershell
$env:RAILWORKS_PLUGINS = 'C:\Program Files (x86)\Steam\steamapps\common\RailWorks\plugins'
python -c "from ingestion.rd_client import _locate_raildriver_dll; print(_locate_raildriver_dll())"
```

2) Ejecutar test de humo local (no en CI todavía):

```powershell
python -m pytest tests/test_real_smoke.py -q
```

Si el test no encuentra DLL, ajusta `RAILWORKS_PLUGINS` o `TSC_RD_DLL_DIR`.

Notas de seguridad
- Evitar exponer la máquina a internet; usar credenciales separadas.
- Mantener políticas de acceso para el usuario que ejecuta el runner (no use admin sin necesidad).
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

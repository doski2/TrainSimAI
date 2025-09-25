## Developer setup (Windows)

Este documento contiene pasos mínimos para contribuir y mantener formato/lint en Windows PowerShell.

1) Entorno Python

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

2) Pre-commit (formateo/lint)

Instala las herramientas y registra los hooks:

```powershell
$env:PATH += ";$env:USERPROFILE\AppData\Roaming\Python\Python311\Scripts"
python -m pip install --user pre-commit black isort ruff
pre-commit install
```

Comprobar antes de push:

```powershell
pre-commit run --all-files
```

Si `pre-commit` muestra cambios, aplícalos y haz commit antes de pushear.

3) EOL en Windows

El repositorio fuerza `LF` para Python con `.gitattributes`. Si ves CRLF localmente:

```powershell
git config core.autocrlf false
git add --renormalize .
git commit -m "chore: normalize EOL to LF" -a
```

4) Ejecutar tests

Tests seguros para CI (no hardware):

```powershell
python -m pytest -q -m "not real"
```

Tests que requieren hardware / DLL: sólo en runners self-hosted con label `real-hw`.

5) Normas rápidas
- Ejecutar `pre-commit run --all-files` antes de push.
- Si editas archivos de perfil (`profiles/`) documenta alias añadidos en `profiles/suggested_aliases.json`.

---
Ficha: si quieres puedo añadir un script PowerShell `scripts/normalize-eol.ps1` para automatizar la normalización en Windows.
# Developer instructions

Windows development quickstart

- Activate virtualenv:
  - PowerShell: `. .venv\Scripts\Activate.ps1`

- Ensure UTF-8 output in PowerShell (helps pre-commit hooks and CI logs):
  - `$env:PYTHONIOENCODING = 'utf-8'`

- Install development dependencies (if using `requirements-dev.txt`):
  - `python -m pip install -r requirements-dev.txt`

- Install and run pre-commit hooks locally:
  - `python -m pip install pre-commit`
  - `pre-commit install`
  - `python -m pre_commit run --all-files`

- Run linters and tests:
  - `python -m ruff check .`
  - `pytest -q`

CI notes

- The hosted CI runs the `not-real` workflow which executes `pre-commit` and `pytest` for non-hardware tests.
- Tests marked with `@pytest.mark.real` run only on self-hosted Windows runners and require manual validation via `scripts/validate_real_runner.ps1`.

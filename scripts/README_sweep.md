Sweep de parámetros para la lógica de frenado

Uso rápido (PowerShell):

```powershell
# activar virtualenv si procede
& .\.venv\Scripts\Activate.ps1
python scripts\sweep_brake_params.py
Get-Content data\sweep\summary.csv -Tail 50
```

Salida: `data/sweep/summary.csv` con una fila por ejecución y conteos de envíos RD (0 / intermedio / 1.0).

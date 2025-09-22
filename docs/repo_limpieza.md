# Higiene del repositorio

## No versionar
- `/data/*` (CSV/JSON/JSONL/Parquet, runs y events), `lua_eventbus.jsonl`
- Logs/temporales: `stdout*.txt`, `stderr*.txt`, `tmp_*.txt`, `*.log`, `*.tmp`, `*.bak`
- Cachés: `__pycache__/`, `.pytest_cache/`, `*.egg-info/`
- Entornos: `.venv/`, `.env*`
- Artefactos de SO: `.DS_Store`, `Thumbs.db`

## Mover a `/docs`
- Dossiers/planes/roadmaps (MD y PDF) para mantener la raíz limpia.

## Vendorizados
- Si no hay parches propios, preferir **pip** a copiar árboles de terceros.
- Si hay parches, usar `vendor/<nombre>` con LICENSE y origen.

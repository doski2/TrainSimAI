# Repository Guidelines

## Project Structure & Module Organization
- `src/` – primary source code (packages, modules, CLI).
- `tests/` – test suites mirroring `src/` layout (unit/integration).
- `assets/` – data, fixtures, and media used by the app/tests.
- `scripts/` – helper scripts for setup, lint, format, and dev tasks.
- `docs/` – project documentation and design notes.

## Build, Test, and Development Commands
- Prefer project scripts if present: `scripts/dev`, `scripts/test`, `scripts/lint`.
- With a `Makefile`: `make install`, `make test`, `make run`.
- Python example: `python -m pip install -e .`, `pytest -q`, `pytest --cov`.
- Node example: `npm ci`, `npm test`, `npm run start`.
- .NET example: `dotnet restore`, `dotnet build -c Release`, `dotnet test`.

## Coding Style & Naming Conventions
- Indentation: 4 spaces; wrap lines at ~100–120 chars.
- Use configured formatters/linters (e.g., Black/flake8, Prettier/ESLint, dotnet-format). Run before committing.
- Naming: `snake_case` for files/functions, `PascalCase` for classes/types, `kebab-case` for CLI names.
- Keep modules cohesive; small functions with clear docstrings or XML/TS docs.

## Testing Guidelines
- Place tests alongside mirrored paths: `tests/<package>/test_<unit>.py` or `tests/<Project>/*Tests.cs`.
- Aim for meaningful coverage on core logic; add regression tests for fixes.
- Mark slow/integration tests clearly (e.g., `@pytest.mark.slow` or Category attributes).
- Run the full test suite locally before opening a PR.

## Commit & Pull Request Guidelines
- Use Conventional Commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
- Commit messages: imperative, present tense; keep body focused on the why.
- PRs: concise description, linked issues (e.g., `Closes #123`), screenshots/logs when relevant, and updated tests/docs.

## Security & Configuration Tips
- Never commit secrets; prefer environment variables. Store examples in `.env.example`; local overrides in `.env.local`.
- Pin dependencies when possible; update via dedicated PRs.

## Agent-Specific Notes
- Keep changes minimal and scoped; prefer small, reviewable patches.
- Obey AGENTS.md in subdirectories when present; deeper files take precedence.
- Do not add license headers unless explicitly requested. Update docs when touching public APIs.

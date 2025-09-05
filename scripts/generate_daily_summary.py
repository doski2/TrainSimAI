from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path


def sh(args: list[str], cwd: Path) -> str:
    cp = subprocess.run(
        args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        shell=False,
    )
    if cp.returncode != 0:
        return ""
    return cp.stdout.strip()


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    out_dir = repo / "docs" / "diario"
    out_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    now_str = today.strftime("%Y-%m-%d %H:%M:%S")
    out_path = out_dir / f"{today_str}.md"

    remote = sh(["git", "remote", "get-url", "origin"], cwd=repo)
    log_raw = sh(
        [
            "git",
            "-c",
            "i18n.logOutputEncoding=UTF-8",
            "log",
            "--since=midnight",
            "--pretty=format:%h|%ad|%s",
            "--date=iso-local",
        ],
        cwd=repo,
    )
    status_raw = sh(["git", "status", "--porcelain=v1"], cwd=repo)

    commits: list[tuple[str, str, str]] = []
    if log_raw:
        for line in log_raw.splitlines():
            try:
                h, ts, msg = line.split("|", 2)
                # ts format "YYYY-MM-DD HH:MM:SS +TZ"
                hhmm = ts.split(" ")[1][:5]
                commits.append((hhmm, msg, h))
            except ValueError:
                continue

    lines: list[str] = []
    lines.append(f"# Resumen del dia - {today_str}")
    lines.append("")
    lines.append(f"- Generado: {now_str} (hora local)")
    if remote:
        lines.append(f"- Repositorio: {remote}")
    lines.append("")
    lines.append("## Commits de hoy")
    lines.append("")
    if commits:
        for hhmm, msg, h in commits:
            lines.append(f"- {hhmm} - {msg} ({h})")
    else:
        lines.append("- (Sin commits hoy)")
    lines.append("")
    lines.append("## Cambios sin commit")
    lines.append("")
    if status_raw:
        code_map = {
            "M": "modificado",
            "A": "añadido",
            "D": "eliminado",
            "R": "renombrado",
            "C": "copiado",
            "U": "en conflicto",
            "?": "no seguido",
            "!": "ignorado",
        }
        for line in status_raw.splitlines():
            if len(line) < 3:
                continue
            xy = line[:2]
            path = line[3:]
            if xy == "??":
                lines.append(f"- {code_map['?']}: {path}")
                continue
            # manejar renombres "old -> new"
            if " -> " in path:
                old, new = path.split(" -> ", 1)
                path = f"{old} -> {new}"
            parts: list[str] = []
            if xy[0] != " ":
                parts.append(f"index {code_map.get(xy[0], xy[0])}")
            if xy[1] != " ":
                parts.append(f"worktree {code_map.get(xy[1], xy[1])}")
            label = ", ".join(parts) if parts else "cambio"
            lines.append(f"- {label}: {path}")
    else:
        lines.append("- (Sin cambios locales)")
    lines.append("")
    lines.append("## Acciones realizadas (no versionadas)")
    lines.append("")
    lines.append("- (N/D)")
    lines.append("")

    new_content = "\n".join(lines)

    # Solo escribir si hay cambios reales (ignorando la línea de timestamp "Generado:")
    def strip_generated(ts: str) -> str:
        return "\n".join(
            ln for ln in ts.splitlines() if not ln.startswith("- Generado:")
        ).strip()

    if out_path.exists():
        old_content = out_path.read_text(encoding="utf-8")
        if strip_generated(old_content) == strip_generated(new_content):
            # Sin novedades: no reescribimos para evitar cambios de timestamp.
            print("[diario] Sin novedades; archivo no actualizado.")
            return

    out_path.write_text(new_content, encoding="utf-8")
    print(f"[diario] Resumen actualizado: {out_path}")


if __name__ == "__main__":
    main()

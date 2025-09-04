from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path


def sh(args: list[str], cwd: Path) -> str:
    cp = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, shell=False)
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
    log_raw = sh(["git", "log", "--since=midnight", "--pretty=format:%h|%ad|%s", "--date=iso-local"], cwd=repo)

    commits = []
    if log_raw:
        for line in log_raw.splitlines():
            try:
                h, ts, msg = line.split("|", 2)
                # ts formato "YYYY-MM-DD HH:MM:SS +TZ"
                hhmm = ts.split(" ")[1][:5]
                commits.append((hhmm, msg, h))
            except ValueError:
                continue

    lines: list[str] = []
    lines.append(f"# Resumen del día — {today_str}")
    lines.append("")
    lines.append(f"- Generado: {now_str} (hora local)")
    if remote:
        lines.append(f"- Repositorio: {remote}")
    lines.append("")
    lines.append("## Commits de hoy")
    lines.append("")
    if commits:
        for hhmm, msg, h in commits:
            lines.append(f"- {hhmm} — {msg} — {h}")
    else:
        lines.append("- (Sin commits hoy)")
    lines.append("")
    lines.append("## Acciones realizadas (no versionadas)")
    lines.append("")
    lines.append("- (N/D)")
    lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()


from __future__ import annotations

from pathlib import Path
from dataclasses import replace

from runtime.braking_v0 import BrakingConfig
from runtime.profiles import load_braking_profile


def test_load_braking_profile_basic(tmp_path: Path):
    p = tmp_path / "loco.json"
    p.write_text(
        """
        {
          "braking_v0": {
            "margin_kph": 4.0,
            "max_service_decel": 0.8,
            "reaction_time_s": 0.5
          }
        }
        """,
        encoding="utf-8",
    )
    cfg = load_braking_profile(p)
    assert cfg.margin_kph == 4.0
    assert cfg.max_service_decel == 0.8
    assert cfg.reaction_time_s == 0.5


def test_cli_override_wins(tmp_path: Path):
    p = tmp_path / "loco.json"
    p.write_text(
        """
        {"braking_v0": {"margin_kph": 2.0, "max_service_decel": 0.6, "reaction_time_s": 0.7}}
        """,
        encoding="utf-8",
    )
    cfg = load_braking_profile(p, base=BrakingConfig())
    # “Simula” que luego el CLI pone margen=5.0
    cfg2 = replace(cfg, margin_kph=5.0)
    assert cfg2.margin_kph == 5.0 and cfg.margin_kph == 2.0

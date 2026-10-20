import importlib.util
import json
from pathlib import Path

K_KILLED = "killed"
K_TOTAL = "total"
PERCENT_80 = 80
PERCENT_85 = 85
EXIT_NO_STATS = 2

SPEC = importlib.util.spec_from_file_location("check_mutation_score", Path(__file__).resolve().parents[1] / "tools" / "check_mutation_score.py")
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


def write(root, killed, total, skipped=0):
    (root / "mutants").mkdir(exist_ok=True)
    (root / "mutants" / "mutmut-cicd-stats.json").write_text(json.dumps({K_KILLED: killed, K_TOTAL: total, "skipped": skipped}))


def test_score_ignores_skipped_and_handles_empty():
    assert tool.score({K_KILLED: 8, K_TOTAL: 12, "skipped": 2}) == PERCENT_80
    assert tool.score({K_KILLED: 0, K_TOTAL: 0}) == 0.0


def test_threshold_from_config_or_default(tmp_path):
    assert tool.threshold(tmp_path) == PERCENT_80
    (tmp_path / "craft-gate.toml").write_text("[mutation]\nthreshold = 85\n")
    assert tool.threshold(tmp_path) == PERCENT_85


def test_main_passes_at_threshold_and_fails_below(tmp_path, capsys):
    write(tmp_path, 80, 100)
    assert tool.main(tmp_path) == 0
    assert "80.0 %" in capsys.readouterr().out
    write(tmp_path, 79, 100)
    assert tool.main(tmp_path) == 1


def test_main_without_stats_is_an_error(tmp_path, capsys):
    assert tool.main(tmp_path) == EXIT_NO_STATS
    assert "mutmut run" in capsys.readouterr().err

import importlib.util
import json
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("check_mutation_score", Path(__file__).resolve().parents[1] / "tools" / "check_mutation_score.py")
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


def write(root, killed, total, skipped=0):
    (root / "mutants").mkdir(exist_ok=True)
    (root / "mutants" / "mutmut-cicd-stats.json").write_text(json.dumps({"killed": killed, "total": total, "skipped": skipped}))


def test_score_ignores_skipped_and_handles_empty():
    assert tool.score({"killed": 8, "total": 12, "skipped": 2}) == 80.0
    assert tool.score({"killed": 0, "total": 0}) == 0.0


def test_threshold_from_config_or_default(tmp_path):
    assert tool.threshold(tmp_path) == 80
    (tmp_path / "craft-gate.toml").write_text("[mutation]\nthreshold = 85\n")
    assert tool.threshold(tmp_path) == 85


def test_main_passes_at_threshold_and_fails_below(tmp_path, capsys):
    write(tmp_path, 80, 100)
    assert tool.main(tmp_path) == 0
    assert "80.0 %" in capsys.readouterr().out
    write(tmp_path, 79, 100)
    assert tool.main(tmp_path) == 1


def test_main_without_stats_is_an_error(tmp_path, capsys):
    assert tool.main(tmp_path) == 2
    assert "mutmut run" in capsys.readouterr().err

"""Score de mutation global : échoue si la part de mutants tués passe sous le seuil de craft-gate.toml [mutation].

Complète le contrôle de craft-gate, qui ne regarde que les fonctions touchées par une PR : tant que le projet est
jeune, le seuil vaut pour l'ensemble du code muté.

    mutmut run && mutmut export-cicd-stats && python tools/check_mutation_score.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

DEFAULT_THRESHOLD = 80


def threshold(root: Path) -> int:
    path = root / "craft-gate.toml"
    if not path.exists():
        return DEFAULT_THRESHOLD
    return int(tomllib.loads(path.read_text(encoding="utf-8")).get("mutation", {}).get("threshold", DEFAULT_THRESHOLD))


def score(stats: dict) -> float:
    """Part de mutants tués parmi ceux qui comptent (les ignorés ne comptent pas)."""
    counted = stats["total"] - stats.get("skipped", 0)
    return 100.0 * stats["killed"] / counted if counted else 0.0


def main(root: Path = Path(".")) -> int:
    stats_path = root / "mutants" / "mutmut-cicd-stats.json"
    if not stats_path.exists():
        print("Aucune statistique : lancer `mutmut run` puis `mutmut export-cicd-stats`.", file=sys.stderr)
        return 2
    stats = json.loads(stats_path.read_text(encoding="utf-8"))
    got, floor = score(stats), threshold(root)
    print(f"Score de mutation global : {got:.1f} % ({stats['killed']} tués sur {stats['total']}), seuil {floor} %.")
    if got < floor:
        print("Sous le seuil : renforcer les tests des fonctions aux mutants survivants (`mutmut results`).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Qualité du code : craft-gate

Ce dépôt applique [craft-gate](https://github.com/gbelbe/craft-gate) (version dans `.craft-gate-version`) : un catalogue
de pratiques de craftsmanship (Beck, Fowler, Martin, Feathers) transformé en convention de commit et en contrôles de CI.

## Convention de commit

Un commit qui touche du code contient soit un rangement séparé `tidy(<type>): ...` avec les trailers `Tidy-Type:` et
`Tidy-Source:`, soit `test(characterize): ...` pour du code sans test, soit un trailer `Tidy-Exempt: <raison>` quand
rien ne s'applique. Le catalogue est dans [CRAFTSMANSHIP.md](../CRAFTSMANSHIP.md), les règles pour les agents dans
[AGENTS.md](../AGENTS.md).

## Contrôles de CI (`.github/workflows/ci.yml`)

| Contrôle | État ici |
|---|---|
| Tidy First ratchet | actif |
| Refactor First | actif |
| Complexité (cyclomatique et cognitive) | actif |
| Couverture du patch (diff-cover, `pytest --cov`) | actif, seuil 90 % |
| Mutation (mutmut), fonctions touchées | actif ; configuré dans `[tool.mutmut]` |
| Mutation, score global ≥ 80 % | actif (`mutation-score`, `tools/check_mutation_score.py`) |
| Couverture comportementale (Gherkin) | actif ; scénarios dans `tests/features`, exécutés par pytest-bdd |

**Seuil de 80 % sur tout le code muté.** Le contrôle de craft-gate ne regarde que les fonctions qu'une PR touche.
Tant que le projet est jeune, le seuil de `craft-gate.toml [mutation]` vaut pour l'ensemble : le job `mutation-score`
lance `mutmut run` sur `domain.py`, `pipeline.py`, `adapters/extractors.py` et `adapters/linker.py`, puis
`tools/check_mutation_score.py` échoue sous le seuil. Mesure actuelle : **96,7 %** (414 mutants tués sur 428). Les 14
survivants sont surtout équivalents (valeurs initiales remplacées avant usage, ordre des candidats).

Les tests sélectionnés pour mutmut sont `tests/test_pipeline.py`, `tests/test_behaviour_details.py` (valeurs exactes et
bornes) et les scénarios Gherkin. Pour voir les survivants : `mutmut run && mutmut results`.

## En local

```bash
bash scripts/check_tidy_ratchet.sh --base origin/main
pytest --cov=mail2graph --cov-report=xml && bash scripts/local-craft-gate.sh
pytest tests/features            # scénarios Gherkin seuls
```

Une mise à jour hebdomadaire de craft-gate est proposée par PR (`craft-gate-update.yml`).

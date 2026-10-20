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
| Mutation (mutmut) | actif ; configuré dans `[tool.mutmut]` (tests unitaires seulement, `tests/features` exclu pour la vitesse) |
| Couverture comportementale (Gherkin) | actif ; scénarios dans `tests/features`, exécutés par pytest-bdd |

Mesure initiale (octobre 2026) : sur `domain.py`, `pipeline.py`, `adapters/extractors.py` et `adapters/linker.py`,
mutmut génère 428 mutants et les tests unitaires en tuent 274 (64 %). Le contrôle applique un plancher de 80 % aux
fonctions qu'une PR touche, avec une baseline enregistrée : les fonctions les plus faibles sont `Pipeline.propose`
(62 survivants), `GazetteerExtractor.extract` (19) et `FuzzyLinker.link` (17). Les toucher demandera d'abord de
renforcer leurs tests. Les scénarios Gherkin ne sont pas comptés dans cette mesure.

## En local

```bash
bash scripts/check_tidy_ratchet.sh --base origin/main
pytest --cov=mail2graph --cov-report=xml && bash scripts/local-craft-gate.sh
pytest tests/features            # scénarios Gherkin seuls
```

Une mise à jour hebdomadaire de craft-gate est proposée par PR (`craft-gate-update.yml`).

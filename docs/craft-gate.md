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
| Mutation (mutmut) | **désactivé**, raison dans `craft-gate.toml` |
| Couverture comportementale (Gherkin) | **désactivé**, raison dans `craft-gate.toml` |

Les deux contrôles désactivés se réactivent en passant `enabled = true` dans `craft-gate.toml` quand `[tool.mutmut]`
est configuré et que les scénarios de `features/` s'exécutent sous `tests/features` (voir [test-plan.md](test-plan.md)).

## En local

```bash
bash scripts/check_tidy_ratchet.sh --base origin/main
pytest --cov=mail2graph --cov-report=xml && bash scripts/local-craft-gate.sh
```

Une mise à jour hebdomadaire de craft-gate est proposée par PR (`craft-gate-update.yml`).

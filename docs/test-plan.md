# Plan de test (Gherkin)

Les scénarios sont écrits en français (`# language: fr`) dans `tests/features/`. Les définitions d'étapes sont dans
`tests/features/conftest.py` et `tests/features/test_features.py` les exécute avec pytest-bdd. État : **35 scénarios
exécutés et passants**, 5 ignorés (2 `@imap`, 3 `@wip`).

## Outillage prévu

- **pytest-bdd** : réutilise `pytest` et les fixtures existantes (`MemorySource`, graphe Turtle de test, dossier temporaire).
- **CliRunner** de Typer pour les scénarios `@cli`.
- **GreenMail** (ou un serveur IMAP de test Python) pour les scénarios `@imap`, lancé en CI.
- **pyshacl** pour les scénarios `@graph` marqués `@wip`.

## Étiquettes

| Étiquette | Sens |
|---|---|
| `@ingestion`, `@linking`, `@review`, `@privacy`, `@cli`, `@extensibility`, `@graph` | domaine |
| `@imap` | exige un serveur IMAP de test |
| `@wip` | fonctionnalité pas encore implémentée : le scénario décrit la cible ; ignoré à l'exécution |

Les scénarios `@wip` et `@imap` sont ignorés par `tests/features/conftest.py` ; retirer l'étiquette (et ajouter les étapes ou le serveur de test) les active.

## Couverture et état

| Fichier | Scénarios | Déjà couverts par un test existant | À implémenter |
|---|---|---|---|
| `ingestion.feature` | 6 | message déjà vu, filtre d'expéditeur | citations, filtre d'objet, 2 scénarios IMAP |
| `linking.feature` | 7 | lien par n° de dossier, par libellé, nouvelle entité | incertitude, nature non configurée, homonymes, doublons de lien |
| `review_commit.feature` | 7 | rien sans acceptation, enfant sans parent, idempotence de `run` | rejet, double `commit`, `--accept-all`, provenance |
| `privacy.feature` | 5 | corps, adresse, signature absents | injection de consigne, `.gitignore`, classes exclues |
| `cli.feature` | 6 | aucun | tous |
| `extensibility.feature` | 5 | aucun | tous |
| `graph_quality.feature` | 4 | aucun | 2 sont `@wip` (ontologie, SHACL) |

## Écarts connus que ces scénarios mettent en évidence

- **Homonymes** (« Phoenix France Infrastructures » existe deux fois dans le graphe du dossier) : le lieur renvoie
  le meilleur score mais ne signale pas l'ambiguïté. Le scénario correspondant échouera tant que ce n'est pas traité.
- **Validation de l'ontologie** : `check` n'avertit pas si une classe ou propriété configurée n'existe pas.
- **Double `commit`** : le comportement attendu (idempotent) n'est pas encore vérifié par un test.

## Ordre de mise en œuvre proposé

1. `cli.feature` et `review_commit.feature` : le contrat visible par un orchestrateur, sans réseau.
2. `privacy.feature` : les garanties qui comptent le plus.
3. `linking.feature`, `ingestion.feature` (hors `@imap`).
4. `@imap` avec un serveur de test en CI.
5. `graph_quality.feature` une fois SHACL ajouté.

## Critères de sortie de la version 0.2

Tous les scénarios sans `@wip` passent en CI ; aucun scénario `@privacy` n'est ignoré ; la couverture de `domain.py`
et `pipeline.py` dépasse 90 %.

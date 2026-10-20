# mail2graph

[![ci](https://github.com/gbelbe/mail2graph/actions/workflows/ci.yml/badge.svg)](https://github.com/gbelbe/mail2graph/actions/workflows/ci.yml)
[![craft-gate](https://img.shields.io/badge/craft--gate-enabled-blue)](https://github.com/gbelbe/craft-gate)

Connecteur **courriel → graphe RDF** avec **relecture humaine**.

Il lit une boîte IMAP, repère dans chaque message les entités de votre graphe (n° de dossier, organismes,
parcelles…), et dépose des *propositions* : le courriel, ses liens vers les entités, un événement daté, de
nouvelles entités à créer. **Rien n'est écrit dans le graphe sans décision d'un humain.**

- **Indépendant de la boîte** : tout passe par un fichier YAML (IMAP, mbox, ou un plugin).
- **Indépendant de l'agent** : fonctionne seul ; un agent se branche comme un extracteur parmi d'autres.
- **Découplé** : architecture hexagonale, cœur sans entrée-sortie, adaptateurs remplaçables.
- **Réutilise des briques libres** : `imap-tools`, `rdflib`, `rapidfuzz`, `pydantic`, `typer`.
- **Respectueux des données** : le corps des messages et les adresses n'entrent jamais dans le graphe.

> Version 0.1, en construction. Voir [Limites](#limites).

## Démarrage rapide

```bash
pip install -e '.[imap]'              # depuis un clone du dépôt
cp examples/minimal.yaml mail2graph.yaml   # puis l'adapter à votre graphe

mail2graph check  -c mail2graph.yaml  # configuration valide ? que voit-on dans le graphe ?
mail2graph run    -c mail2graph.yaml  # interroge la source, dépose des propositions
mail2graph review -c mail2graph.yaml  # liste ; --accept ID  --reject ID  --accept-all
mail2graph commit -c mail2graph.yaml  # écrit dans le graphe ce qui a été accepté
```

Toutes les commandes acceptent `--json`. Codes de sortie : `0` succès · `1` erreur d'exécution · `2` configuration
invalide · `3` relecture en attente (`run --fail-if-pending`).

## Exemple de résultat

Pour un message qui cite « DP 029 174 26 00122 » et « Mairie de Plonéour-Lanvern », `run` propose :

```
message   Re: DP 029 174 26 00122                    (le courriel : sujet, date, domaine, hachage)
link      DP 029 174 26 00122            1.00
link      Mairie de Plonéour-Lanvern     1.00
event     Re: DP 029 174 26 00122                    (événement daté de la réception)
```

Après `review --accept-all` puis `commit`, un fichier Turtle séparé reçoit les triplets avec leur provenance.

## Documentation

- [Architecture](docs/architecture.md) : ports, flux, ce qui entre dans le graphe.
- [Configuration](docs/configuration.md) : toutes les clés et les commandes.
- [Étendre](docs/extending.md) : plugins, injection d'adaptateurs, extracteur d'agent.
- [Qualité du code (craft-gate)](docs/craft-gate.md)
- [Contribuer](CONTRIBUTING.md) · [Changelog](CHANGELOG.md)

## Intégration dans un orchestrateur

Le module ne connaît aucun outil d'orchestration. On l'appelle par :
- **processus** : `mail2graph run --json`, `review --json`, `commit --json` ;
- **bibliothèque** : `build_pipeline(Config.load(...), source=..., extractors=[...])` ;
- **plugins** : entry points `mail2graph.sources | extractors | stores | queues`.

## Confidentialité et sécurité

- Entrent dans le graphe : sujet, date, domaine de l'expéditeur, hachage de l'identifiant, liens, événement.
  N'entrent **jamais** : corps, adresse complète, nom de l'expéditeur.
- Le mot de passe n'est jamais dans le fichier : `source.password_cmd` appelle votre trousseau.
- La lecture IMAP ne marque, ne déplace et ne supprime rien.
- Le texte d'un message est une donnée, jamais une instruction : aucun message ne déclenche d'action.
- `staging/` (propositions et état) contient des données personnelles : ne pas le versionner.

## Limites

Extraction par expressions régulières, libellés du graphe et, en option, GLiNER (extra `[ner]`, non mesuré sur de vrais courriels) ; liaison floue qui peut se tromper (d'où la relecture) ;
pas encore de validation SHACL, de pièces jointes ni d'interface web. Les classes et propriétés de la
configuration doivent exister dans votre ontologie.

## Développement

```bash
pip install -e '.[dev]'
pytest
```

## Licence

MIT. Voir [LICENSE](LICENSE).

# Étendre mail2graph

## Brancher un adaptateur par entry point

Chaque groupe attend une **fabrique** `cfg -> adaptateur` (`cfg` est l'objet `Config`).

| Groupe | Port implémenté |
|---|---|
| `mail2graph.sources` | `MailSource` |
| `mail2graph.extractors` | `Extractor` |
| `mail2graph.stores` | `GraphStore` |
| `mail2graph.queues` | `ReviewQueue` |

```toml
# pyproject.toml de votre paquet
[project.entry-points."mail2graph.extractors"]
gliner = "mon_paquet.gliner:fabrique"
```

```python
# mon_paquet/gliner.py
from mail2graph.domain import Mention

class GlinerExtractor:
    def __init__(self, labels): ...
    def extract(self, message, ctx):
        # ctx.classes donne les classes du graphe : les utiliser comme étiquettes zéro-shot
        return [Mention(message.id, "organisation", text, score) for text, score in ...]

def fabrique(cfg):
    return GlinerExtractor([c.label for c in ...])
```

Activation : `extract.plugins: [gliner]` dans le fichier de configuration.

## Injecter des adaptateurs sans configuration

```python
from mail2graph import Config, build_pipeline
pipeline = build_pipeline(Config.load("mail2graph.yaml"), source=ma_source, extractors=[mon_extracteur])
pipeline.run()
```

C'est la voie recommandée pour intégrer le module dans un orchestrateur : il n'a besoin que de la CLI (`--json`)
ou de cette fonction.

## NER intégré : GLiNER

`extract.gliner` active `GlinerExtractor` (`adapters/gliner_extractor.py`). Il envoie sujet et corps au modèle avec les
étiquettes de la configuration, ou à défaut celles des classes du graphe, et renvoie des `Mention` (nature, texte,
confiance). Elles suivent ensuite le chemin normal : liaison floue, puis proposition de nouvelle entité si la nature est
dans `graph.new_entity_kinds`. Le modèle se charge à la première utilisation, ou s'injecte (`model=`) pour les tests.

## Un extracteur qui délègue à un agent

Un agent (LLM) se branche comme n'importe quel `Extractor`. Deux règles : le texte du message est une **donnée**
transmise dans un champ délimité, jamais une instruction ; la sortie de l'agent est limitée à des `Mention`
(texte, nature, confiance), et passe par la même relecture humaine.

## Pistes

NER zéro-shot (GLiNER) dont les étiquettes viennent de `ctx.classes` ; validation SHACL avant `commit`
(pyshacl) ; pièces jointes (PDF) ; interface de relecture web ; magasin SPARQL (Oxigraph, Fuseki).

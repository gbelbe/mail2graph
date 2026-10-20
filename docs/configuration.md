# Référence de configuration

Fichier YAML validé par `pydantic` (`src/mail2graph/config.py`). Les chemins relatifs partent du dossier du fichier
de configuration (`root`).

## `source`

| Clé | Défaut | Rôle |
|---|---|---|
| `type` | `imap` | `imap`, `mbox`, ou le nom d'un plugin du groupe `mail2graph.sources` |
| `host`, `port` | — , 993 | serveur IMAP (TLS) |
| `user` | — | identifiant de la boîte |
| `password_cmd` | — | commande qui **affiche** le mot de passe d'application (trousseau, gestionnaire de secrets). Le secret n'est jamais dans le fichier |
| `mailbox` | `INBOX` | dossier IMAP ou libellé |
| `limit` | 200 | nombre maximal de messages par exécution |
| `path` | — | fichier pour `type: mbox` |

La lecture IMAP est en lecture seule : aucun message n'est marqué lu, déplacé ni supprimé.

Exemple de commande pour macOS : `security find-generic-password -s mail2graph -a boite@exemple.fr -w`.
Pour Gmail, il faut IMAP activé et un mot de passe d'application ; pour Proton, Proton Bridge.

## `filter`

`senders_allow` : adresses ou domaines acceptés (vide = tous). `subject_regex` : motif facultatif sur l'objet.

## `extract`

- `regex` : dictionnaire *nature de mention → expression régulière*. La nature sert ensuite à `graph.new_entity_kinds`.
- `gazetteer` : repère les libellés d'entités déjà dans le graphe (`gazetteer_min_len` caractères au minimum).
- `gliner` : reconnaissance d'entités zéro-shot (extra `pip install 'mail2graph[ner]'`, télécharge un modèle au premier usage).
  `labels` associe une nature de mention à l'étiquette donnée au modèle (`organisation: "organisation"`) ; sans `labels`,
  chaque classe du graphe devient une étiquette et sa nature est l'URI de la classe. `model`, `threshold` (0,5 par
  défaut) et `max_chars` (4000 : sujet + début du corps) règlent le reste.
- `plugins` : extracteurs tiers (groupe `mail2graph.extractors`).

## `link`

`link_threshold` (défaut 0,92) et `suggest_threshold` (0,75).

## `graph`

| Clé | Rôle |
|---|---|
| `files` | motifs de fichiers Turtle/RDF à lire (relatifs à `root`) |
| `base_uri` | préfixe des identifiants créés |
| `mail_class`, `event_class` | classes du courriel et de l'événement dans votre ontologie |
| `link_predicate`, `date_predicate` | propriétés « mentionne » et date |
| `identifier_predicates` | propriétés dont la valeur sert aussi à lier (n° de dossier, SIREN…) |
| `exclude_classes` | classes à ne jamais proposer (par exemple des personnes physiques) |
| `new_entity_kinds` | nature de mention → classe proposée pour une entité absente |
| `output_file` | fichier Turtle qui reçoit les ajouts validés |
| `event_from_message` | propose un événement daté de la réception |

Les classes et propriétés indiquées doivent exister dans votre ontologie : mail2graph ne les crée pas.

## `paths`

`queue` (propositions) et `state` (messages vus). Ces fichiers contiennent des données personnelles : ne pas les
versionner dans un dépôt public.

## Commandes

| Commande | Effet |
|---|---|
| `check` | valide la configuration ; affiche classes et entités liables |
| `run [--fail-if-pending] [--json]` | interroge la source, dépose des propositions |
| `review [--accept ID] [--reject ID] [--accept-all] [--note T] [--json]` | liste ou décide |
| `commit [--json]` | écrit les propositions acceptées |

Codes de sortie : 0 succès ; 1 erreur d'exécution ; 2 configuration invalide ; 3 relecture en attente.

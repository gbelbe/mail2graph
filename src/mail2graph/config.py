"""Configuration YAML validée (pydantic). Aucune valeur propre à un graphe n'est codée en dur ailleurs."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class SourceCfg(BaseModel):
    type: str = "imap"                         # imap | mbox | adaptateur tiers
    host: str = ""
    port: int = 993
    user: str = ""
    password_cmd: str = ""                     # commande qui affiche le mot de passe (trousseau) ; jamais le secret
    mailbox: str = "INBOX"
    limit: int = 200
    path: str = ""                             # pour type: mbox


class FilterCfg(BaseModel):
    senders_allow: list[str] = Field(default_factory=list)   # adresses ou domaines ; vide = tous
    subject_regex: str | None = None


class ExtractCfg(BaseModel):
    regex: dict[str, str] = Field(default_factory=dict)      # nom de mention -> expression régulière
    gazetteer: bool = True                                   # repère les libellés d'entités déjà dans le graphe
    gazetteer_min_len: int = 5
    plugins: list[str] = Field(default_factory=list)         # extracteurs tiers (entry points)


class LinkCfg(BaseModel):
    link_threshold: float = 0.92
    suggest_threshold: float = 0.75


class GraphCfg(BaseModel):
    files: list[str] = Field(default_factory=lambda: ["*.ttl"])
    base_uri: str = "https://example.org/dossier/"
    mail_class: str = "https://example.org/ontology#Courriel"
    event_class: str = "https://example.org/ontology#Evenement"
    link_predicate: str = "https://example.org/ontology#mentionne"
    date_predicate: str = "https://example.org/ontology#dateEvenement"
    identifier_predicates: list[str] = Field(default_factory=list)   # propriétés dont la valeur sert à la liaison
    exclude_classes: list[str] = Field(default_factory=list)
    new_entity_kinds: dict[str, str] = Field(default_factory=dict)   # nature de mention -> classe proposée
    output_file: str = "mail2graph-courriels.ttl"
    event_from_message: bool = True


class PathsCfg(BaseModel):
    queue: str = "staging/propositions.yaml"
    state: str = "staging/state.json"


class Config(BaseModel):
    source: SourceCfg = SourceCfg()
    filter: FilterCfg = FilterCfg()
    extract: ExtractCfg = ExtractCfg()
    link: LinkCfg = LinkCfg()
    graph: GraphCfg = GraphCfg()
    paths: PathsCfg = PathsCfg()
    store: str = "rdf"
    queue: str = "yaml"
    root: Path = Path(".")                     # base des chemins relatifs

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        p = Path(path)
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        data.setdefault("root", str(p.resolve().parent))
        return cls.model_validate(data)

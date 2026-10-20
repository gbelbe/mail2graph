"""Assemblage (composition root) : la configuration choisit les adaptateurs ; les tiers s'ajoutent par entry points.

Groupes d'entry points : mail2graph.sources, mail2graph.extractors, mail2graph.stores, mail2graph.queues.
Une fabrique reçoit (cfg: Config) et renvoie l'adaptateur.
"""
from __future__ import annotations

from importlib.metadata import entry_points
from pathlib import Path
from typing import Callable

from .adapters.extractors import GazetteerExtractor, RegexExtractor
from .adapters.gliner_extractor import GlinerExtractor
from .adapters.linker import FuzzyLinker
from .adapters.rdf_store import RdfGraphStore
from .adapters.sources import ImapSource, MboxSource
from .adapters.stores import JsonState, YamlQueue
from .config import Config
from .pipeline import Pipeline


def _plugin(group: str, name: str) -> Callable:
    for ep in entry_points(group=group):
        if ep.name == name:
            return ep.load()
    raise ValueError(f"Adaptateur inconnu : {name!r} (groupe {group})")


def _source(cfg: Config):
    t = cfg.source.type
    if t == "imap":
        return ImapSource(cfg.source)
    if t == "mbox":
        return MboxSource(str(cfg.root / cfg.source.path))
    return _plugin("mail2graph.sources", t)(cfg)


def _store(cfg: Config):
    return RdfGraphStore(cfg.graph, cfg.root) if cfg.store == "rdf" else _plugin("mail2graph.stores", cfg.store)(cfg)


def _queue(cfg: Config):
    return YamlQueue(cfg.root / cfg.paths.queue) if cfg.queue == "yaml" else _plugin("mail2graph.queues", cfg.queue)(cfg)


def build_pipeline(cfg: Config, **override) -> Pipeline:
    """`override` permet d'injecter des adaptateurs (tests, intégration dans un autre outil)."""
    exs = []
    if cfg.extract.regex:
        exs.append(RegexExtractor(cfg.extract.regex))
    if cfg.extract.gazetteer:
        exs.append(GazetteerExtractor(cfg.extract.gazetteer_min_len))
    if cfg.extract.gliner:
        exs.append(GlinerExtractor.from_config(cfg.extract.gliner))
    exs += [_plugin("mail2graph.extractors", n)(cfg) for n in cfg.extract.plugins]
    return Pipeline(
        cfg=cfg,
        source=override.get("source") or _source(cfg),
        store=override.get("store") or _store(cfg),
        queue=override.get("queue") or _queue(cfg),
        state=override.get("state") or JsonState(Path(cfg.root) / cfg.paths.state),
        linker=override.get("linker") or FuzzyLinker(),
        extractors=override.get("extractors") if override.get("extractors") is not None else exs,
    )

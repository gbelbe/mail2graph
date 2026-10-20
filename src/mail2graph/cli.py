"""Interface en ligne de commande : contrat stable (options, sortie JSON, codes de sortie) pour tout orchestrateur.

Codes de sortie : 0 succès ; 1 erreur d'exécution ; 2 erreur de configuration ; 3 relecture en attente (--fail-if-pending).
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import typer

from .config import Config
from .factory import build_pipeline

app = typer.Typer(help="Connecteur courriel -> graphe RDF avec relecture humaine.", no_args_is_help=True)
CONFIG = typer.Option("mail2graph.yaml", "--config", "-c", help="Fichier de configuration YAML.")
JSON = typer.Option(False, "--json", help="Sortie JSON lisible par machine.")


def _load(path: str) -> Config:
    try:
        return Config.load(Path(path))
    except Exception as e:  # fichier absent ou invalide
        typer.echo(f"Configuration invalide : {e}", err=True)
        raise typer.Exit(2)


def _out(data: dict, as_json: bool, text: str) -> None:
    typer.echo(json.dumps(data, ensure_ascii=False) if as_json else text)


@app.command()
def run(config: str = CONFIG, json_: bool = typer.Option(False, "--json"),
        fail_if_pending: bool = typer.Option(False, "--fail-if-pending")) -> None:
    """Interroge la boîte, extrait, lie, et dépose des propositions à relire."""
    p = build_pipeline(_load(config))
    rep = p.run()
    pending = len(p.queue.pending())
    _out({**asdict(rep), "pending": pending}, json_,
         f"{rep.fetched} lus, {rep.skipped_known} déjà vus, {rep.skipped_filtered} filtrés, "
         f"{rep.new_propositions} nouvelles propositions ({pending} en attente de relecture).")
    if fail_if_pending and pending:
        raise typer.Exit(3)


@app.command()
def review(config: str = CONFIG, json_: bool = typer.Option(False, "--json"),
           accept: list[str] = typer.Option([], "--accept", help="Identifiant à accepter (répétable)."),
           reject: list[str] = typer.Option([], "--reject", help="Identifiant à rejeter (répétable)."),
           accept_all: bool = typer.Option(False, "--accept-all", help="Accepte toutes les propositions en attente."),
           note: str = typer.Option("", "--note")) -> None:
    """Liste les propositions en attente, ou enregistre des décisions."""
    p = build_pipeline(_load(config))
    ids = [x.id for x in p.queue.pending()]
    for pid in (ids if accept_all else accept):
        p.queue.decide(pid, True, note)
    for pid in reject:
        p.queue.decide(pid, False, note)
    pend = p.queue.pending()
    _out({"pending": [asdict(x) for x in pend]}, json_,
         "\n".join(f"{x.id}  {x.kind:<10} {x.payload.get('subject') or x.payload.get('entity_label') or x.payload.get('label')}"
                   f"  ({x.confidence:.2f}) {x.note}" for x in pend) or "Rien en attente.")


@app.command()
def commit(config: str = CONFIG, json_: bool = typer.Option(False, "--json")) -> None:
    """Écrit dans le graphe les propositions acceptées."""
    n = build_pipeline(_load(config)).commit()
    _out({"committed": n}, json_, f"{n} éléments ajoutés au graphe.")


@app.command()
def check(config: str = CONFIG) -> None:
    """Valide la configuration et affiche ce que le graphe expose (classes, entités)."""
    cfg = _load(config)
    ctx = build_pipeline(cfg).store.context()
    typer.echo(f"Configuration valide. Graphe : {len(ctx.classes)} classes, {len(ctx.entities)} entités liables.")


if __name__ == "__main__":
    app()

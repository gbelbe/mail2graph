"""mail2graph : connecteur courriel -> graphe RDF avec relecture humaine."""
from .config import Config
from .domain import Decision, Mention, Message, Proposition
from .factory import build_pipeline
from .pipeline import Pipeline

__all__ = ["Config", "Pipeline", "build_pipeline", "Message", "Mention", "Proposition", "Decision"]
__version__ = "0.1.0"

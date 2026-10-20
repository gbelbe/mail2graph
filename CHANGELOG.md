# Changelog

## Non publié

- Extracteur GLiNER optionnel (`extract.gliner`, extra `[ner]`) : étiquettes de la configuration ou classes du graphe.
- Score de mutation global vérifié en CI (`tools/check_mutation_score.py`).

## 0.1.0

- Cœur sans entrée-sortie, six ports, assemblage par configuration et entry points.
- Sources : IMAP (imap-tools), mbox, mémoire. Extraction : expressions régulières, gazetteer du graphe.
- Liaison floue (rapidfuzz), graphe Turtle (rdflib), file de relecture YAML, état JSON.
- CLI : `check`, `run`, `review`, `commit`, sortie `--json`.

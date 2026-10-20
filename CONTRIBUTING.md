# Contribuer

- Installer : `pip install -e '.[dev]'` puis `pytest`.
- Le cœur (`domain.py`, `pipeline.py`) ne doit importer aucun adaptateur ni faire d'entrée-sortie : toute nouvelle
  dépendance externe passe par un port dans `ports.py` et un adaptateur dans `adapters/`.
- Tout adaptateur ou règle nouvelle s'accompagne d'un test qui n'utilise pas le réseau.
- Ne jamais écrire dans le graphe le corps d'un message, une adresse ou un nom de personne physique.
- Les messages de commit décrivent le pourquoi, en français ou en anglais.

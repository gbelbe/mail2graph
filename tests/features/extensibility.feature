# language: fr
@extensibility
Fonctionnalité: Extension par plugins et injection d'adaptateurs
  Pour adapter le connecteur à d'autres boîtes, extracteurs ou graphes
  En tant qu'intégrateur
  Je veux remplacer un adaptateur sans modifier le cœur

  Scénario: Une source fournie par un plugin
    Étant donné un paquet déclarant une source dans le groupe "mail2graph.sources"
    Quand la configuration indique ce type de source
    Alors le pipeline lit les messages de ce plugin

  Scénario: Un extracteur de plugin s'ajoute aux extracteurs intégrés
    Étant donné un extracteur de plugin renvoyant la mention "Cabinet Durand"
    Quand je l'active dans "extract.plugins"
    Alors ses mentions sont liées comme celles des extracteurs intégrés

  Scénario: Un adaptateur inconnu produit une erreur claire
    Quand la configuration nomme un plugin inexistant
    Alors l'erreur indique le nom du plugin et son groupe

  Scénario: Injection d'adaptateurs en bibliothèque
    Étant donné une source et un extracteur construits par l'appelant
    Quand j'appelle "build_pipeline" avec ces adaptateurs
    Alors le pipeline les utilise à la place de ceux de la configuration

  Scénario: Le cœur n'importe aucun adaptateur
    Alors "domain.py", "ports.py" et "pipeline.py" n'importent rien de "mail2graph.adapters"

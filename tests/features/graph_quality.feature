# language: fr
@graph
Fonctionnalité: Qualité du graphe produit
  Pour que les ajouts restent cohérents avec l'ontologie
  En tant que responsable du graphe
  Je veux valider ce qui est écrit

  Contexte:
    Étant donné un passage "run" ayant produit un courriel, deux liens et un événement

  @wip
  Scénario: Les classes et propriétés configurées existent dans l'ontologie
    Étant donné une configuration dont la classe de courriel est absente de l'ontologie
    Quand je lance "check"
    Alors un avertissement nomme la classe manquante

  @wip
  Scénario: La sortie respecte les contraintes SHACL
    Étant donné des formes SHACL pour courriel, lien et événement
    Quand je lance "commit"
    Alors le fichier de sortie est conforme avant d'être écrit

  Scénario: Les fichiers sources du graphe ne sont jamais modifiés
    Quand je lance "commit"
    Alors seuls le fichier de sortie configuré et la file de relecture changent

  Scénario: Un événement est daté de la réception
    Quand j'accepte un événement
    Alors il porte la date du message et une provenance vers le courriel

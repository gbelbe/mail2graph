# language: fr
@review
Fonctionnalité: Relecture humaine et écriture dans le graphe
  Pour que rien n'entre dans le graphe sans décision humaine
  En tant que relecteur
  Je veux accepter ou rejeter chaque proposition avant l'écriture

  Contexte:
    Étant donné un passage "run" ayant produit un courriel, deux liens et un événement

  Scénario: Rien n'est écrit sans acceptation
    Quand je lance "commit" sans avoir rien accepté
    Alors le fichier de sortie ne contient aucun triplet

  Scénario: Une proposition acceptée est écrite avec sa provenance
    Quand j'accepte le courriel et un lien puis je lance "commit"
    Alors le fichier de sortie contient le courriel typé avec sa date et son hachage
    Et il contient le lien vers l'entité acceptée
    Et il n'est pas modifié dans les fichiers sources du graphe

  Scénario: Une proposition rejetée n'est jamais écrite
    Quand je rejette un lien puis je lance "commit"
    Alors ce lien n'apparaît pas dans le fichier de sortie

  Scénario: Un enfant sans courriel accepté n'est pas écrit
    Quand j'accepte un lien sans accepter son courriel puis je lance "commit"
    Alors aucun triplet n'est écrit

  Scénario: Relancer "run" ne duplique rien
    Quand je relance "run" avec les mêmes messages
    Alors le nombre de propositions en attente est inchangé

  Scénario: Une décision n'est pas appliquée deux fois
    Quand j'accepte le courriel, je lance "commit" puis je relance "commit"
    Alors la deuxième écriture n'ajoute aucun triplet

  Scénario: Accepter tout
    Quand je lance "review --accept-all" puis "commit"
    Alors toutes les propositions sont au statut "committed"

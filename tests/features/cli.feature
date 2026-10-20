# language: fr
@cli
Fonctionnalité: Interface en ligne de commande
  Pour qu'un orchestrateur puisse appeler le module sans le connaître
  En tant qu'intégrateur
  Je veux un contrat stable de commandes, de sorties JSON et de codes de sortie

  Scénario: Une configuration invalide
    Quand je lance "check" avec un fichier de configuration absent
    Alors le code de sortie est 2

  Scénario: "check" décrit ce que voit le module
    Quand je lance "check" avec une configuration valide
    Alors la sortie indique le nombre de classes et d'entités liables
    Et le code de sortie est 0

  Scénario: "run --json" produit un rapport lisible par machine
    Quand je lance "run --json"
    Alors la sortie est un objet JSON avec "fetched", "new_propositions" et "pending"

  Scénario: "--fail-if-pending" signale un travail de relecture
    Étant donné qu'il reste des propositions en attente
    Quand je lance "run --fail-if-pending"
    Alors le code de sortie est 3

  Scénario: "review" liste sans modifier
    Étant donné qu'il reste des propositions en attente
    Quand je lance "review --json"
    Alors la sortie liste les propositions en attente
    Et aucune décision n'est enregistrée

  Scénario: Une décision sur un identifiant inconnu
    Quand je lance "review --accept inconnu"
    Alors le code de sortie est différent de 0

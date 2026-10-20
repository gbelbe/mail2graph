# language: fr
@linking
Fonctionnalité: Extraction et liaison aux entités du graphe
  Pour relier chaque courriel aux objets qu'il concerne
  En tant qu'opérateur
  Je veux des propositions de liens avec un niveau de confiance

  Contexte:
    Étant donné un graphe contenant la mairie "Mairie de Plonéour-Lanvern" et le dossier "DP 029 174 26 00122"

  Scénario: Un numéro de dossier est relié à son entité
    Étant donné un message qui cite "DP 029 174 26 00122"
    Quand je lance "run"
    Alors une proposition "link" vers l'entité du dossier est créée avec un score de 1,00

  Scénario: Un libellé connu du graphe est repéré sans règle spéciale
    Étant donné un message qui cite "la Mairie de Plonéour-Lanvern"
    Quand je lance "run"
    Alors une proposition "link" vers l'entité de la mairie est créée

  Scénario: Une correspondance incertaine est signalée
    Étant donné un message qui cite "Mairie de Ploneour Lanvern" avec une faute
    Quand je lance "run"
    Alors la proposition "link" porte la note "Correspondance incertaine"

  Scénario: Une organisation inconnue devient une nouvelle entité proposée
    Étant donné que la nature "organisation" est configurée pour la classe "Organisme"
    Et un message qui cite "Cabinet Durand", absent du graphe
    Quand je lance "run"
    Alors une proposition "new_entity" "Cabinet Durand" de classe "Organisme" est créée

  Scénario: Une mention dont la nature n'est pas configurée ne crée pas d'entité
    Étant donné un message qui cite "Société Inconnue" détecté avec la nature "autre"
    Quand je lance "run"
    Alors aucune proposition "new_entity" n'est créée

  Scénario: Deux entités de même libellé
    Étant donné deux entités du graphe portant le libellé "Phoenix France Infrastructures"
    Et un message qui cite "Phoenix France Infrastructures"
    Quand je lance "run"
    Alors les deux entités sont proposées pour relecture
    Et la proposition signale l'ambiguïté

  Scénario: Un lien n'est proposé qu'une fois par entité et par message
    Étant donné un message qui cite deux fois "DP 029 174 26 00122"
    Quand je lance "run"
    Alors une seule proposition "link" vers cette entité est créée

# language: fr
@ingestion
Fonctionnalité: Ingestion des courriels
  Pour ne traiter chaque message qu'une fois et ne retenir que le texte utile
  En tant qu'opérateur du connecteur
  Je veux que le pipeline nettoie, filtre et dédoublonne les messages

  Contexte:
    Étant donné un graphe contenant la mairie "Mairie de Plonéour-Lanvern" et le dossier "DP 029 174 26 00122"

  Scénario: Un message déjà traité est ignoré
    Étant donné un message "<1@x>" déjà traité lors d'un passage précédent
    Quand je lance "run" avec ce même message
    Alors le rapport indique 1 message déjà vu
    Et aucune proposition n'est créée

  Scénario: Les citations et la signature ne sont pas analysées
    Étant donné un message dont le corps cite "DP 029 174 26 00122" uniquement dans une citation précédée de ">"
    Quand je lance "run"
    Alors aucun lien vers le dossier "DP 029 174 26 00122" n'est proposé

  Scénario: Un expéditeur non autorisé est filtré
    Étant donné que la configuration n'autorise que le domaine "mairie.fr"
    Et un message envoyé par "inconnu@autre.fr"
    Quand je lance "run"
    Alors le rapport indique 1 message filtré
    Et le message est tout de même marqué comme traité

  Scénario: Un motif d'objet filtre les messages sans rapport
    Étant donné que la configuration exige un objet contenant "DP"
    Et un message d'objet "Newsletter"
    Quand je lance "run"
    Alors le rapport indique 1 message filtré

  @imap
  Scénario: La lecture de la boîte ne modifie rien
    Étant donné une boîte IMAP de test contenant 3 messages non lus
    Quand je lance "run"
    Alors les 3 messages sont toujours non lus et toujours dans leur dossier

  @imap
  Scénario: Le mot de passe vient d'une commande, jamais du fichier
    Étant donné une configuration avec "password_cmd"
    Quand je lance "run"
    Alors le secret n'apparaît ni dans les journaux ni dans la sortie JSON

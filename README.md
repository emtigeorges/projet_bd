# Projet ANFR — Carte interactive des supports radioélectriques

### 1\. La structure globale du code

"carte.py" : script Python principal découpé en 4 blocs :


&#x09;Chargement : lecture des tables ANFR (data et ref) via la fonction lire()


&#x09;Traitement \& Agrégation : conversion des coordonnées GPS, regroupement par support (SUP\\\_ID) des antennes, technologies et bandes de fréquences via joindre()


&#x09;Classification : tri des opérateurs (Orange, SFR, Bouygue, Free, Autres) et extraction des générations (2G, 3G, 4G, 5G)


&#x09;Cartographie : génération de la carte interactive carte.html avec folium et ouverture dans le navigateur


&#x09;"carte.html" : carte générée localement à l'exécution du script

### 2\. LA démarche algoritmique

Normalisation : lecture des identifiants ("STA\\\_NM\\\_ANFR") en texte ("str") pour conserver les zéros initiaux et mise en majuscules des colonnes


Jointure : regroupement des tables filles par "SUP\\\_ID" ("groupby" + suppression des doublons) avant les "merge" afin d'éviter la multiplication des lignes


Optimisation: utilisation de "FastMarkerCluster" avec un rendu Canvas, chargement progressif ("chunkedLoading") et calques par opérateur masqués au démarrage pour fluidifier le navigateur.

### 3\. les contraintes pour les utilisateurs externes

Python : installer les bibliothèques nécessaires avec :

```
  pip install pandas 
  pip install folium
  ```

Données ANFR non incluses : télécharger les fichiers CSV/TXT de l'ANFR (dossiers data et ref`)
IMPORTANT : modifier les chemins aux lignes 9 et 10 de "carte.py" (data = r"..." et ref = r"...").

Réseau : une connexion Internet est nécessaire pour afficher le fond de carte Esri dans le navigateur.


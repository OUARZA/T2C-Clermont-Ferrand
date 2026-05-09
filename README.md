# T2C Clermont-Ferrand

Intégration Home Assistant personnalisée pour afficher les prochains passages T2C de Clermont-Ferrand.

Cette version utilise les données ouvertes officielles Clermont Auvergne Métropole :

- GTFS statique pour charger les lignes et les arrêts dans le flux de configuration ;
- GTFS-RT Trip Updates pour les prochains départs en temps réel ;
- page QR T2C en secours si le flux temps réel ne contient aucun départ pour l'arrêt choisi.

## Installation via HACS

1. HACS > Intégrations > Menu ⋮ > Dépôts personnalisés
2. Ajouter l'URL de ce dépôt GitHub
3. Catégorie : Intégration
4. Installer `T2C Clermont-Ferrand`
5. Redémarrer Home Assistant
6. Paramètres > Appareils et services > Ajouter une intégration > T2C Clermont-Ferrand

## Installation manuelle

Copier le dossier :

```text
custom_components/t2c_clermontferrand
```

dans :

```text
/config/custom_components/t2c_clermontferrand
```

Puis redémarrer Home Assistant.

## Configuration

Depuis Home Assistant :

1. Paramètres > Appareils et services > Ajouter une intégration.
2. Choisir `T2C Clermont-Ferrand`.
3. Sélectionner la ligne.
4. Sélectionner l'arrêt et la direction.

L'intégration crée un capteur `Prochain passage` dont l'état est le temps d'attente du prochain départ en minutes. Les attributs exposent la ligne, la direction, l'arrêt, la destination, le statut temps réel et la liste des prochains passages.

## Diagnostics

Home Assistant peut exporter les diagnostics de l'entrée de configuration. Ils contiennent la configuration de l'arrêt, l'état du coordinateur et quelques informations sur l'index GTFS chargé.

## Notes

Le domaine Home Assistant reste `t2c_clermontferrand`. Les mises à jour sont coordonnées par `DataUpdateCoordinator` avec un rafraîchissement par défaut toutes les minutes.

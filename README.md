# T2C Clermont-Ferrand

Intégration Home Assistant personnalisée pour afficher les prochains passages T2C de Clermont-Ferrand.

Cette version utilise les données ouvertes officielles Clermont Auvergne Métropole :

- GTFS statique pour charger les lignes et les arrêts dans le flux de configuration ;
- GTFS-RT Trip Updates pour les prochains départs en temps réel.

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
4. Sélectionner la direction.
5. Sélectionner l'arrêt.

L'intégration crée :

- un capteur `Prochain passage`, dont l'état est le temps d'attente du prochain départ en minutes ;
- un capteur `Passages disponibles`, dont les attributs contiennent une liste `departures` prête pour un affichage en tableau ;
- des capteurs `Passage 1` à `Passage 5`, exposés comme timestamps Home Assistant.

## Exemple d'affichage

Une carte Markdown peut afficher les prochains passages sous forme de tableau :

```yaml
type: markdown
title: Prochains passages T2C
content: >
  | Ligne | Destination | Départ | Info |
  |---|---|---:|---|
  {% for departure in state_attr('sensor.t2c_b_les_chapelles_passages_disponibles', 'departures') or [] %}
  | {{ departure.ligne }} | {{ departure.destination }} | {{ departure.depart }} | {{ departure.info }} |
  {% endfor %}
```

Remplacer `sensor.t2c_b_les_chapelles_passages_disponibles` par l'entité créée chez vous.

## Diagnostics

Home Assistant peut exporter les diagnostics de l'entrée de configuration. Ils contiennent la configuration de l'arrêt, l'état du coordinateur et quelques informations sur l'index GTFS chargé.

## Notes

Le domaine Home Assistant reste `t2c_clermontferrand`. Les mises à jour sont coordonnées par `DataUpdateCoordinator` avec un rafraîchissement par défaut toutes les minutes.

# T2C Clermont-Ferrand

<img src="logo.png" alt="Logo T2C Clermont-Ferrand" width="100">

Intégration Home Assistant personnalisée pour suivre les prochains passages du
réseau T2C de Clermont-Ferrand.

L'intégration expose les passages d'une ligne à un arrêt, les perturbations de
ligne, les informations réseau générales, ainsi que des attributs détaillés
utilisables dans des cartes Lovelace personnalisées.

## Fonctionnalités

- Configuration depuis l'interface Home Assistant.
- Sélection d'une ligne, d'une direction, d'un arrêt et du nombre de passages.
- Un seul service Home Assistant `T2C - Clermont-Ferrand` pouvant contenir
  plusieurs arrêts suivis.
- Capteur global `Informations réseau` pour les messages applicables à tout le
  réseau.
- Capteurs de passage individuels `Passage 1`, `Passage 2`, etc.
- Attributs riches sur chaque passage : ligne, destination, horaires, statut,
  couleurs officielles de ligne et alertes applicables.
- Capteur `Perturbations ligne` avec état court et détails complets en attributs.
- Support des passages annulés et des horaires théoriques affichés avec `*`.

## Sources de données

L'intégration utilise plusieurs sources officielles T2C / transport.data.gouv.fr.

| Usage | URL |
| --- | --- |
| Métadonnées GTFS | `https://www.data.gouv.fr/api/1/datasets/syndicat-mixte-des-transports-en-commun-de-lagglomeration-clermontoise-smtc-ac-reseau-t2c-gtfs-gtfs-rt/` |
| GTFS-Realtime Trip Updates | `https://proxy.transport.data.gouv.fr/resource/t2c-clermont-gtfs-rt-trip-update?token=xdgqKBTAzhw4DSPz6zeGc4c5eW0LhwztcGv4-vpzP4U` |
| Prochains passages QR Code | `https://qrcode.t2c.fr/api/timetable?_stop_code={stop_id}&_limit={limit}` |
| Perturbations d'une ligne | `https://api.t2c.fr/siv/alerts/by-line/{line_id}?type=Trafic` |
| Informations réseau | `https://api.t2c.fr/siv/alerts/banners` |

Le flux QR Code renvoie les passages affichés par les panneaux T2C. Le GTFS
statique est utilisé pour les sélecteurs, les couleurs de ligne et la
correspondance entre le nom public de ligne (`E4`) et l'identifiant API interne
(`9`).

## Installation via HACS

1. Ouvrir HACS.
2. Aller dans `Intégrations`.
3. Menu `...` > `Dépôts personnalisés`.
4. Ajouter l'URL de ce dépôt.
5. Choisir la catégorie `Intégration`.
6. Installer `T2C Clermont-Ferrand`.
7. Redémarrer Home Assistant.
8. Aller dans `Paramètres > Appareils et services > Ajouter une intégration`.
9. Choisir `T2C Clermont-Ferrand`.

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

1. Ajouter l'intégration `T2C Clermont-Ferrand`.
2. Sélectionner une ligne.
3. Sélectionner une direction.
4. Sélectionner un arrêt.
5. Choisir le nombre de prochains passages à afficher.

Si une entrée `T2C - Clermont-Ferrand` existe déjà, un nouvel arrêt est ajouté
au même service au lieu de créer une nouvelle entrée séparée.

## Appareils et entités

L'intégration crée un appareil par arrêt suivi, nommé par exemple :

```text
Ligne B - Direction ROYAT Pl. Allard - Arrêt Les Chapelles
```

Elle crée aussi un appareil global :

```text
Informations réseau
```

### Entités par arrêt

| Entité | Etat | Description |
| --- | --- | --- |
| `Prochain passage` | Minutes | Temps restant avant le prochain passage non annulé. |
| `Passages disponibles` | Nombre | Nombre de passages actuellement fournis par l'API. |
| `Perturbations ligne` | Titre ou `Aucune perturbation` | Première perturbation de la ligne configurée. |
| `Passage 1` | Temps restant | Premier passage. |
| `Passage 2..X` | Heure de passage | Passages suivants. |

Les anciennes entités `Info passage X` ne sont plus créées. Les informations
sont maintenant directement disponibles dans les attributs de chaque `Passage X`.

### Entité réseau

| Entité | Etat | Description |
| --- | --- | --- |
| `Informations réseau` | Message réseau ou `Pas d'information du réseau T2C` | Messages globaux du réseau T2C. |

## Attributs des passages

Chaque capteur `Passage X` expose notamment :

| Attribut | Description |
| --- | --- |
| `line` | Nom court affichable de la ligne, par exemple `B`, `C`, `E4`. |
| `route_id` | Identifiant API / GTFS réel, par exemple `9` pour `E4`. |
| `route_color` | Couleur officielle de la ligne, format CSS `#rrggbb`. |
| `route_text_color` | Couleur officielle du texte de ligne. |
| `direction` | Direction configurée dans l'intégration. |
| `stop` | Nom de l'arrêt. |
| `stop_id` | Identifiant de l'arrêt. |
| `destination` | Destination du passage. |
| `label` | Libellé lisible du passage. |
| `due_at` | Heure de passage utilisée. |
| `scheduled_at` | Heure théorique. |
| `estimated_at` | Heure estimée temps réel si disponible. |
| `minutes` | Temps restant en minutes. |
| `info` | Information courte du passage, ou `Aucune info`. |
| `status` | Statut brut du passage, par exemple `onTime` ou `cancelled`. |
| `theoretical` | `true` si l'horaire est théorique. |
| `realtime` | `true` si une estimation temps réel est disponible. |
| `trip_id` | Identifiant de course si disponible. |
| `vehicle_id` | Identifiant véhicule si disponible. |
| `has_alert` | `true` si une alerte semble applicable au passage. |
| `alert_icon` | Icône suggérée, actuellement `mdi:alert-circle`. |
| `alert_title` | Titre de l'alerte applicable. |
| `alert_text` | Texte de l'alerte applicable. |
| `updated_at` | Date de mise à jour de l'alerte applicable. |
| `alerts` | Liste brute des alertes applicables au passage. |

## Attribut `departures`

Le capteur `Passages disponibles` expose un attribut `departures`, pratique pour
construire un tableau Lovelace.

Chaque ligne contient notamment :

```yaml
ligne: B
couleur_ligne: "#0069b4"
couleur_texte_ligne: "#ffffff"
destination: ROYAT Pl. Allard
depart: 17:20
info: Aucune info
has_alert: false
alert_icon: null
alert_title: null
alert_text: null
alert_updated_at: null
etat: onTime
theorique: false
temps_reel: true
```

## Perturbations

### Perturbations de la ligne configurée

Le capteur `Perturbations ligne` expose :

- état : premier titre d'alerte, ou `Aucune perturbation` ;
- attribut `alerts` : liste complète des alertes de la ligne ;
- attributs `title`, `text`, `type`, `level`, `priority`, `updated_at`,
  `affected_routes`.

L'état est volontairement court pour respecter la limite Home Assistant de 255
caractères.

### Alertes par passage

Les passages peuvent appartenir à une autre ligne que celle configurée lorsque
l'API QR Code renvoie plusieurs lignes sur le même arrêt. L'intégration tente de
rattacher chaque passage à l'alerte de sa propre ligne :

- mapping du nom public vers l'identifiant réel (`E4` -> `9`) ;
- récupération des alertes via `alerts/by-line/{route_id}` ;
- filtrage simple pour éviter les alertes d'un autre sens lorsque l'alerte
  mentionne une direction différente.

Ces informations sont exposées via `has_alert`, `alert_icon`, `alert_title`,
`alert_text` et `alerts`.

## Informations réseau

L'entité `Informations réseau` utilise :

```text
https://api.t2c.fr/siv/alerts/banners
```

Elle sert aux messages globaux comme :

```text
Le jeudi 14 mai 2026, vous devrez être en possession d'un titre de transport valide.
La gratuité ne s'applique pas la semaine.
```

## Exemple Lovelace

Exemple minimal avec une carte Markdown :

```yaml
type: markdown
title: Prochains passages T2C
content: |
  {% set passages = state_attr('sensor.votre_entite_passages_disponibles', 'departures') or [] %}

  | Ligne | Destination | Départ | Info |
  |:---:|:---|---:|:---:|
  {% for passage in passages %}
  | {{ passage.ligne }} | {{ passage.destination }} | {{ passage.depart }} | {{ passage.info }} |
  {% endfor %}
```

Pour une carte personnalisée, utilisez `has_alert` et `alert_icon` pour afficher
une icône, puis `alert_title` / `alert_text` pour un tooltip.

## Diagnostics

Home Assistant peut exporter les diagnostics de l'entrée de configuration. Ils
contiennent notamment :

- les données de configuration de l'entrée ;
- le nombre d'arrêts suivis ;
- l'état des coordinateurs ;
- quelques informations sur l'index GTFS chargé.

## Notes techniques

- Domaine Home Assistant : `t2c_clermontferrand`.
- Version actuelle : `0.2.0`.
- Rafraîchissement par défaut : toutes les minutes.
- Type d'intégration : `service`.
- Classe IoT : `cloud_polling`.

L'intégration dépend de :

```text
gtfs-realtime-bindings==1.0.0
```

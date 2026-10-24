# T2C Clermont-Ferrand

<img src="logo.png" alt="Logo T2C Clermont-Ferrand" width="100">

Intégration Home Assistant personnalisée pour suivre les prochains passages du
réseau T2C de Clermont-Ferrand.

La carte Lovelace est maintenant incluse : une seule installation HACS fournit les
deux composants. Voir [l’installation commune](#installation-commune--intégration-et-carte)
et [la migration de l’ancienne carte](#migration-depuis-la-carte-hacs-séparée).

L'intégration expose les passages d'une ligne à un arrêt, les perturbations de
ligne, les informations réseau générales, ainsi que des attributs détaillés
utilisables dans des cartes Lovelace personnalisées.

## Nouveautés de la version 0.2.13

- Migration des passages vers l’API du site officiel T2C ; suppression des appels QR Code.
- Récupération des horaires détaillés par ligne pour dépasser les trois passages
  par sens de la synthèse et remplir le nombre demandé, si le service le permet.
- Six passages par défaut pour les nouveaux arrêts ; limites existantes conservées.
- Horaires théoriques disponibles en l’absence d’estimation temps réel, notamment
  aux Chapelles vers Royat. Distinction explicite pour chaque passage.
- Tri chronologique selon l’heure effectivement utilisée et conservation des
  courses à terminus intermédiaire dans la direction configurée.
- Alertes rattachées à la ligne, comme dans le panneau de course de la cartographie T2C.
- Configuration, identifiants d’entités et attributs utilisés par la carte conservés.

### Mise à jour depuis 0.2.12

Installer la mise à jour, puis redémarrer Home Assistant. Les arrêts déjà
configurés sont conservés ; aucune suppression ni recréation n’est nécessaire.
Un arrêt réglé sur cinq passages reste réglé sur cinq. La carte Lovelace est désormais fournie par cette intégration (voir migration ci-dessous).

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
- Support des passages annulés et distinction théorique / temps réel dans les attributs.

## Sources de données

L'intégration utilise plusieurs sources officielles T2C / transport.data.gouv.fr.

| Usage | URL |
| --- | --- |
| Métadonnées GTFS | `https://www.data.gouv.fr/api/1/datasets/syndicat-mixte-des-transports-en-commun-de-lagglomeration-clermontoise-smtc-ac-reseau-t2c-gtfs-gtfs-rt/` |
| Prochains passages de la ligne configurée | `https://api.t2c.fr/siv/stops/{parent_stop_id}/routes/{route_id}/departures?dateTime={date_iso_encodee}&direction={direction_id}` |
| Référence du quai | `https://api.t2c.fr/siv/stops/{stop_id}` |
| Perturbations d'une ligne | `https://api.t2c.fr/siv/alerts/by-line/{line_id}?type=Trafic` |
| Informations réseau | `https://api.t2c.fr/siv/alerts/banners` |

Les passages proviennent de l’API du site officiel. À chaque requête,
`dateTime` contient la date et l’heure courantes en ISO 8601 avec fuseau
Europe/Paris, encodées comme paramètre d’URL (`+` devient `%2B`).
Sans ce paramètre obligatoire, le serveur renvoie une erreur 400.

L’arrêt parent est résolu par `parent_station` dans le GTFS statique, puis,
si nécessaire, par la référence officielle du quai (`parent_station` ou
`parent_stop_id`). Exemple : `CHAPB → CHAP`. Aucun identifiant n’est tronqué.
La configuration conserve le quai et la direction déjà enregistrés : aucune
reconfiguration ni modification des identifiants d’entités n’est nécessaire.
Le GTFS fournit également les sélecteurs, les couleurs et les noms de ligne.

Les passages de la réponse détaillée sont filtrés par ligne, quai et
`trip_direction_id`. Le paramètre `direction` est envoyé même pour le sens `0`.
Aucun filtre `headline` n’est envoyé, afin de conserver les terminus intermédiaires.
Le nom de destination ne sert pas de filtre : un terminus intermédiaire tel
que Jules Verne reste admissible dans le même sens qu’Aulnat.
Tous les passages retenus sont triés par heure effective avant la limite
configurée. Le serveur peut fournir moins de passages que cette limite.

L’endpoint de synthèse `/siv/stops/{parent_stop_id}/departures` ne fournit
que trois passages par sens dans les réponses observées (six en additionnant
les deux sens). L’intégration utilise donc l’endpoint détaillé par ligne :
sept départs vers Aulnat à Jaude et six vers Royat aux Chapelles ont été
observés le 15 octobre 2026. Six n’est pas une limite générale de l’API.
La synthèse reste disponible uniquement pour les appels du client sans ligne.

### Horaires théoriques et temps réel

- `scheduled_at` reprend `theorical_departure_datetime` (orthographe API).
- `estimated_at` reprend `real_time_stop_time` si la date est valide et le
  statut est `scheduled`, confirmé avec des estimations réelles.
- `no_data`, une estimation absente/invalide ou un statut inconnu entraînent
  un repli théorique. Le champ `real_time: true` ne suffit pas.
- `due_at` est l’estimation valide, sinon l’horaire théorique. Les minutes
  sont calculées depuis cet instant. Les dates sont restituées en Europe/Paris.
- Pour chaque passage : estimation utilisée → `realtime: true`,
  `theoretical: false` ; horaire théorique utilisé → `realtime: false`,
  `theoretical: true`, `estimated_at: null`.
- `cancelled` et `skipped` sont affichés comme annulés par le site officiel.
  Ils deviennent `status: cancelled` pour les capteurs existants, restent dans
  la liste avec leur horaire théorique et sont exclus du capteur « Prochain passage ».
- `real_time_delay` correspond dans les réponses observées à un décalage en
  secondes, positif ou négatif. Le site utilise la date explicite : l’intégration
  ne fabrique jamais d’estimation en ajoutant ce délai à l’horaire théorique.

Une liste peut mélanger horaires théoriques et temps réel. Les attributs
des capteurs et les clés compactes `theorique` / `temps_reel` restent compatibles
avec la carte Lovelace fournie dans ce dépôt.

Les passages, les alertes et les informations réseau utilisent uniquement
`api.t2c.fr`. Le GTFS statique reste nécessaire aux références et aux sélecteurs.
Aucun appel au flux QR Code n’est effectué.

### Compatibilité des messages

L’attribut `messages` est conservé et alimenté par les alertes de la ligne
configurée, déjà récupérées pour `Perturbations ligne` : aucune requête
supplémentaire. Les champs `id`, `title`, `content`, `valid_from`, `valid_until`,
`line_refs`, `stop_refs` et `scope` sont conservés. Le contenu HTML est converti
en texte. La portée est explicitement `line` et `stop_refs` reste vide :
une alerte de ligne ne prouve pas qu’un quai précis est touché.

Les messages restent disponibles même sans prochain passage. En cas d’erreur
de récupération des alertes, `messages` et `alerts` sont vides, sans masquer
les passages. Les messages réseau restent sur leur entité dédiée.

Les réponses vérifiées des références d’arrêt et des alertes ne fournissent
pas d’équivalent confirmé à tous les messages spécifiques d’arrêt du QR Code.
Ces anciens messages ne sont donc plus récupérés ; cette migration ne garantit
pas une couverture identique. À Jaude, le message de travaux de la ligne C
est bien présent dans la nouvelle API, avec la seconde perturbation du bandeau.

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
5. Choisir le nombre de prochains passages à afficher, de 1 à 20, avec 6 par défaut.

Les limites déjà enregistrées sont conservées : un arrêt configuré sur 5
reste sur 5. La nouvelle récupération permet de remplir ces cinq passages
lorsque le service restant le permet.

Si une entrée `T2C - Clermont-Ferrand` existe déjà, un nouvel arrêt est ajouté
au même service au lieu de créer une nouvelle entrée séparée.

Pour supprimer un arrêt suivi, ouvrir l'intégration `T2C Clermont-Ferrand`,
cliquer sur `Configurer`, puis choisir l'arrêt à retirer.
Home Assistant peut aussi proposer la suppression directement depuis la fiche de
l'appareil de l'arrêt suivi.

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
| `Passages disponibles` | Nombre | Nombre de passages correspondant à la ligne et à la direction configurées. |
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
| `status` | Statut API (`scheduled`, `no_data`…), avec `skipped` normalisé en `cancelled`. |
| `theoretical` | `true` si l'horaire est théorique. |
| `realtime` | `true` si une estimation temps réel valide est utilisée. |
| `trip_id` | Identifiant de course si disponible. |
| `vehicle_id` | Identifiant véhicule si disponible. |
| `has_alert` | `true` si la ligne du passage possède au moins une alerte. |
| `alert_icon` | Icône suggérée, actuellement `mdi:alert-circle`. |
| `alert_title` | Titre de la première alerte de ligne. |
| `alert_text` | Texte de la première alerte de ligne. |
| `updated_at` | Date de mise à jour de la première alerte de ligne. |
| `alerts` | Liste compacte des alertes de la ligne du passage. |

### Distinguer les horaires dans une carte

Ces attributs sont propres à chaque passage : une liste peut mélanger les deux types.

| Type d’horaire utilisé | `realtime` | `theoretical` | `estimated_at` | `due_at` |
| --- | --- | --- | --- | --- |
| Estimation temps réel valide | `true` | `false` | Date estimée | Date estimée |
| Horaire théorique | `false` | `true` | `null` | Date théorique |

`scheduled_at` conserve la date théorique dans les deux cas. Dans l’attribut
compact `departures`, les indicateurs équivalents sont `temps_reel` et `theorique`.
Les heures sont affichées sans astérisque ; utilisez ces attributs pour distinguer
visuellement les horaires théoriques et temps réel dans une carte.

## Attribut `departures`

Le capteur `Passages disponibles` expose un attribut `departures`, pratique pour
construire un tableau Lovelace. Les passages sont filtrés puis triés par heure
effective avant d’appliquer le nombre demandé.

Pour éviter les avertissements Recorder de Home Assistant, cet attribut reste
compact : les données brutes complètes ne sont pas dupliquées et `alert_text`
est tronqué dans la liste `departures`.

Les capteurs `Passage X` conservent la couleur officielle de la ligne même
lorsqu'ils affichent `Fin de service`.

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
etat: scheduled
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

Les passages sont filtrés sur la ligne et la direction configurées, même lorsque
l’API du site renvoie plusieurs lignes au même arrêt. L'intégration rattache
ensuite chaque passage à l'alerte de sa ligne :

- mapping du nom public vers l'identifiant réel (`E4` -> `9`) ;
- récupération des alertes via `alerts/by-line/{route_id}` ;
- affichage de toutes les alertes de la ligne, même si leur texte concerne
  un autre arrêt ou l’autre direction, comme dans les exemples du site T2C.

Vérification dans la cartographie du site : la fiche de l’arrêt seul et la
liste des départs ne présentent pas ce bloc de perturbations. Il apparaît
dans le panneau de la course après sélection d’un départ. Les alertes
affichées sont celles de sa ligne, sans filtre supplémentaire par quai
ou direction. L’intégration dispose déjà de la ligne dans sa configuration ;
elle conserve donc aussi ces informations dans `Perturbations ligne` et
`messages` lorsqu’aucun départ n’est disponible.

Ainsi, un passage INSPÉ Chamalières vers Jules Verne affiche aussi l’alerte
de report vers Zone des Gravanches. `has_alert` signale une perturbation de
la ligne, sans garantir que ce passage précis est affecté. Le filtrage des
horaires par quai et identifiant de direction reste inchangé.

Ces informations sont exposées via `has_alert`, `alert_icon`, `alert_title`,
`alert_text` et `alerts`. Le détail complet des perturbations reste disponible
sur le capteur `Perturbations ligne`.

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
- Version actuelle : `0.2.13`.
- Rafraîchissement par défaut : toutes les minutes.
- Type d'intégration : `service`.
- Classe IoT : `cloud_polling`.

L'intégration dépend de :

```text
gtfs-realtime-bindings==1.0.0
```

## Validation de la migration

Les tests utilisent des réponses réelles des Chapelles, de Jaude et de Gare SNCF
capturées le 15 octobre 2026, complétées par des cas synthétiques (annulations,
terminus Jules Verne, désordre chronologique, erreurs et données invalides).
Voir [les observations et sources](tests/fixtures/README.md).

Avec Python 3.12 ou supérieur :

```sh
python -m pip install -r tests/requirements.txt
python -m unittest discover -s tests -v
```


## Installation commune : intégration et carte

Home Assistant **2026.10.0 minimum** pour cette version regroupée. Installer uniquement
**OUARZA/T2C-Clermont-Ferrand**, catégorie **Intégration** dans HACS, puis redémarrer
Home Assistant. Le dossier `custom_components/t2c_clermontferrand/www/` est inclus
avec l’intégration ; aucune installation Dashboard supplémentaire n’est nécessaire.
Après la configuration d’une entrée T2C, la carte est servie et sa ressource de type
module est créée automatiquement lorsque les ressources Lovelace sont gérées par l’interface.
Le rechargement d’une entrée et plusieurs entrées réutilisent le même chemin HTTP.
Les ressources restent présentes si la dernière entrée est déchargée, pour permettre
son rechargement ; elles ne sont pas supprimées automatiquement lors d’une désinstallation.

![Carte T2C](docs/card-preview.png)

Ajouter une carte « T2C Clermont-Ferrand Card » dans l’éditeur visuel, sélectionner
le capteur `passage_1`, puis ajuster les options. Les dashboards existants gardent
le même type et la même configuration :

```yaml
type: custom:t2c-clermontferrand-card
entity: sensor.ligne_b_direction_royat_pl_allard_arret_les_chapelles_passage_1
title: Les Chapelles
passages: 5
show_network_info: true
```

| Option | Défaut | Usage |
| --- | --- | --- |
| `entity` | obligatoire | Capteur passage_1 ; les autres passages utilisent son préfixe. |
| `title` | nom de l’arrêt | Titre personnalisé. |
| `passages` | 5 | Entre 1 et 6, limite identique dans l’éditeur et en YAML. |
| `show_network_info` | false | Informations générales du réseau. |
| `line` | détection automatique | Surcharge historique du libellé de ligne en YAML. |

L’éditeur visuel, les couleurs de lignes, les alertes au clic et l’icône verte de
temps réel sont conservés. Les horaires théoriques restent sans astérisque.

## Migration depuis la carte HACS séparée

1. Sauvegarder Home Assistant, noter les URL et types de ressources T2C existants,
   et conserver la version précédente de l’intégration et de la carte pour un retour arrière.
2. Installer cette version de l’intégration et redémarrer Home Assistant. Ne pas
   désinstaller la carte séparée avant d’avoir vérifié la ressource et l’affichage.
3. En gestion des ressources par l’interface, l’intégration remplace en place une
   ressource T2C reconnue, conserve son identifiant et retire ses doublons reconnus.
   Les autres ressources sont préservées. La ressource finale est de type module :
   `/t2c_clermontferrand/t2c_clermont-ferrand_card.js?v=<empreinte>`.
   L’empreinte du fichier renouvelle le cache à chaque changement du JavaScript.
4. Vérifier dans les ressources qu’une seule version T2C est active. Les chemins
   personnalisés non listés ci-dessous doivent être retirés manuellement **après
   vérification qu’ils correspondent bien à cette carte**. Ne pas retirer les autres cartes.
5. Fermer ou actualiser complètement **tous** les onglets et applications Companion
   utilisant les dashboards. Un composant déjà chargé dans un navigateur ne peut
   pas être remplacé à chaud : Ctrl+F5 ou fermeture/réouverture est nécessaire.
6. Tester l’affichage et l’éditeur. Ensuite seulement, désinstaller dans HACS l’ancien
   dépôt **T2C-Clermont-Ferrand-Card** (Dashboard), puis vérifier à nouveau les ressources.
   Ne pas réinstaller ou mettre à jour l’ancienne carte ensuite : HACS pourrait recréer
   son ancienne ressource. Si cela arrive, la retirer puis rafraîchir les navigateurs ;
   un rechargement de l’entrée T2C réconcilie aussi les chemins reconnus.

Les seuls anciens chemins migrés automatiquement sont les suivants ; les paramètres
`?v=…`, `?hacstag=…` et fragments sont ignorés pour les reconnaître :

- `/hacsfiles/T2C-Clermont-Ferrand-Card/t2c_clermont-ferrand_card.js`
- `/local/community/T2C-Clermont-Ferrand-Card/t2c_clermont-ferrand_card.js`
- `/local/community/t2c_clermontferrand_card/t2c_clermont-ferrand_card.js`
- `/local/community/t2c_clermontferrand_card/dist/t2c_clermont-ferrand_card.js`

Une URL externe ou un autre dossier n’est jamais supprimé sur la seule base du nom
JavaScript. Aucun fichier de l’ancienne carte ni fichier utilisateur n’est supprimé.

### Ressources gérées en YAML

La gestion des ressources est indépendante du mode du dashboard : un dashboard YAML
peut utiliser des ressources en stockage. Si les **ressources** sont en YAML,
l’intégration sert le fichier mais ne modifie ni leur collection ni les fichiers.
Un avertissement donne l’URL exacte avec empreinte dans les journaux au démarrage.
Remplacer manuellement les anciennes entrées de cette carte par **une seule** :

```yaml
lovelace:
  resource_mode: yaml
  resources:
    - url: /t2c_clermontferrand/t2c_clermont-ferrand_card.js?v=<empreinte_des_journaux>
      type: module
```

Adapter la section existante ou son fichier inclus ; ne pas dupliquer `lovelace:`.
Conserver toutes les autres ressources. Recharger les ressources Lovelace puis tous
les navigateurs. À chaque mise à jour de la carte, reporter la nouvelle empreinte
indiquée dans les journaux pour renouveler le cache.

### Retour arrière

Restaurer la sauvegarde est la solution complète. Sinon : réinstaller la précédente
version de l’intégration, réinstaller l’ancienne carte HACS si nécessaire, puis
retirer uniquement la ressource `/t2c_clermontferrand/t2c_clermont-ferrand_card.js`
et restaurer **une seule** ancienne ressource T2C (module) notée à l’étape 1.
Faire l’équivalent dans le YAML si nécessaire. Redémarrer Home Assistant et fermer
ou rafraîchir tous les navigateurs. Les configurations des cartes et les entités
n’ont pas à être recréées. Restaurer l’ancienne version de l’intégration avant
l’ancienne ressource évite que la migration ne la remplace à nouveau.

## Développement de la carte et distribution

La carte provient de la copie locale du dépôt séparé, `main` au commit
`ae1c932` (version 0.2.9), sans modifications non publiées lors de l’import.
Le JavaScript d’origine était déjà la source maintenue, sans bundler ni dépendance
externe. Il est désormais dans `frontend/src/t2c_clermont-ferrand_card.js`, avec
sa licence. L’éditeur est dans le même fichier. Aucun CDN ou paquet npm n’est requis.

Avec Node.js 22+, depuis `frontend/` :

```sh
npm run build
npm run check
npm test
```

La construction copie de façon déterministe la source dans le dossier `www/` de
l’intégration. Commiter **source et fichier construit** ensemble. Redémarrer Home
Assistant après le déploiement du fichier construit pour recalculer l’empreinte.
La garde du composant et de son éditeur empêche une double déclaration ; elle ne
remplace pas le retrait des ressources anciennes ni le rafraîchissement navigateur.

HACS reste en catégorie intégration, sans `zip_release` et sans filtre de fichiers :
il distribue le dossier complet `custom_components/t2c_clermontferrand/`, y compris
`www/`. Aucun workflow de release n’existait lors de ce regroupement. Les archives
GitHub des tags incluent le bundle commité ; aucune release n’est publiée par ce travail.
Si un ZIP dédié est ajouté ultérieurement, il devra inclure le dossier `www/` complet.
La CI vérifie source/bundle, tests Python/JS et contenu de l’archive Git, en plus
de HACS et hassfest. `python scripts/check_package.py` vérifie le **commit HEAD**.

Voir [la vérification des API et les tests sur instance](docs/bundled-card-validation.md)
et [le texte préparé pour l’ancien dépôt](docs/old-card-repository-notice.md).

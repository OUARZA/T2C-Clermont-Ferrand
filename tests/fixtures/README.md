# Observations du 15 octobre 2026

Réponses publiques capturées vers 20 h 54 (Europe/Paris), avec la date courante
encodée dans chaque requête. Les champs volumineux shapes et stops ont été
retirés des fixtures ; les lignes et next_departures sont conservés.

- chap.json : /siv/stops/CHAP/departures, CHAPB/B/0 vers Royat :
  trois passages théoriques, real_time=true, statut no_data, estimation null.
- jaud.json : /siv/stops/JAUD/departures, JAUDB/B/0 : une estimation
  scheduled et deux horaires no_data ; JAUDS/B/1 vers Aulnat est également mixte.
- gasn.json : /siv/stops/GASN/departures, GASNA/B/0 : même mélange.
  GASNR/B/1 contient aussi un délai non nul avec estimation null : ne pas
  reconstruire une estimation à partir du délai.
- chapb.json : [référence officielle](https://api.t2c.fr/siv/stops/CHAPB),
  parent_station=CHAP et parent_stop_id=CHAP.
- [QR Code CHAPB](https://qrcode.t2c.fr/api/timetable?_stop_code=CHAPB&_limit=5) :
  HTTP 200, timetable.timetable=[] et message=[]. Cela ne démontre pas que
  les messages sont absents sur tous les arrêts. Observation historique : les appels
  QR Code sont désormais supprimés.

## Code public du site vérifié

Le [service du site](https://www.t2c.fr/chunk-VSBTQ7X3.js), méthode
loadStopDetails, appelle /siv/stops/{stopId}/departures avec dateTime (le site
sérialise en UTCString ; l’intégration en ISO 8601, accepté par les essais API).
Il conserve real_time_stop_time et theorical_departure_datetime.

Les [composants horaires](https://www.t2c.fr/chunk-HD3ZZRYL.js) sélectionnent
real_time_stop_time si présent sauf pour cancelled/skipped, alors affichés
« Annulé ». Aucune utilisation de real_time_delay dans ces composants ni dans
le service. Dans les exemples réels, scheduled accompagne les estimations ;
no_data n’en fournit pas. Par prudence, un statut inconnu reste théorique.

Exemple Jaude/B/0 : théorique 19:08:00Z, estimation 19:03:13Z,
real_time_delay=-287, soit exactement la différence en secondes. D’autres
réponses ont un délai positif. Le délai seul ne valide pas une estimation.

La [documentation communautaire](https://dumb-software.github.io/T2C-API-Documentation/Yoozly/API_Server/)
a servi à repérer les endpoints ; les champs ont été vérifiés sur l’API et le site.
Les noms de modules du site peuvent changer à chaque déploiement.

## Limites de la validation

Aucune annulation ni course vers Jules Verne n’était présente dans les captures.
Ces cas sont testés synthétiquement avec les statuts confirmés dans le site et
les mêmes structures de réponse. Les listes mixtes et Aulnat sont testées avec
les réponses réelles. Les tests ne nécessitent pas un accès réseau et figent
l’heure au moment de la capture. Un contrôle visuel dans une instance
Home Assistant reste à effectuer.

## Migration des messages vers la même API

`line_c_alerts.json` contient les deux réponses de `/siv/alerts/by-line/C?type=Trafic`
vérifiées le 15 octobre 2026 : `1.33548.2` et `1.32583.2`, soit les deux
perturbations du bandeau de Jaude vers Durtol. Le test vérifie leur conversion
au format `messages`, avec `scope: line` et aucune référence de quai inventée.
Les réponses `/siv/stops/JAUDB`, `/siv/stops/JAUD` et `/siv/alerts` ont également
été inspectées : elles n’établissent pas une couverture complète des anciens
messages propres aux arrêts. Les tests du coordinateur vérifient la réutilisation
d’un seul appel d’alertes, les messages sans départs et les erreurs partielles.

## Vérification du filtrage du site officiel

Le 15 octobre 2026, le composant de détail de course Eo du module public
https://www.t2c.fr/chunk-HD3ZZRYL.js construit alertForCurrentRoute$ en
combinant la ligne courante et les alertes, puis applique uniquement :

```javascript
l.filter(m => m.affected_routes.includes(r.route_id))
```

Ce filtre ne consulte ni l’arrêt, ni la direction, ni le texte de l’alerte.
Le template Fs transmet cette liste au bandeau ; le bouton _s affiche le
premier titre et le nombre d’alertes supplémentaires. Cela confirme la règle
retenue dans l’intégration pour les deux pages de détail de course fournies
(Jaude/C/Durtol et INCH/10/Jules Verne). Cette première vérification portait sur le JavaScript livré par le site.
La vérification visuelle de la cartographie ci-dessous la complète.

## Vérification visuelle de la cartographie

Le 15 octobre 2026, après relecture des modifications existantes :

1. Ouverture de Horaires & plans puis du mode Carte.
2. Sélection d’INSPÉ Chamalières, consultation à 21 h 00 pour retrouver le
   départ de 21 h 16 : la fiche d’arrêt liste la ligne S11 (route_id 10)
   et Jules Verne, sans bloc de perturbations.
3. Clic sur Jules Verne : la liste des départs affiche 21 h 16 sans ce bloc.
4. Clic sur le départ de 21 h 16 : le panneau de la course affiche
   « Arrêt INSPÉ Chamalières direction Zone des Gravanches reporté le
   19 octobre 2026 », alors que le trajet sélectionné va vers Jules Verne.
5. Ouverture de la course Jaude/C/Durtol fournie par l’utilisateur :
   carte avec trajet tracé, perturbation boulevard Charles de Gaulle et +1.

L’affichage dépend donc de la sélection d’une course dans cette interface,
mais la portée des données est celle de la ligne. L’intégration conserve
ce rattachement. Le capteur de perturbations et messages reste accessible
même sans départ ; ce choix est explicite et couvert par les tests.

Aucune modification supplémentaire de logique n’a été nécessaire à l’issue
de cette vérification ; seules les explications ont été précisées.

## Départs détaillés au-delà des trois passages de synthèse

Le 15 octobre 2026 vers 21 h 48, avec dateTime courant encodé :

- Synthèse JAUD : A, B et C fournissent chacune trois passages par sens.
- `jaud_b_direction1.json` : /siv/stops/JAUD/routes/B/departures avec
  direction=1, sept départs sur le quai JAUDS vers Aulnat.
- `chap_b_direction0.json` : /siv/stops/CHAP/routes/B/departures avec
  direction=0, six départs sur CHAPB vers Royat.

Cet endpoint renvoie une liste plate, adaptée au parseur commun. Les tests
vérifient les limites 5, 6 et 20, le filtrage local ligne/quai/direction,
les terminus intermédiaires, une réponse vide et une erreur de récupération.
Le nombre renvoyé dépend du service restant, et ne prouve pas un maximum à 6.

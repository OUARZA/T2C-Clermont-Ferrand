# Vérifications du regroupement

## État inspecté avant modification

- Intégration locale : main, abed298, aucun changement suivi ou non suivi signalé par git status.
- Carte locale voisine : main, ae1c932, version 0.2.9, aucun changement non publié.
- git fetch origin effectué sur les deux dépôts : branches locales à jour.
- Autre branche locale de l’intégration : fix-brand-retina-icon, 2e6fe5a (amont supprimé), non modifiée.
- Aucun dossier sources/ ni fichier AGENTS.md trouvé dans ces deux copies ; dossiers .agents vides.
- Aucune copie d’une autre session supposée accessible. Aucun changement connu à récupérer
  n’a été identifié dans les copies inspectées ; des fichiers absents de ces copies ne sont pas vérifiables.
- Branche de travail : feat/bundle-lovelace-card, créée dans le dépôt de l’intégration.
- Aucun changement effectué dans le dépôt de la carte.

## Sources officielles vérifiées

La [demande de Frenck](https://github.com/hacs/default/pull/12061#issuecomment-6384887297)
a été lue via GitHub. Les API ont été vérifiées dans le tag Home Assistant **2026.10.3** :

- [HTTP server](https://github.com/home-assistant/core/blob/2026.10.3/homeassistant/components/http/server.py),
  SHA e86cb8c7d31e918ddb2118c31b1986939122527e : StaticPathConfig et
  async_register_static_paths. L’enregistrement asynchrone délègue la lecture du système
  de fichiers à l’exécuteur. Le bundle est servi sans cache HTTP long.
- [Lovelace](https://github.com/home-assistant/core/blob/2026.10.3/homeassistant/components/lovelace/__init__.py),
  SHA 8b468f29acab80aee7b3efb158c8eda3743be5dd : LovelaceData.resources et
  séparation resource_mode/dashboard mode. Les dépendances manifest http/lovelace
  garantissent que ces services sont prêts avant le setup de l’entrée T2C.
- [Ressources](https://github.com/home-assistant/core/blob/2026.10.3/homeassistant/components/lovelace/resources.py),
  SHA 2d0edd4fff69f5ed31b88b18087c412a2fda78fb : async_get_info charge la collection,
  async_items lit ses ressources ; create/update attendent **res_type**, stocké en **type**.
  Les modifications utilisent les méthodes asynchrones de collection, jamais .storage directement.
- [Constantes](https://github.com/home-assistant/core/blob/2026.10.3/homeassistant/components/lovelace/const.py),
  SHA 9b42415119e5744cecff40e46e184eeb92bee086 : LOVELACE_DATA.

Le minimum HACS est porté explicitement à **2026.10.0** pour cibler cette génération
vérifiée d’API, sans prétendre prendre en charge les anciennes représentations
Lovelace en dictionnaire. Ces API internes Lovelace peuvent évoluer ; vérifier les
sources et tester lors d’une future mise à niveau majeure de Home Assistant.

## Vérifications locales exécutées

- 29 tests Python unittest réussis : 21 tests API/coordinator existants et 8 tests frontend.
- 3 tests JavaScript Node réussis : double évaluation, composant ancien déjà chargé,
  éditeur et configuration, temps réel et couleurs de ligne.
- Construction déterministe et vérification source/bundle réussies.
- Ruff sur les nouveaux fichiers Python : contrôle et format après correction des imports.
- Vérification du contenu de l’archive Git exécutée après le commit : bundle autonome,
  éditeur, module Python et manifest présents. HACS n’utilise pas de ZIP de release séparé.
- git diff --check exécuté.

Les premiers essais de la suite Python ont échoué faute d’aiohttp dans le runtime.
Les dépendances ont ensuite été installées dans un dossier temporaire et la suite
complète a réussi. Les tests frontend utilisent des doubles aux frontières des API
Home Assistant. Ils ne constituent **pas** un test de démarrage d’une vraie instance.
Les tests JavaScript utilisent un environnement minimal, pas un navigateur complet.
HACS, hassfest et les régressions ont réussi dans GitHub Actions (run 40127063471, commit aa2c193). HACS/hassfest n’ont pas été exécutés localement.

## Tests à effectuer sur Home Assistant avant publication

Utiliser une sauvegarde et déployer la branche pour essai ; aucune release n’a été publiée.

1. **Migration stockage** : avant mise à jour, noter les ressources existantes et ouvrir
   une carte existante. Installer cette branche, redémarrer HA. Vérifier une seule
   ressource module sous /t2c_clermontferrand/, absence de l’ancien chemin HACS et
   préservation de chaque autre ressource. Vérifier aussi des doublons T2C si disponibles.
2. **Navigateur et Companion** : fermer/rafraîchir complètement tous les clients.
   Dans les outils réseau, vérifier un seul chargement du module T2C, HTTP 200 et
   JavaScript valide. Pas d’erreur de double définition dans la console. Un ancien
   composant déjà chargé reste en mémoire jusqu’au rafraîchissement.
3. **Carte existante** : vérifier arrêt, titre, 1/5/6 passages, temps réel et théorique,
   couleurs, alertes au clic/tap, informations réseau. Ouvrir l’éditeur visuel,
   modifier/enregistrer les options et ajouter une nouvelle carte.
4. **Cycles** : recharger l’entrée plusieurs fois, désactiver/réactiver la dernière
   entrée, redémarrer HA, et si possible essayer avec plusieurs anciennes entrées.
   Toujours une seule ressource ; aucune erreur de route HTTP déjà enregistrée.
5. **YAML** : dans une instance de test configurée avec des ressources YAML, vérifier
   que le fichier reste inchangé et qu’un avertissement fournit la nouvelle URL.
   Remplacer manuellement seulement les ressources T2C, recharger les ressources,
   puis rafraîchir les clients. Les autres modules doivent toujours fonctionner.
6. **Cache** : déployer un bundle modifié, redémarrer HA ; vérifier que le paramètre
   v change (mise à jour automatique en stockage, manuelle en YAML). Un simple
   rechargement d’entrée réutilise l’empreinte du processus : le déploiement exige un redémarrage.
7. **Ancien HACS** : après validation, désinstaller l’ancienne carte Dashboard. Vérifier
   à nouveau la ressource canonique et l’affichage. Ne pas mettre à jour l’ancienne carte
   pendant la migration, HACS peut recréer sa ressource.
8. **Retour arrière** : restaurer la précédente intégration, l’ancienne carte et une
   seule ancienne ressource selon le README, puis redémarrer/rafraîchir. Vérifier le dashboard.

## Résultats rapportés sur l’instance de Mathieu le 24 octobre 2026

- Déploiement manuel du dossier local et redémarrage Home Assistant effectués.
- Carte affichée après Ctrl+F5 ; éditeur visuel et modification des options confirmés.
- Une seule ressource module canonique observée, avec empreinte de contenu.
- Après rechargement de l’entrée, une seule ressource T2C toujours présente.
- Après désinstallation de l’ancienne carte HACS, erreur « Custom element doesn’t exist ».
  Mathieu a supprimé la ressource T2C ; il confirme sa recréation automatique et
  le retour de la carte. La cause exacte de l’incident n’est pas établie.
- Aucune erreur T2C signalée dans les journaux par Mathieu après ces manipulations.

L’affichage de passages en circulation reste à vérifier : Mathieu indique une
suspension du service en raison de manifestations. Les tests multi-entrées réels,
YAML, renouvellement du cache après une nouvelle mise à jour, retour arrière,
réseau HTTP/console navigateur et affichage Companion ne sont pas confirmés.

 La version du manifest passe à 0.2.14 pour la publication autorisée par Mathieu
après fusion de la PR et validation des premiers tests sur son instance.
Les vérifications non confirmées ci-dessus restent des limites de cette validation.

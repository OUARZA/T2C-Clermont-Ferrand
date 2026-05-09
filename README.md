# T2C Clermont-Ferrand

Intégration Home Assistant personnalisée pour afficher les prochains passages T2C de Clermont-Ferrand.

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

L'intégration demande :
- le nom de la ligne ;
- l'identifiant technique de ligne T2C ;
- le nom de la direction ;
- l'identifiant technique de direction ;
- le nom de l'arrêt ;
- l'identifiant technique de l'arrêt.

Pour une première version, les identifiants peuvent être récupérés avec le script historique `t2c-harvester.py`.

## Notes

Cette version interroge les pages publiques T2C utilisées historiquement par le projet `t2c-harvester`.
Si T2C change son site ou son API, le fichier `api.py` sera le point principal à adapter.

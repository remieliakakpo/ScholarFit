# ScholarFit : guide complet de mise en ligne

Ce guide décrit tout le chemin, de votre ordinateur jusqu'au site visible par tout le monde, avec les erreurs possibles à chaque étape et leur solution.

## 0. Vue d'ensemble

Le projet a trois morceaux, chacun hébergé à un endroit différent :

| Morceau | Rôle | Où il vit |
|---|---|---|
| Le code | Tous les fichiers du projet | **GitHub** (dépôt `scholarfit`) |
| Le site (dossier `frontend`) | Ce que voit le visiteur | **Vercel** |
| Le serveur (dossier `backend`) | Comptes, bourses, IA, collecte automatique | **Railway** |

Le chemin d'une modification : vous remplacez les fichiers sur votre ordinateur, vous envoyez avec Git vers GitHub, et Vercel et Railway se mettent à jour tout seuls en lisant GitHub.

Pourquoi deux hébergeurs ? Vercel ne sait faire tourner que de petites fonctions de quelques secondes. Le serveur de ScholarFit doit rester allumé en permanence (collecte des bourses chaque semaine, alertes chaque jour, base de données, tâches IA). Il lui faut donc un vrai serveur, d'où Railway. Railway n'est gratuit que pour un essai limité ; ensuite il est payant (quelques dollars par mois). Render, Fly.io ou PythonAnywhere sont des alternatives.

## 1. Préparer son ordinateur

1. Installez Git, VS Code et Python.
2. Ouvrez dans VS Code le dossier du projet (exemple : `Documents\plateforme-bourses`) avec Fichier > Ouvrir le dossier. Travaillez toujours depuis ce dossier.
3. Ouvrez le terminal intégré : menu Terminal > Nouveau terminal. Toutes les commandes `git` se tapent là, pas besoin d'un autre terminal.
4. Le dossier caché `.git` contient l'historique du dépôt. Il est invisible dans VS Code, c'est normal. Pour le voir dans l'Explorateur Windows : onglet Affichage > cocher « Éléments masqués ». **Ne le supprimez jamais.** Pour vérifier qu'un dossier est bien un dépôt, tapez `git remote -v` : le lien GitHub doit s'afficher.

## 2. Mettre le code sur GitHub (première fois)

1. Créez un dépôt **vide** sur github.com (New repository, nom `scholarfit`, sans README).
2. Dans le terminal, à la racine du projet :
   ```
   git init
   git add -A
   git commit -m "Première version ScholarFit"
   git branch -M main
   git remote add origin https://github.com/VOTRE-COMPTE/scholarfit.git
   git push -u origin main
   ```
3. Une fenêtre de connexion GitHub s'ouvre. Connectez-vous et autorisez. Si elle demande un code (« Autoriser votre appareil »), il s'affiche dans la fenêtre Git/VS Code ou dans le terminal, sous la forme `XXXX-XXXX`.

Les messages « LF will be replaced by CRLF » pendant `git add` sont des avertissements normaux sous Windows. Ce ne sont pas des erreurs : laissez la commande finir.

Le fichier `backend/.env` (vos clés secrètes) n'est **pas** envoyé sur GitHub, il est dans `.gitignore`. C'est voulu.

## 3. Mettre à jour le code à chaque nouvelle version (zip)

Chaque nouveau zip remplace tout le code. Procédure :

1. Ouvrez le dossier du dépôt dans VS Code et vérifiez avec `git remote -v`.
2. Copiez `backend/.env` et tout fichier `.db` (base locale) sur le Bureau. Ils sont dans `backend`, qui va être effacé.
3. Dans l'Explorateur Windows (pas dans VS Code), ouvrez ce dossier. Sélectionnez tout **sauf** `.git` et `.gitattributes`, puis supprimez. Éléments à remplacer : `backend`, `frontend`, `.github`, `.gitignore`, `docker-compose.yml`, `README.md`, `start.ps1`, `start.sh`.
4. Copiez dans le dossier tout le contenu du nouveau zip. Remettez ensuite votre `backend/.env`.
5. Dans le terminal :
   ```
   git add -A
   git commit -m "Mise à jour ScholarFit"
   git push
   ```
6. Vercel et Railway redéploient seuls. Suivez l'avancement dans leurs onglets Deployments.

Un seul dépôt suffit : Git enregistre la différence, même si presque tous les fichiers ont changé. Inutile d'en créer un nouveau.

Le dossier `.venv` (outils Python de votre ordinateur) n'a pas à être envoyé et peut être supprimé sans risque, il se recrée avec `start.ps1`.

## 4. Utiliser deux comptes GitHub

Règle simple : **un dossier = un compte**. Ce qui décide où part le code, c'est le lien `origin` du dossier.

Pour envoyer un projet vers un autre compte :
1. Connectez-vous au nouveau compte (fenêtre de navigation privée) et créez-y un dépôt vide.
2. Dans le terminal du dossier : `git remote set-url origin https://github.com/NOUVEAU-COMPTE/scholarfit.git`
3. Réglez la signature des commits, **une commande par ligne** :
   ```
   git config user.name "NomDuCompte"
   git config user.email "adresse-du-compte@exemple.com"
   ```
   Sans `--global`, cela ne vaut que pour ce dossier. L'adresse e-mail doit être liée au compte GitHub (Settings > Emails) pour que les commits lui soient attribués.
4. `git push -u origin main`.

Vérifications à tout moment : `git remote -v` (où ça part) et `git config user.name` (qui signe).

Erreurs fréquentes :

| Message | Cause | Solution |
|---|---|---|
| `403 Permission denied to AUTRECOMPTE` | Windows a mémorisé l'ancien compte | Menu Démarrer > Gestionnaire d'identification > Informations d'identification Windows > supprimer les lignes `git:https://github.com`, puis refaire `git push` et se connecter avec le bon compte |
| `error: no action specified` | Deux commandes collées avec le mot « et » | Les taper séparément |
| Fenêtre « Autoriser votre appareil » avec un code | Connexion par code | Chercher le code dans la fenêtre Git (parfois cachée derrière VS Code) ou dans le terminal |
| Vercel ne liste pas le dépôt | L'application Vercel n'a pas accès au dépôt | Vercel > Add New > Project > Adjust GitHub App Permissions, donner accès au dépôt |
| Vercel clone encore l'ancien compte | Vercel est relié à l'ancien compte | Vercel > Settings > Git, ou réimporter le dépôt depuis le nouveau compte |

## 5. Les clés et réglages secrets

Les clés se mettent dans `backend/.env` en local et dans les **Variables** de Railway en ligne. Jamais sur GitHub, jamais dans un chat.

- `SECRET_KEY` : une longue chaîne aléatoire. Pour la générer, dans le terminal, **sur une seule ligne** : `python -c "import secrets; print(secrets.token_hex(32))"`. Si la commande reste bloquée sur `>>`, faites Ctrl + C et recopiez-la en entier, avec la parenthèse et le guillemet finaux.
- `ANTHROPIC_API_KEY` : clé de l'IA, créée sur console.anthropic.com > Settings > API Keys. Un compte claude.ai ne suffit pas : il faut aussi acheter du crédit (Plans & Billing, 5 $ pour commencer). Une clé Gemini ne marche pas, le code est écrit pour l'API Anthropic.
- `CLAUDE_MODEL` : modèle utilisé. Par défaut `claude-opus-5-5` (le plus puissant, le plus cher). On peut mettre `claude-sonnet-5-5` ou `claude-haiku-5-5` pour réduire la facture.
- `RELIEFWEB_APPNAME` : nom d'application pour les stages des organisations internationales. Gratuit : formulaire sur apidoc.reliefweb.int, réponse par e-mail sous deux jours ouvrés. Mettre ensuite le nom reçu, exactement.
- `AI_DISCOVERY_ENABLED` : mettre `false` si vous n'avez pas de crédit IA.
- `CORS_ORIGINS` : adresse du site Vercel (voir parties 6 et 7).
- `DATABASE_URL` : base de données (voir 6.5).

Si vous avez perdu votre `.env`, rien de grave : on recrée la clé secrète, la clé IA et le nom ReliefWeb. Seuls les comptes de test d'une base locale sont perdus. Sans aucune clé IA, le site fonctionne en mode hors-ligne (règles et modèles), sans génération IA de CV, lettres, diagnostics ni découverte de bourses par IA.

## 6. Déployer le serveur sur Railway

### 6.1 Création
1. railway.com : New Project > Deploy from GitHub repo, choisissez le dépôt (donnez à Railway l'accès à ce compte GitHub si nécessaire).

### 6.2 Réglages indispensables
1. **Settings > Source > Root Directory** = `backend`. Sans cela, Railway lance le `start.sh` de la racine, fait pour votre ordinateur, et les logs répètent `start.sh: line 7: python3: command not found` (redémarrages en boucle, statut « Crashed »).
2. **Settings > Deploy > Start Command** : laissez vide. Le `Dockerfile` du dossier `backend` contient déjà la bonne commande.
3. **Variables** : ajoutez `SECRET_KEY`, `PORT` = `8000`, et selon le cas `ANTHROPIC_API_KEY`, `RELIEFWEB_APPNAME`, `AI_DISCOVERY_ENABLED`. Le champ de gauche est le **nom**, celui de droite la **valeur**. Ne pas les inverser (exemple d'erreur vécue : « Domaine » écrit dans le champ du nom au lieu de `CORS_ORIGINS`).
4. **Settings > Networking** : cliquez Generate Domain. Vérifiez que le port du domaine est `8000`.

### 6.3 Vérifier
Dans les **Deploy Logs**, cherchez `Uvicorn running on http://0.0.0.0:8000` et `Application startup complete`. Puis ouvrez dans le navigateur `https://VOTRE-DOMAINE.up.railway.app/docs` : la page de documentation de l'API doit s'afficher. Les logs affichent aussi les comptes de démonstration créés au premier démarrage (administrateur, démo, conseiller).

### 6.4 Erreurs Railway

| Message ou symptôme | Cause | Solution |
|---|---|---|
| `start.sh: line 7: python3: command not found`, boucle de redémarrage | Mauvais dossier déployé | Root Directory = `backend`, Start Command vide |
| « Application failed to respond » dans le navigateur | Le domaine vise un mauvais port | Variable `PORT=8000` et port du domaine sur 8000, attendre le redéploiement |
| Erreur 400 « Your credit balance is too low » dans les logs | La clé est valide mais le compte Anthropic n'a plus de crédit | Acheter du crédit (console.anthropic.com > Plans & Billing) ou mettre `AI_DISCOVERY_ENABLED=false`. Ce n'est pas bloquant : le site marche sans IA |
| « 0 bourse(s) proposée(s) » pour chaque zone | Même cause (découverte par IA sans crédit) | Idem. Les 98 bourses de départ et les sites d'annonces restent chargés |

### 6.5 Base de données durable
Par défaut, la base est un fichier SQLite dans le conteneur : elle est effacée à chaque redéploiement, donc comptes et dossiers aussi. Pour la conserver : dans Railway, New > Database > PostgreSQL, puis copiez son lien de connexion dans la variable `DATABASE_URL` du serveur (au format `postgresql+psycopg://...`). Le Dockerfile installe déjà le pilote Postgres.

### 6.6 Sécurité après le premier démarrage
Les comptes de démonstration (`admin@example.org`, `demo@example.org`, `conseiller@example.org`) ont des mots de passe écrits dans le code et donc publics. Avant de partager le site : changez-les ou supprimez-les, et définissez `ADMIN_EMAILS` avec votre vraie adresse.

## 7. Déployer le site sur Vercel

1. vercel.com : Add New > Project, importez le dépôt.
2. **Root Directory** = `frontend` (et non `./`). Sinon la construction échoue avec « No Next.js version detected », car le `package.json` est dans `frontend`. Si le projet existe déjà : Settings > General > Root Directory.
3. **Environment Variables** (nom à gauche, valeur à droite) :
   - `API_URL_INTERNAL` = adresse Railway, par exemple `https://scholarfit-production.up.railway.app` (https obligatoire, pas de `/` à la fin)
   - `NEXT_PUBLIC_API_URL` = la même adresse
4. Cliquez Deploy. Vercel donne l'adresse du site (exemple `https://scholarfit-phi.vercel.app`).
5. **Retour dans Railway** > Variables : `CORS_ORIGINS` = cette adresse Vercel (https, sans `/` final). Plusieurs adresses sont possibles, séparées par une virgule. Sans cela, le navigateur bloque les appels vers le serveur.
6. Les variables ne s'appliquent qu'à un **nouveau déploiement** : Deployments > dernier déploiement > ⋯ > Redeploy (sans le cache de build).

### Erreurs Vercel

| Message ou symptôme | Cause | Solution |
|---|---|---|
| « No Next.js version detected » | Mauvais dossier racine | Root Directory = `frontend`, puis Redeploy |
| Adresse du backend collée dans le champ « Key » | Nom et valeur inversés | Key = `API_URL_INTERNAL`, Value = l'adresse |
| « Le serveur de ScholarFit ne répond pas » sur la page de connexion | Le site n'atteint pas le backend | Tester `/docs` sur Railway ; vérifier les deux variables Vercel ; Redeploy sans cache |
| Page qui charge mais données vides ou erreurs réseau | `CORS_ORIGINS` absent ou faux | Mettre l'adresse exacte du site Vercel dans Railway |

## 8. Test final

1. Ouvrez l'adresse Vercel : la page d'accueil s'affiche.
2. La liste des bourses se remplit (98 au départ, plus la collecte automatique).
3. Créez un compte et connectez-vous.
4. Les fonctions IA (CV, lettres, compatibilité) ne marchent que si la clé IA est valide **et** le compte a du crédit ; sinon le site utilise le mode hors-ligne.
5. Les stages des organisations internationales apparaissent après l'ajout de `RELIEFWEB_APPNAME`.

## 9. Check-list rapide en cas de problème

1. Railway : le dernier déploiement est-il « Active » ? Que disent les Deploy Logs ?
2. `https://VOTRE-DOMAINE.up.railway.app/docs` s'affiche-t-il ?
3. Railway : `PORT=8000`, port du domaine sur 8000, Root Directory = `backend`.
4. Vercel : Root Directory = `frontend`, variables `API_URL_INTERNAL` et `NEXT_PUBLIC_API_URL` correctes, Redeploy fait.
5. Railway : `CORS_ORIGINS` = adresse du site Vercel.
6. Git : `git remote -v` montre-t-il le bon dépôt ? Le dernier `git push` a-t-il réussi ?

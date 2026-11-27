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
- `DATABASE_URL` : base de données (voir 6.5). En ligne, PostgreSQL est obligatoire.
- `SITE_URL` et `API_PUBLIC_URL` : adresses publiques du site et de l'API, en https (voir 8.1).
- `PAYMENT_PROVIDER`, `CINETPAY_APIKEY`, `CINETPAY_SITE_ID`, `CINETPAY_SECRET_KEY` : paiement en ligne (voir 8.3).
- `EMAIL_BACKEND`, `SMTP_FROM`, `BREVO_API_KEY` : envoi des e-mails (voir 8.4).

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
Les comptes de démonstration (`admin@example.org`, `demo@example.org`, `conseiller@example.org`) ont des mots de passe écrits dans le code et donc publics. Ils sont recréés à chaque démarrage tant que `DEMO_ACCOUNTS=true`. Avant de partager le site : mettez `DEMO_ACCOUNTS=false`, supprimez-les depuis l'API ou la base, et définissez `ADMIN_EMAILS` avec votre vraie adresse. Pour que les e-mails de confirmation et de mot de passe oublié partent vraiment, ajoutez aussi `SITE_URL` (adresse publique du site) et les variables `SMTP_*` (voir le README).

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

## 8. Avant d'ouvrir le site au public

Une commande fait le tour de tous les réglages et dit ce qui manque. Dans Railway : service backend > ⋯ > **Shell** (ou en local, avec le `.env` de production) :

```
python -m app.cli check-config
```

Chaque ligne `[BLOQUANT]` doit être corrigée avant d'annoncer le site. Les lignes `[CONSEIL]` sont facultatives. Au démarrage, l'API écrit aussi ces avertissements dans les Deploy Logs tant qu'ils ne sont pas réglés.

### 8.1 Nom de domaine et HTTPS
1. Achetez un nom de domaine (par exemple `scholarfit.tg` ou `scholarfit.org`) chez un registraire (OVH, Namecheap, Gandi…).
2. **Site** : Vercel > projet > Settings > Domains > Add, tapez `www.votre-domaine.org`. Vercel affiche l'enregistrement DNS à créer chez le registraire (un `CNAME` vers `cname.vercel-dns.com`). Ajoutez aussi le domaine nu `votre-domaine.org`, Vercel le redirige vers `www`.
3. **API** : Railway > service backend > Settings > Networking > Custom Domain, tapez `api.votre-domaine.org` et créez le `CNAME` indiqué.
4. Le certificat HTTPS est fourni et renouvelé automatiquement par Vercel et Railway (quelques minutes après la mise à jour du DNS). Rien à installer.
5. Variables à mettre à jour ensuite :
   - Railway : `SITE_URL=https://www.votre-domaine.org`, `API_PUBLIC_URL=https://api.votre-domaine.org`, `CORS_ORIGINS=https://www.votre-domaine.org`
   - Vercel : `API_URL_INTERNAL` et `NEXT_PUBLIC_API_URL` = `https://api.votre-domaine.org`, `NEXT_PUBLIC_SITE_URL=https://www.votre-domaine.org`, puis Redeploy.

### 8.2 Base PostgreSQL et sauvegardes
1. Railway : New > Database > PostgreSQL. Copiez son lien de connexion (`DATABASE_URL` du service PostgreSQL) dans la variable `DATABASE_URL` du backend, tel quel.
2. Les tables sont créées au premier démarrage. Les nouvelles colonnes des versions suivantes sont ajoutées automatiquement.
3. **Sauvegardes** : Railway > PostgreSQL > Backups (sauvegardes automatiques selon votre offre). En plus, une sauvegarde portable se fait depuis votre ordinateur, une fois par semaine, avec le `DATABASE_URL` de production dans `backend/.env` :
   ```
   python -m app.cli backup --dir sauvegardes
   ```
   Le fichier `sauvegardes/scholarfit-AAAAMMJJ-HHMM.json.gz` contient toutes les tables ; les 14 dernières sont gardées. Rangez-le aussi sur un disque ou un Drive.

### 8.3 Paiement en ligne avec CinetPay
1. Créez un compte marchand sur cinetpay.com (pièces de l'entreprise demandées, validation en quelques jours).
2. Tableau de bord CinetPay > **Intégrations** : notez l'`API KEY`, le `SITE ID` et la `SECRET KEY`.
3. Railway > Variables :
   - `PAYMENT_PROVIDER=cinetpay`
   - `CINETPAY_APIKEY`, `CINETPAY_SITE_ID`, `CINETPAY_SECRET_KEY`
   - `API_PUBLIC_URL` doit être l'adresse https de l'API : CinetPay y envoie la confirmation de chaque paiement (`/api/payments/cinetpay/notify`).
4. Rien à déclarer chez CinetPay : l'adresse de notification et l'adresse de retour sont envoyées avec chaque paiement.
5. **Essai réel** : payez un abonnement de 2 500 F CFA avec votre propre numéro. La page « Paiement confirmé » s'affiche, le reçu arrive par e-mail et le paiement apparaît dans /admin > Paiements en ligne.

Ce qui se paie en ligne : l'abonnement CV et lettres (2 500 F CFA par mois) et les offres d'accompagnement Standard (15 000 F CFA) et Premium (35 000 F CFA). Le paiement par transfert sur vos numéros Flooz et Mixx by Yas reste proposé en dessous, avec validation manuelle dans /admin.

En local, `PAYMENT_PROVIDER=simulation` (valeur par défaut) affiche un guichet d'essai : on peut tester tout le parcours sans argent. Avec `PAYMENT_PROVIDER=manuel`, seul le paiement par transfert est proposé.

Si un candidat ferme la page avant le retour, rien n'est perdu : l'API revérifie toutes les 15 minutes les paiements CinetPay restés en attente et active l'accès dès qu'ils sont confirmés.

### 8.4 E-mails (compte, rappels, reçus, accompagnement)
Le site envoie : la confirmation de l'adresse et le lien « mot de passe oublié », les rappels avant les dates limites (J-30, J-14, J-7, J-3, J-1), les nouvelles bourses qui correspondent au profil (un seul e-mail groupé), les reçus de paiement et les messages d'accompagnement (au plus un e-mail toutes les 30 minutes par personne).

Le plus simple est **Brevo** (gratuit jusqu'à 300 e-mails par jour) :
1. Créez un compte sur brevo.com, puis Senders, Domains & Dedicated IPs > Domains > ajoutez votre domaine et créez chez le registraire les enregistrements DNS indiqués (DKIM, DMARC). Sans cette étape, les e-mails partent en indésirables.
2. SMTP & API > API Keys > Generate a new API key.
3. Railway > Variables : `EMAIL_BACKEND=brevo`, `BREVO_API_KEY=…`, `SMTP_FROM=ScholarFit <no-reply@votre-domaine.org>`, `EMAIL_REPLY_TO=contact@votre-domaine.org`.
4. Essai : `python -m app.cli test-email votre.adresse@gmail.com`.

Autres possibilités : `EMAIL_BACKEND=resend` avec `RESEND_API_KEY`, ou le SMTP de votre choix avec `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` (Gmail : mot de passe d'application, port 587). Sans aucun réglage, les e-mails et leurs liens s'affichent dans la fenêtre de l'API, ce qui suffit en local. Dans tous les cas, l'expéditeur est `SMTP_FROM`.

Chaque envoi est enregistré dans la table `email_log` (date, destinataire, objet, succès ou erreur).

### 8.5 Collecte hebdomadaire
Rien à planifier : l'API relance la collecte toutes les 24 heures (`AUTO_COLLECT_HOURS=24`) et chaque source n'est relue qu'une fois par semaine. Chaque passage retire les offres expirées, teste les liens officiels (une offre dont le lien est mort disparaît du site et apparaît dans /admin > Liens cassés), envoie les rappels et revérifie les paiements.

Avec plusieurs copies de l'API, laissez `AUTO_COLLECT_HOURS=24` sur une seule et mettez `0` sur les autres.

### 8.6 Pages légales et référencement
- Renseignez dans Vercel `NEXT_PUBLIC_COMPANY_NAME`, `NEXT_PUBLIC_COMPANY_ADDRESS`, `NEXT_PUBLIC_CONTACT_EMAIL` et `NEXT_PUBLIC_CONTACT_PHONE` : ils s'affichent dans À propos, Conditions d'utilisation et Confidentialité.
- Relisez `/conditions` (en particulier la règle de remboursement) et `/confidentialite`, puis faites-les valider si possible par un juriste.
- Google Search Console : ajoutez le domaine, puis Sitemaps > `https://www.votre-domaine.org/sitemap.xml`. Le plan liste les pages pays (`/destinations/france`, `/destinations/france/bourses`…) et toutes les fiches.

### 8.7 Comptes de démonstration
Mettez `DEMO_ACCOUNTS=false` et votre adresse dans `ADMIN_EMAILS`. `python -m app.cli check-config` signale aussi les comptes de démonstration dont le mot de passe public n'a pas été changé.

## 9. Test final

1. Ouvrez l'adresse Vercel : la page d'accueil s'affiche.
2. La liste des bourses se remplit (98 au départ, plus la collecte automatique).
3. Créez un compte et connectez-vous.
4. Les fonctions IA (CV, lettres, compatibilité) ne marchent que si la clé IA est valide **et** le compte a du crédit ; sinon le site utilise le mode hors-ligne.
5. Les stages des organisations internationales apparaissent après l'ajout de `RELIEFWEB_APPNAME`.
6. Payez un abonnement : la page « Paiement confirmé » s'affiche et le reçu arrive par e-mail.
7. Ouvrez `/destinations`, `/conditions`, `/confidentialite`, `/sitemap.xml` et `/robots.txt`.

## 10. Check-list rapide en cas de problème

1. Railway : le dernier déploiement est-il « Active » ? Que disent les Deploy Logs ?
2. `https://VOTRE-DOMAINE.up.railway.app/docs` s'affiche-t-il ?
3. Railway : `PORT=8000`, port du domaine sur 8000, Root Directory = `backend`.
4. Vercel : Root Directory = `frontend`, variables `API_URL_INTERNAL` et `NEXT_PUBLIC_API_URL` correctes, Redeploy fait.
5. Railway : `CORS_ORIGINS` = adresse du site Vercel.
6. Git : `git remote -v` montre-t-il le bon dépôt ? Le dernier `git push` a-t-il réussi ?

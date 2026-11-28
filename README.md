# ScholarFit

Plateforme qui collecte les bourses d'études (du bac au doctorat), montre à chaque étudiant celles auxquelles il a droit, et l'aide à préparer son dossier : CV amélioré, lettre de motivation, suivi des candidatures.

Ce dépôt est le **MVP** décrit dans le document de conception du projet. Il tourne en local en quelques minutes, avec ou sans clé d'API d'IA.

## Ce que fait le MVP

| Fonction | Où | Détails |
|---|---|---|
| Assistant de recherche (chat) | Page d'accueil | L'étudiant écrit librement (« Je suis en L3 de biologie au Sénégal… »). L'assistant extrait les critères, pose seulement les questions qui manquent (avec réponses rapides), puis cherche **dans la base** et affiche des cartes avec le lien officiel. L'IA ne répond jamais de mémoire. Visiteur : 3 résultats ; compte : tous, et le profil se remplit. |
| Questionnaire | `/questionnaire` | 5 étapes (toi, études, destination, langues, situation) servies par `GET /api/questionnaire`. Sans compte : nombre de bourses trouvées et 3 aperçus sans score ; après inscription, retour automatique au résultat avec les scores et le profil enregistré. Réponses gardées dans le navigateur (`sf_questionnaire`). Étape destination : choisir un continent réduit la liste des pays précis à ce continent (`filter_by`, région de chaque pays servie par l'API). Résultats : d'abord les bourses dans les pays ou continents choisis (`in_destination`, `destination_total`), puis « Autres bourses disponibles ». |
| Catalogue | `/bourses` | Barre de filtres à gauche : type d'opportunité (bourses, stages, conférences), région, niveau, pays d'études, domaine, nationalité, financement ; tri par priorité (urgentes d'abord), date limite ou montant ; option pour voir les bourses clôturées. Les filtres sont dans l'URL (`/bourses?country=FR`, lien du carrousel de l'accueil). Fiches rendues côté serveur : conditions détaillées, documents avec explications, lien officiel et son état, « Comment postuler » étape par étape, bouton d'accompagnement et tarifs. |
| Postuler | `/postuler/ID` | Le bouton « Postuler » des cartes et des fiches ouvre cette page interne, sans compte : conditions, ce qui est pris en charge, pièces à fournir, étapes, puis **le lien officiel de candidature** en bas, et l'option **« Me faire accompagner par un expert »** (Standard 15 000 F CFA pour 1 bourse, Premium 35 000 F CFA pour 3 bourses ; l'expert dépose lui-même la candidature). Le compte n'est demandé que pour l'accompagnement. |
| Profil en 3 étapes | `/profil` | Identité, parcours, projet et atouts, plus une étape facultative (revenus modestes, réfugié, handicap…). Barre de complétude et conseil (« ajoute ton score de langue… »). Import du CV (PDF, .docx, .txt) qui préremplit les champs vides. Suppression du compte en un clic. |
| Matching | `/mes-bourses` | 3 passes : filtres durs (niveau, nationalité, âge, date limite, pays, public ciblé), score de 0 à 100 (domaine 30, projet 25, notes et langues 20, pays 15, financement 10), explication « pourquoi / à surveiller ». Score de chance (faible, moyenne, bonne). |
| Accompagnement | `/accompagnement`, `/conseiller`, `/admin` | Le candidat demande un suivi (objectif, besoins : choix des bourses, CV, lettre, recommandations, entretien, test de langue, visa ; bourses concernées ; langue ; disponibilités) et accepte de partager son dossier. Le conseiller le plus adapté qui a de la place est attribué tout de suite (langue, niveau, domaine, pays, charge), sinon la demande attend dans `/admin`. Un **plan d'étapes daté à rebours** depuis la date limite la plus proche est créé, puis : messages (liés ou non à une candidature), rendez-vous proposés par l'un et confirmés par l'autre avec compte rendu, vue du profil, du CV et des candidatures pour le conseiller, alertes à chaque événement et rappel la veille d'une étape ou d'un rendez-vous. Fin par le conseiller et avis du candidat (1 à 5). Deux offres payantes (Standard 15 000 F CFA, jusqu'à 2 bourses ; Premium 35 000 F CFA, jusqu'à 5 bourses, entretien blanc et visa) ; le candidat peut aussi postuler seul gratuitement. Le paiement (Mobile Money, Wave…) se fait hors plateforme et l'admin le marque reçu. |
| Suivi Kanban | `/suivi` | Colonnes À préparer, En cours, Envoyée, Résultat (glisser-déposer). Checklist des pièces exigées par chaque bourse, notes, **vérification du dossier** (pièces manquantes, longueur de la lettre, crochets à compléter, test de langue, moyenne). |
| Mon CV | `/cv` | Import du CV (PDF, Word, texte). **Diagnostic sur 9 critères** (coordonnées, rubriques, dates, verbes d'action, résultats mesurables, longueur, langues, lisibilité, adéquation avec la bourse) avec constat, recommandation et trois priorités. **CV adapté** à la bourse : format choisi automatiquement selon le pays d'études (Lebenslauf, Europass, résumé nord-américain, CV britannique, CV français, CV académique pour le doctorat, sinon CV international ATS), langue de la candidature, mots-clés du jury. Aperçu modifiable sur place, téléchargement **PDF** et **Word** (polices libres Carlito et Caladea intégrées). **Modèle ATS (2026-11-22)** : nom et titre en capitales « diplôme visé | spécialités », coordonnées, ligne « Candidature : bourse | Rentrée | Mobilité » à la place des mentions d'emploi, profil personnalisé (diplôme, expérience, compétences clés, objectif lié à la bourse), compétences par catégorie, expériences « poste | organisme | lieu » avec dates à droite, projets, formation, langues sur une ligne. Mentions CDI, CDD, disponibilité retirées. |
| Lettre de motivation | `/lettre/ID` | En-tête complet tiré du profil (nom, adresse, ville, téléphone, e-mail) et du CV. Réponses facultatives : programme visé, pourquoi ce pays, pourquoi ce programme, plan d'études, projet après les études, réalisation marquante. Disposition française (destinataire à droite, « Lomé, le … », objet, formule de politesse) ou anglophone (britannique ou américaine). Contrôle avant affichage : pas de deux-points dans le corps, pas de tiret cadratin, pas de phrase incomplète, pas de crochets, pas de formule stéréotypée (réécriture automatique si besoin). Aperçu modifiable, téléchargement **PDF** et **Word**. |
| Préparer ma candidature | `/preparer/ID` | **Compatibilité avant de postuler** : conditions d'accès, pièces du dossier, thèmes valorisés par le jury couverts ou non par le CV, score, verdict et améliorations classées par priorité. |
| Dossiers CV + lettre | `/cv`, `/lettre/ID`, `/admin` | Un dossier = CV adapté + lettre pour une bourse, 3 générations de chaque. **Le premier est offert, ensuite abonnement à 2 500 F CFA par mois** (`SUBSCRIPTION_PRICE`) pour préparer jusqu'à 10 dossiers par mois (`SUBSCRIPTION_MONTHLY_PACKS`, limite qui maîtrise le coût de l'IA). Paiement Flooz, Mixx by Yas, TapTap Send, LemFi ou PI-SPI vers les numéros affichés ; l'étudiant déclare la référence, l'admin valide dans `/admin` et l'abonnement démarre pour 30 jours (ou est prolongé d'un mois). Le diagnostic et les modifications manuelles restent gratuits. |
| Alertes par e-mail | `/mes-bourses` + e-mail | Nouvelles bourses correspondant au profil, nouvelles offres des **recherches sauvegardées**, rappels J-30, J-7 et J-1 pour les candidatures pas encore envoyées, messages et rendez-vous d'accompagnement. **Un seul e-mail par personne et par passage** (toutes les `AUTO_COLLECT_HOURS` heures) qui regroupe ses alertes, avec un lien de désabonnement (`/desabonner`, en-tête `List-Unsubscribe`). Pas d'e-mail si l'adresse n'est pas confirmée ou si les alertes sont refusées dans le profil. Sans `SMTP_HOST`, l'e-mail est écrit dans la console de l'API. |
| Recherches sauvegardées | `/bourses`, `/mes-bourses` | Dans Explorer, « M'alerter des nouvelles offres » enregistre les filtres affichés (20 recherches au plus). Chaque nouvelle fiche qui y répond crée une alerte. Liste, activation des alertes et suppression dans « Mes bourses ». |
| Signalements | fiche, `/admin` | « Signaler une erreur » sur chaque fiche (lien mort, date fausse, informations erronées, offre disparue, autre), réservé aux comptes, un signalement ouvert par personne et par fiche. Trois signalements « lien mort » de personnes différentes marquent le lien comme cassé. Dans l'administration : liste, « Corrigé » (prévient les personnes qui ont signalé) ou « Rejeter ». |
| Agenda et partage | fiche, `/suivi` | Date limite d'une fiche en fichier `.ics` (rappels 7 jours et 1 jour avant), toutes les dates limites du suivi en un fichier. Partage sur WhatsApp et partage natif du téléphone. Aperçu du lien soigné (titre, résumé, image générée `opengraph-image`) : définir `NEXT_PUBLIC_SITE_URL`. |
| Application installable et hors ligne | tout le site | Manifeste (`/manifest.webmanifest`, icônes dans `public/icons/`) et service worker (`public/sw.js`, actif après `npm run build`) : fichiers du site gardés, pages et données de « Mes bourses », du suivi et des fiches suivies lisibles sans réseau, page `/hors-ligne` sinon, bandeau « Hors connexion ». Rien de personnel n'est gardé après la déconnexion. |
| Mode léger | tout le site | Sans globe animé, illustrations ni animations. Activé tout seul si le téléphone signale une connexion lente (2G, 3G) ou l'économiseur de données, annoncé par une notification (« Garder le mode léger » ou « Tout afficher », choix retenu) ; lien en pied de page pour changer d'avis. |
| Administration | `/admin` | Lancer une source de collecte, tester l'extraction d'une URL, valider les bourses « à vérifier », saisie manuelle, maintenance (expirations et alertes), fiches signalées, **coût de l'IA** (par jour et par fonction) et **journal d'audit**. |
| Types d'opportunités | `/admin` | Interrupteur par type (bourses, stages, conférences, formations, concours, échanges, fellowships, cours en ligne), avec le nombre d'offres ouvertes et en base. Un type désactivé reste en base mais disparaît des onglets, de la recherche, des fiches, du matching, du questionnaire, des alertes et des statistiques, et n'est plus collecté (catégories et zones de découverte sautées : aucun coût d'IA). Par défaut, tous sont affichés. Réglage gardé en base (`site_settings`), changement inscrit au journal d'audit. |
| Journal d'audit | `/admin` | Toute modification réussie sous `/api/admin` est inscrite automatiquement (auteur, action, cible, détails comme le titre d'une fiche supprimée ou le statut d'un paiement, adresse IP), ainsi que les connexions des administrateurs, les changements et réinitialisations de mot de passe et les suppressions de compte. |
| Supervision | API et site | Suivi des erreurs par Sentry (ou compatible, GlitchTip) si `SENTRY_DSN` est défini, sans donnée personnelle. Les erreurs d'affichage du site (`app/error.tsx`, `app/global-error.tsx`) remontent à l'API (`POST /api/erreurs-site`). Chaque appel à Claude enregistre ses jetons et son coût estimé (`ai_costs`, prix `AI_PRICE_*`) ; `AI_DAILY_BUDGET_USD` coupe l'IA pour la journée au-delà d'un plafond (les règles hors-ligne prennent le relais). |

### Avec ou sans IA

- **Sans clé** (`ANTHROPIC_API_KEY` vide) : tout fonctionne en mode hors-ligne. Le chat utilise un analyseur par règles, le CV un diagnostic par règles, la lettre un modèle à trous, l'extraction des pages des expressions régulières.
- **Avec une clé Claude** : extraction des critères du chat, diagnostic complet du CV (orthographe comprise), lettres rédigées sur mesure et extraction des pages de bourses en fiches structurées (sorties JSON garanties par schéma). Réservé aux comptes connectés, avec un plafond quotidien (`AI_FREE_GENERATIONS_PER_DAY`) pour maîtriser le coût. Si l'API échoue ou refuse, la plateforme bascule seule sur le mode hors-ligne.

Les consignes données à l'IA interdisent d'inventer une expérience, une note ou un chiffre : ce qui manque est laissé entre [crochets].

## Démarrer en local

Prérequis : **Python 3.11+** et **Node.js 20+**.

### Le plus simple

```bash
bash start.sh       # macOS / Linux
.\start.ps1         # Windows PowerShell (avant : Set-ExecutionPolicy -Scope Process Bypass)
```

Le script vérifie Python et Node.js, crée ou répare l'environnement Python, met à jour la base (sans doublons, une ancienne base reçoit les nouvelles colonnes et les nouvelles offres), installe le site, lance l'API dans sa propre fenêtre « API ScholarFit » et attend qu'elle réponde avant de lancer le site. Ouvre ensuite http://localhost:3000.

Le navigateur n'appelle jamais le port 8000 directement : le site relaie `/api/...` vers l'API (`frontend/next.config.mjs`). Il n'y a donc ni problème de CORS ni de `localhost` sous Windows, et le site marche aussi ouvert par `127.0.0.1` ou sur un autre port. Si une page affiche « Le serveur de ScholarFit ne répond pas », regarde le message dans la fenêtre « API ScholarFit ».

### À la main

```bash
# 1. API
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows : .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                 # facultatif : ajoute ta clé ANTHROPIC_API_KEY
python -m app.cli seed               # base SQLite + 133 opportunités (117 bourses, 10 stages, 6 conférences) + comptes de démo (local uniquement)
uvicorn app.main:app --reload --port 8000

# 2. Site (dans un autre terminal)
cd frontend
npm install
npm run dev                          # relaie /api vers http://127.0.0.1:8000
```

- Site : http://localhost:3000
- Documentation interactive de l'API : http://localhost:8000/docs

### Avec Docker (PostgreSQL)

Le pilote PostgreSQL est dans `backend/requirements-postgres.txt` (installé par le Dockerfile) : l'installation locale avec SQLite n'en a pas besoin.


```bash
docker compose up --build
```

Lance PostgreSQL, l'API et le site. Pour activer l'IA : `ANTHROPIC_API_KEY=sk-... docker compose up --build`.

### Comptes de démo

| Rôle | E-mail | Mot de passe |
|---|---|---|
| Étudiante (profil rempli : Sénégal, master en informatique) | `demo@example.org` | `demo12345` |
| Administrateur | `admin@example.org` | `admin12345` |
| Conseiller (accompagnement, français/anglais, France, Canada, Belgique) | `conseiller@example.org` | `conseil12345` |

Ces trois comptes sont créés **et réparés à chaque démarrage de l'API** (`app/demo.py`) : même si l'API est lancée sans `start.ps1`, depuis un autre dossier, ou si `ADMIN_EMAILS` contient votre propre adresse, ces identifiants marchent. Après la connexion, chacun arrive sur son tableau de bord : « Mes bourses » pour l'étudiante, `/admin` pour l'administrateur, `/conseiller` pour le conseiller. La base SQLite est toujours `backend/bourses.db`, quel que soit le dossier de lancement.

Ces comptes n'existent qu'en local : en ligne (`APP_ENV=production` ou base PostgreSQL), ils sont désactivés automatiquement à chaque démarrage. Pour vous donner les droits d'administrateur en ligne : `python -m app.cli make-admin votre.adresse@gmail.com` (voir DEPLOIEMENT.md 6.6).

### Comptes, confirmation de l'e-mail et mot de passe oublié

- L'inscription demande un **prénom ou nom d'utilisateur**, affiché ensuite en haut de l'espace (« Salut, Awa »). Il se modifie dans Profil > Mon compte. Les anciens comptes sans nom affichent le prénom du profil, sinon le début de l'e-mail.
- Après l'inscription, un **e-mail de confirmation** part avec un lien valable 48 h (`VERIFY_LINK_HOURS`). Tant que l'adresse n'est pas confirmée, un bandeau le rappelle dans l'espace avec un bouton « Renvoyer le lien » (un envoi par minute au plus).
- **Mot de passe oublié** : lien sous le champ mot de passe de la connexion. L'e-mail contient un lien valable 60 min (`RESET_LINK_MINUTES`) qui ne sert qu'une fois. La réponse est la même que l'adresse ait un compte ou non.
- **Sans SMTP configuré** (en local), les e-mails ne partent pas : ils sont écrits dans la fenêtre « API ScholarFit », lien compris. Copiez le lien dans le navigateur.
- **Pour envoyer de vrais e-mails**, renseignez dans `backend/.env` : `SMTP_HOST`, `SMTP_PORT` (587, ou 465 avec `SMTP_SSL=true`), `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, et `SITE_URL` (adresse publique du site, utilisée dans les liens). Brevo (300 e-mails par jour gratuits), Mailjet ou un compte Gmail avec mot de passe d'application conviennent.

## Collecte des bourses, stages et conférences dans le monde entier

### Ce qui tourne tout seul

Quand l'API est lancée, elle regarde **une fois par jour** (`AUTO_COLLECT_HOURS=24`, `app/scheduler.py`) quelles sources sont dues, chacune selon sa fréquence (**une fois par semaine**, 168 h, pour les sites et l'IA, afin de limiter le nombre de requêtes). Les alertes, rappels et expirations restent quotidiens. Les nouvelles fiches apparaissent sur le site dès qu'elles sont en base :

1. **Sources déclarées** dans `backend/app/data/sources.json` dont la fréquence est écoulée, dont **13 sites d'annonces** : Afri-Carrières, Opportunities For Africans, Opportunity Desk, Scholars4Dev, After School Africa, Opportunities Circle, Youth Opportunities, Scholarship Positions, World Scholarship Forum, Scholarships Ads, Scholarship Roar, Study Abroad Nations, Opportunities Corners (connecteur `site`), plus Conference Index et l'annuaire **Campus Bourses** de Campus France (connecteur `campusbourses` : lecture de son API JSON ouverte, programmes annuels pour étudier en France, marqués récurrents). EURAXESS est désactivée : plus de flux RSS, et le site bloque les robots. **Huit types d'opportunités** sont collectés : bourses, stages, conférences, formations, concours, programmes d'échange (écoles d'été, camps), fellowships et cours en ligne (`vocab.KINDS`). Un site peut être lu **par catégorie** (`feeds` : `{"url", "kind"}`) : le type donné par la catégorie prime, et `exclude_pattern` écarte guides, conseils de visa et emplois avant toute lecture. Activer ou désactiver une source dans `sources.json` s'applique aussi à une base existante. Les 3 premières pages du flux RSS sont lues (sinon les annonces de la page d'accueil), jusqu'à 60 annonces nouvelles par site et par passage ; une annonce déjà lue n'est pas relue ; les offres d'emploi sont écartées ; le lien gardé est celui du **site officiel** cité dans l'annonce (la page de l'agrégateur reste dans `source_page`) ;
2. **Stages des organisations internationales** via l'API ReliefWeb (ONU OCHA, connecteur `reliefweb`) : tous les stages publiés par les agences de l'ONU, les ONG et les organisations internationales, avec le pays du stage et la date de clôture. Il faut un nom d'application gratuit, à demander sur https://apidoc.reliefweb.int, à mettre dans `RELIEFWEB_APPNAME` ;
3. **Découverte par l'IA** (`app/scrapers/discovery.py`) : Claude cherche sur le web une fois par semaine, sur les **46 zones** en un seul passage : les régions du monde (Afrique en 5 zones, Europe en 6, Amériques, Moyen-Orient, Asie, Océanie, programmes internationaux), des pays d'études africains (Ghana, Nigeria, Sénégal, Côte d'Ivoire, Togo, Bénin, Maroc, Égypte, Rwanda, Kenya), les publics (femmes, réfugiés, revenus modestes), les domaines (informatique, santé, agriculture et climat, ingénierie et sciences, droit et économie, arts et journalisme), les niveaux (licence, doctorat et post-doc, écoles d'été), 10 zones de stages (ONU et agences, Banque mondiale, FMI, BAD, BCEAO, Union africaine, CEDEAO, OIF, institutions européennes, ONG, entreprises par continent) et les conférences. Le monde entier est parcouru à chaque passage hebdomadaire. Chaque lien est testé avant enregistrement (un lien mort n'entre pas en base). Les fiches réservées à un public (par exemple les femmes) sont marquées comme telles ;
4. **Dates limites** : une bourse annuelle dont la date vient de passer est signalée « session close » avec la session suivante estimée ; une bourse ponctuelle passe en « expirée » ;
5. **Vérification des liens officiels** (`app/linkcheck.py`) : `ok`, `redirige` (on garde la nouvelle adresse), `casse` (signalé dans l'administration), `non_verifie` ;
6. **Alertes** (nouvelles bourses pour le profil, rappels J-30, J-7, J-1) et rappels d'accompagnement.

La découverte IA a besoin de `ANTHROPIC_API_KEY` dans `backend/.env` ; sans clé, le reste tourne quand même. Pour ne pas laisser l'API faire la collecte, mets `AUTO_COLLECT_HOURS=0` et planifie `python -m app.cli nightly` (cron, ou Planificateur de tâches sous Windows).

### Coût de l'IA pendant la collecte

- **Pages déjà lues** (`seen_pages`) : chaque annonce est mémorisée avec l'empreinte de son texte, qu'elle ait donné une fiche ou non (offre d'emploi…). Une annonce relayée n'est plus jamais retéléchargée ; une page de liste n'est relue par l'IA que si son texte a changé.
- **Traitement par lots** (`app/ai/batch.py`, Message Batches API, **moitié prix**) : l'extraction des annonces, la mise en forme des recherches de la découverte et les traductions sont mises en file pendant le passage, envoyées en un lot à la fin, et appliquées au passage suivant (la plupart des lots finissent en moins d'une heure, 24 h au plus). Un travail échoué retombe sur l'extraction par règles. `AI_USE_BATCH=false` pour revenir aux appels immédiats. La recherche web elle-même reste immédiate (un lot ne peut pas enchaîner des recherches).
- **Extraction en deux temps** (idée reprise d'Opportia, `app/scrapers/extract.py`) : un premier passage par un modèle économique (`EXTRACT_MODEL`, Claude Haiku 5.5 par défaut) produit la fiche avec, pour la date limite, les conditions et le financement, une **preuve** recopiée mot pour mot de la page. Un contrôle sans IA vérifie que chaque preuve se trouve bien dans la page, que la date limite n'est pas oubliée alors que la page en parle, et que le niveau d'études est indiqué. Seules les fiches douteuses partent en **relecture** chez le modèle principal (`REVIEW_MODEL`, sinon `CLAUDE_MODEL`), qui ne renvoie que les champs à corriger. Avec `EXTRACT_PROVIDER=ollama`, le premier passage se fait sur une machine à vous (Ollama, `OLLAMA_URL`, `OLLAMA_MODEL`), gratuitement ; la relecture ciblée reste chez Claude. Les fiches restent « à vérifier » par l'administration.
- **Réponses réutilisées** (`ai_cache`, `AI_CACHE_DAYS`, 30 jours) : diagnostic de CV, conseils de compatibilité et lecture des messages du chat ; une demande identique reprend la réponse gardée. Les CV adaptés et les lettres ne sont pas concernés (régénérer doit donner une nouvelle version).
- Le tableau « Coût de l'IA » de l'administration montre aussi les travaux en file, envoyés, faits et échoués.

### Commandes

```bash
python -m app.cli nightly                       # un passage complet (sources, IA, dates, liens, alertes)
python -m app.cli discover --zones 20           # découverte IA sur tout le monde d'un coup
python -m app.cli check-links --all             # teste tous les liens officiels et liste les liens morts
python -m app.cli translate                     # version anglaise des fiches qui n'en ont pas (IA)
python -m app.cli collect                       # toutes les sources activées
python -m app.cli extract https://exemple.org/une-bourse   # teste l'extraction d'une page
```

> La vérification des liens n'a pas pu être lancée depuis l'environnement de développement (sites externes bloqués). Lance `python -m app.cli check-links --all` une fois chez toi : il affiche les liens à corriger.

### Connecteurs

| Connecteur | Usage | Paramètres |
|---|---|---|
| `ai_discovery` | Recherche web par l'IA, zone par zone | `zones_per_run`, `frequency_hours` |
| `site` | Site d'annonces à structure inconnue (agrégateur) | `url`, `limit`, `feeds`, `feed_pages`, `paths`, `link_pattern`, `kind` |
| `reliefweb` | Stages ONU, ONG et organisations internationales (API ReliefWeb) | `limit`, `RELIEFWEB_APPNAME` dans `.env` |
| `json` | Export officiel, partenariat, fichier local | `path` ou `url` |
| `rss` | Flux RSS ou Atom dont chaque entrée pointe vers une bourse | `url`, `limit` |
| `page_list` | Page « liste de bourses » + liens vers les fiches | `url`, `link_selector` (CSS), `link_pattern` (regex), `limit` |

Règles de collecte (`app/scrapers/base.py`) : lecture de `robots.txt`, une requête toutes les 5 secondes par domaine, User-Agent identifiable, cache de 24 h, seuls les faits sont stockés (l'IA reformule, rien n'est recopié), aucune donnée personnelle. Avant d'activer une nouvelle source, lis ses conditions d'utilisation ; EURAXESS reste désactivée (blocage des robots).

> **Données de départ** : 82 bourses, 10 stages (ONU, Banque mondiale, FMI, Commission et Parlement européens, BAD, Union africaine, UNICEF, OMS, Volontariat de la Francophonie) et 6 conférences (Deep Learning Indaba, Data Science Africa, One Young World, Forum jeunesse de l'ECOSOC, Women Deliver, YouthConnekt Africa). Bourses : 82 vrais programmes sur tous les continents (Eiffel, DAAD, Chevening, MEXT, Swedish Institute, Knight-Hennessy, KAUST, Manaaki, Université panafricaine, AIMS, AMCI…), avec 55 pays d'études. **Montants, dates limites et critères sont indicatifs** (les dates sont marquées « estimées ») et doivent être vérifiés sur chaque page officielle. Une base déjà créée reçoit les nouvelles colonnes au démarrage ; relance `python -m app.cli seed` pour charger les nouvelles bourses.

## API pour le site (nouveautés)

| Route | Rôle |
|---|---|
| `GET /api/scholarships` | `country_exact=true` : seulement les offres du pays (même total que `/api/stats/countries`). Filtre `kind` (`bourse`, `stage`, `conference` ; vide = tout), filtres `level`, `country`, `region` (afrique, europe, amerique, asie, oceanie), `domain`, `nationality`, `full_funding`, `deadline_status`, `include_expired`, tri `sort=priority` (urgentes d'abord) |
| `GET /api/scholarships/{id}` | En plus des champs de base : `eligibility_notes` (conditions détaillées), `documents` (pièces à fournir avec précisions), `application_steps` (comment postuler), `apply_url`, `link_status`, `deadline_status` (`urgente` ≤ 14 j, `bientot` ≤ 45 j, `ouverte`, `inconnue`, `expiree`), `priority`, `days_left`, `deadline_label`, `next_expected_deadline`, `regions`, et pour les stages et conférences `kind_label`, `event_start`, `event_end`, `city`, `remote`, `duration`, `source_page` |
| `GET /api/stats/countries` | Nombre réel de bourses par pays d'études, avec région, latitude et longitude (globe, carrousel) |
| `GET /api/stats` | Total, ouvertes, bientôt closes, expirées, nombre de pays, répartition par région et par type (`by_kind`) ; `/api/stats/countries` accepte aussi `kind` |
| `GET /api/matches?kind=stage` | Matching sur un type (bourses par défaut, `tout` pour tout) ; même paramètre sur `POST /api/questionnaire` |
| `GET /api/questionnaire` / `POST` | Questionnaire de profil en 5 étapes (vous, études, destination, langues, situation et besoin d'aide). Sans compte : nombre de bourses trouvées et 3 aperçus sans score ; avec compte : profil enregistré, toutes les bourses avec score, offre conseillée |
| `GET /api/offres` | Postuler seul (gratuit), Standard (15 000 F CFA), Premium (35 000 F CFA), avec l'offre conseillée selon le profil. Prix réglables (`OFFER_STANDARD_PRICE`, `OFFER_PREMIUM_PRICE`) |
| `POST /api/accompagnement` | Accepte `offer` (`standard` ou `premium`) ; prix figé et statut de paiement |
| `PATCH /api/admin/accompagnement/{id}/paiement` | L'admin marque le paiement reçu |
| `POST /api/admin/liens/verifier`, `GET /api/admin/liens/casses` | Vérifier les liens, lister les liens morts |
| `POST /api/auth/verification/envoyer`, `POST /api/auth/verification` | Renvoyer le lien de confirmation de l'e-mail, confirmer l'adresse avec le jeton du lien |
| `POST /api/auth/mot-de-passe-oublie`, `POST /api/auth/reinitialiser` | Recevoir un lien de réinitialisation, choisir un nouveau mot de passe avec ce lien |
| `PATCH /api/auth/me` | Changer son nom d'utilisateur |
| `GET /api/auth/email-disponible` | Prévenir dès la saisie qu'un compte existe déjà. Mot de passe : 8 caractères minimum avec une lettre et un chiffre |

### Version anglaise

Toutes les routes répondent en anglais avec `?lang=en` ou le cookie `sf_lang=en` ; sans l'un ni l'autre, rien ne change (français). Sont traduits : titre, résumé, conditions (`eligibility_notes`), pièces (`documents`), étapes (`application_steps`), `deadline_label`, `kind_label`, raisons et points à surveiller du matching, `/api/meta` (niveaux, domaines, régions, pays, couverture, pièces), `/api/questionnaire`, `/api/offres`, l'assistant `/api/chat` (qui comprend aussi les messages en anglais) et les alertes (dans la langue retenue pour le compte).

Les 98 fiches historiques ont leur version anglaise (les 35 ajoutées le 27/11/2026 sont traduites par l'IA à la première collecte ou avec `python -m app.cli translate`) dans `backend/app/data/scholarships_en.json`, chargée au démarrage. Les nouvelles fiches sont traduites par l'IA à chaque collecte automatique, ou à l'ouverture d'une fiche en anglais, puis gardées en base (`translations`). Pour tout traduire d'un coup : `python -m app.cli translate`.

Côté interface, le bouton **FR / EN** de l'en-tête enregistre le cookie `sf_lang` et recharge la page. Le serveur lit ce cookie (`lib/i18n-server.ts`) et écrit la langue dans `<html lang>` ; le navigateur la lit avec `useT()` (`components/LangProvider.tsx`). Chaque texte de l'interface passe par `t("texte en français")` ; sa version anglaise est dans `frontend/lib/i18n-en.ts` (un texte absent reste en français). Pour ajouter un texte : l'écrire en français dans `t(...)`, puis ajouter la ligne correspondante dans `i18n-en.ts`. Les noms de pays viennent de `Intl.DisplayNames`, les dates et montants suivent la langue choisie.

## Design

Identité propre : fond d'encre profonde, menthe pour les actions (boutons, score), ambre pour la mise en avant (mots en italique, dates limites). Titres en Montserrat, texte en Poppins. Tout le site vouvoie l'utilisateur.

- Accueil : globe terrestre animé (`components/WorldGlobe.tsx`, canvas, se fait tourner à la souris ou au doigt) avec un halo par pays proportionnel au nombre de bourses, carrousel des pays avec les vrais chiffres (`/api/stats/countries`), sections qui apparaissent au défilement (`components/Reveal.tsx`). Les points or qui clignotent sont les pays où il y a des bourses, les points gris les terres sans bourse (légende sous le globe). Les animations s'arrêtent si le système demande moins de mouvement.
- Connexion et inscription dans une fenêtre par-dessus la page (`components/AuthModal.tsx`, illustration `StudentsIllustration.tsx`) ; `/connexion` reste une vraie page.
- Dons : section « Soutenir le site » sur l'accueil et page `/soutenir`. Un clic sur un moyen de paiement (Flooz, Mixx by Yas, carte bancaire, Taptap Send, LemFi, PI-SPI) affiche le numéro et le copie.
- Carrousel des pays : 4 pays visibles au plus, un pas toutes les 5 secondes ; un clic ouvre `/bourses?country=XX&country_exact=true&kind=bourse`, avec exactement le nombre affiché.
- Drapeaux des pays (`components/Flag.tsx`, fichiers SVG du paquet libre flag-icons dans `public/flags/`) sur les fiches, la recherche, le carrousel et le bandeau défilant sous les chiffres clés.
- Stages et conférences : section dédiée sur l'accueil (`components/KindsShowcase.tsx`), lien « Stages » dans le menu, onglets Bourses / Stages / Conférences / Tout en haut de `/bourses`.
- Petites illustrations animées (`components/Illustrations.tsx`) dans les espaces vides, chiffres qui défilent (`components/CountUp.tsx`).
- Responsive : vérifié sans débordement de 340 px à 1920 px ; les titres changent de taille selon l'écran, et toute l'échelle se réduit un peu sous 380 px (`globals.css`).
- Pied de page commun (`components/Footer.tsx`) avec logo et liens, sur le site public et dans l'espace connecté.
- Comptes : champs compatibles avec le remplissage automatique et les gestionnaires de mots de passe (`autocomplete`), mot de passe suggéré, e-mail déjà utilisé signalé, retour à la page demandée après connexion (`/connexion?next=…`).

- **Sombre par défaut**, avec un bouton soleil / lune dans l'en-tête pour passer en **mode clair**. Le choix est mémorisé dans le navigateur (`localStorage`, clé `bm_theme`) et appliqué avant l'affichage pour éviter un flash.
- Les couleurs sont des variables dans `frontend/app/globals.css` (`@theme` pour le sombre, `html[data-theme="light"]` pour le clair). Les panneaux de score restent sombres dans les deux modes.
- Pages publiques (accueil, connexion, liste des bourses sans compte) : en-tête simple. Appli connectée : barre latérale (`components/Shell.tsx`). Sans compte, les scores sont masqués et invitent à s'inscrire.

## Logo

Le symbole est le logo fourni (deux formes en S, menthe en haut, ambre en bas), redessiné en vectoriel aux couleurs du site. Fichiers dans `frontend/public/brand/` :

- `scholarfit-logo-sombre.svg` et `scholarfit-logo-clair.svg` : symbole + nom en Montserrat, pour fond sombre ou clair (texte vectorisé, aucune police nécessaire) ;
- `scholarfit-symbole.svg` et `scholarfit-symbole-inverse.svg` : symbole seul ;
- `scholarfit-icone.svg` : icône d'appli sur fond carré sombre.

Le favicon (`app/icon.svg`, `app/favicon.ico`) et l'icône Apple (`app/apple-icon.png`) sont pris en compte automatiquement par Next.js. Dans le site, le logo est dessiné par `LogoMark` / `Logo` (`components/Icon.tsx`) et suit le thème.

## Structure

```
backend/                      API FastAPI (Python)
  app/
    main.py                   point d'entrée
    models.py                 tables : bourses, sources, utilisateurs, profils, candidatures, documents, alertes
    matching.py               filtres durs, score, explications, complétude du profil
    alerts.py                 nouvelles bourses et rappels de date limite (branche ici l'e-mail ou WhatsApp)
    coaching.py               accompagnement : choix du conseiller, plan d'étapes daté, rappels
    ai/                       client Claude avec repli hors-ligne, chat, CV et lettres
    scrapers/                 collecte polie, extraction, dédoublonnage, connecteurs
    routers/                  routes de l'API
    data/                     sources.json, bourses d'exemple
    cli.py                    seed, collect, extract, nightly
  tests/                      tests (pytest), sans réseau ni clé API
frontend/                     site Next.js 15 (React, TypeScript, Tailwind)
  app/                        pages : accueil, bourses, profil, mes-bourses, suivi, accompagnement, conseiller, cv, lettre, admin
  components/                 cartes de bourses, chat, sélecteur de pays…
  lib/api.ts                  client de l'API
docker-compose.yml            PostgreSQL + API + site
.github/workflows/ci.yml      tests et build à chaque push
```

## Tests

```bash
<<<<<<< HEAD
cd backend && python -m pytest -q        # 90 tests, sans réseau ni clé API (dont sécurité, alertes, signalements, audit, agenda, coûts IA)
cd frontend && npm run typecheck && npm run build
```

**Test de bout en bout**, contre une plateforme qui tourne déjà (passe par le site, comme un visiteur : catalogue, aperçu des liens, application installable, inscription, sécurité, profil, suivi, agenda, recherches, signalement, export, mot de passe, administration, suppression du compte de test) :

```bash
python scripts/e2e_smoke.py --base http://localhost:3000 --admin admin@example.org:admin12345
```

Pour tester le service worker sans arrêter `npm run dev` : `NEXT_DIST_DIR=.next-prod npm run build` puis `NEXT_DIST_DIR=.next-prod npx next start -p 3200`.
=======
cd backend && python -m pytest -q        # 72 tests : paiement en ligne, e-mails et rappels, pages pays, documents d'accompagnement, API, comptes (démo, e-mail, mot de passe oublié), matching, chat, CV, lettres, admin, accompagnement, monde entier, dates limites, questionnaire, offres, liens, stages et conférences, agrégateurs, IA simulée
cd frontend && npm run typecheck && npm run build
```

Tests de bout en bout (vrai navigateur, site et API lancés, `PAYMENT_PROVIDER=simulation`) : connexion, questionnaire et scores, page Postuler, CV, abonnement payé, accompagnement payé avec envoi d'un document, pages publiques sur ordinateur et mobile.

```bash
cd e2e && npm install && npx playwright install chromium
npx playwright test                       # E2E_BASE_URL=https://www.votre-domaine.org pour tester le site en ligne
```

## Lancement : paiement, e-mails, pages pays, pages légales

- **Paiement en ligne (CinetPay)** : abonnement CV (2 500 F CFA), accompagnement Standard (15 000 F CFA) et Premium (35 000 F CFA). `app/payments.py`, `app/routers/payments.py`, pages `/paiement/simulation` (guichet d'essai) et `/paiement/retour`. Le statut est toujours revérifié auprès de CinetPay, l'accès n'est accordé qu'une fois, et les paiements restés en attente sont revérifiés toutes les 15 minutes. Le paiement par transfert reste proposé en dessous. Suivi dans /admin > Paiements en ligne.
- **E-mails** (`app/mailer.py`, partagé avec les comptes) : console, SMTP, Brevo ou Resend. Rappels J-30, J-14, J-7, J-3, J-1 ; nouvelles bourses groupées en un seul e-mail ; reçus de paiement ; messages d'accompagnement (au plus un e-mail toutes les 30 minutes). Tout envoi est tracé dans `email_log`. Essai : `python -m app.cli test-email vous@exemple.org`.
- **Qualité des offres** : les offres expirées et celles dont le lien officiel est mort ne sont plus affichées ni comptées ; chaque fiche indique sa date de mise à jour.
- **Espace conseiller** : files « À traiter » (payé), « En attente de paiement » et « Clos », compteurs d'étapes en retard et de messages non lus. Onglet **Documents** dans chaque accompagnement : le candidat envoie ses pièces, l'expert livre les documents et la preuve de dépôt (PDF, Word, JPG, PNG, 8 Mo).
- **Référencement** : `/destinations` (pays par continent), `/destinations/france`, `/destinations/france/bourses|stages|conferences`, avec titre, description, adresse canonique et données structurées ; `sitemap.xml` et `robots.txt`.
- **Pages légales** : `/a-propos`, `/conditions`, `/confidentialite` (FR et EN), liées dans le pied de page. Identité de l'éditeur dans les variables `NEXT_PUBLIC_COMPANY_*` et `NEXT_PUBLIC_CONTACT_*`.
- **Mise en ligne** : `python -m app.cli check-config` liste ce qui manque ; `python -m app.cli backup` exporte toute la base. Voir DEPLOIEMENT.md partie 8.
>>>>>>> origin/main

## Variables d'environnement

Backend (`backend/.env`, voir `.env.example`) : `APP_ENV` (`production` en ligne), `DATABASE_URL`, `SECRET_KEY`, `SENTRY_DSN` (facultatif), `RATE_LIMIT_ENABLED` (par défaut `true`), `CORS_ORIGINS`, `ADMIN_EMAILS`, `DEMO_ACCOUNTS` (par défaut `true`), `SITE_URL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_SSL`, `VERIFY_LINK_HOURS`, `RESET_LINK_MINUTES`, `ANTHROPIC_API_KEY`, `CLAUDE_MODEL` (par défaut `claude-opus-5-5`), `AI_FREE_GENERATIONS_PER_DAY`, `COACHING_AUTO_ASSIGN` (par défaut `true` ; à `false`, chaque demande d'accompagnement attend qu'un administrateur choisisse le conseiller), `SCRAPER_USER_AGENT`, `SCRAPER_MIN_DELAY_SECONDS`, `OFFER_STANDARD_PRICE`, `OFFER_PREMIUM_PRICE`, `AUTO_COLLECT_HOURS` (6 par défaut, 0 pour désactiver), `RELIEFWEB_APPNAME`, `AI_DISCOVERY_ENABLED`, `AI_DISCOVERY_MAX_SEARCHES`, `API_PUBLIC_URL`, `PAYMENT_PROVIDER` (`simulation` par défaut, `cinetpay`, `manuel`), `CINETPAY_APIKEY`, `CINETPAY_SITE_ID`, `CINETPAY_SECRET_KEY`, `EMAIL_BACKEND` (`console`, `smtp`, `brevo`, `resend`), `EMAIL_REPLY_TO`, `BREVO_API_KEY`, `RESEND_API_KEY`.

Site (`frontend/.env.local`) : `API_URL_INTERNAL` (adresse de l'API pour le serveur Next.js, `http://127.0.0.1:8000` par défaut) ; `NEXT_PUBLIC_API_URL` seulement si l'API est sur un autre domaine en production (sinon laisser vide) . Les numéros de don (Flooz, Mixx by Yas) sont dans `frontend/components/Support.tsx` (constante `NUMBERS`), les logos dans `frontend/public/paiement/`.

## Ce qui reste à faire (suite du plan)

<<<<<<< HEAD
- **Paiement en ligne** : brancher un agrégateur Mobile Money (CinetPay, PayDunya, Wave, Orange Money) sur `POST /api/accompagnement`.
- **Alertes WhatsApp ou Telegram** : un second canal dans `send_alert_emails` (`app/alerts.py`), à côté de l'e-mail.
- **Connecteurs réels** : vérifier robots.txt et conditions de chaque source, ajuster les sélecteurs, demander des partenariats.
- **Recherche sémantique** : remplacer la similarité par mots-clés par des embeddings stockés dans PostgreSQL avec pgvector.
=======
- **Paiement en ligne** : ouvrir le compte marchand CinetPay et faire un premier paiement réel (voir DEPLOIEMENT.md 8.3).
- **Alertes WhatsApp** : en plus des e-mails, via l'API WhatsApp Business.
- **Connecteurs réels** : vérifier robots.txt et conditions de chaque source, ajuster les sélecteurs, demander des partenariats.
- **Recherche sémantique** : remplacer la similarité par mots-clés par des embeddings stockés dans PostgreSQL avec pgvector.
- **Migrations de base** : les colonnes et index nouveaux sont ajoutés au démarrage ; passer à Alembic si le schéma doit un jour renommer ou supprimer des colonnes.
- **Vérification des fiches** : les 133 fiches de départ restent « à vérifier » (dates estimées d'après la session précédente) tant qu'un administrateur ne les a pas confirmées dans /admin (voir DEPLOIEMENT.md, « Entretien du site »).
>>>>>>> origin/main
- **Stockage des fichiers** : les CV sont stockés en texte dans la base ; pour garder les fichiers d'origine, ajouter un stockage S3 privé et chiffré.
- **Accompagnement** : envoyer les messages et rappels par e-mail ou WhatsApp, synchroniser les rendez-vous avec un agenda (fichier .ics, Google Agenda), joindre des fichiers aux messages, formules payantes si le modèle économique le prévoit, et un coach IA qui prépare les relectures pour le conseiller.
- **Base existante** : les nouvelles tables (`advisors`, `coachings`, `coaching_steps`, `coaching_messages`, `coaching_meetings`) sont créées au démarrage ; aucune table existante ne change, donc une base du MVP précédent continue de fonctionner (relance `python -m app.cli seed` pour y ajouter le compte conseiller de démo).
- **V2 / V3** : score de chance appris sur les résultats réels, formats de CV exportés en PDF, simulation d'entretien, témoignages et mentorat, gestion des lettres de recommandation des professeurs, alertes WhatsApp.

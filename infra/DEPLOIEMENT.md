# Guide de déploiement — Marswalk sur AWS Lightsail + S3 + CloudFront

## Architecture cible

```
Navigateur
  │
  └─► CloudFront (1 distribution, 4 behaviors)
        │
        ├─ /*          → S3 bucket (HTML/JS/CSS, frontend statique)
        ├─ /api/*      → Lightsail instance (Nginx → Uvicorn)
        ├─ /tiles/*    → Lightsail instance (Nginx → Uvicorn, FileResponse)
        └─ /ws/*       → Lightsail instance (Nginx → Uvicorn, WebSocket upgrade)

Lightsail Ubuntu 24.04 (2 GB RAM)
  └─ Docker Compose (infra/compose.prod.yaml)
       ├─ nginx:1.27-alpine  → ports 80/443, TLS Let's Encrypt
       ├─ marswalk-api       → port 8000 (interne), 1 worker Uvicorn
       └─ postgis/postgis:16-3.4  → port 5432 (interne)
```

---

## Prérequis

- Compte AWS avec droits S3, CloudFront, Lightsail, IAM
- `awscli` installé et configuré localement (`aws configure`)
- `pnpm` installé localement
- `git` installé localement
- Un nom de domaine dont tu contrôles le DNS (pour le certificat TLS)

---

## Étape 0 — Variables d'environnement locales

Copie `.env.prod.example` localement et remplis-le. Ces variables sont utilisées par les scripts.

```bash
cp .env.prod.example .env.local.sh
# Édite .env.local.sh, puis charge-le dans ta session :
source .env.local.sh
```

Variables à renseigner :
| Variable | Exemple | Rôle |
|---|---|---|
| `POSTGRES_USER` | `marswalk` | Utilisateur PostgreSQL |
| `POSTGRES_PASSWORD` | *(openssl rand -base64 32)* | Mot de passe PostgreSQL |
| `POSTGRES_DB` | `marswalk` | Nom de la base |
| `CLOUDFRONT_URL` | `https://d1a2b3c4.cloudfront.net` | Origine du frontend (CORS) |
| `MARSWALK_DOMAIN` | `api.marswalk.example.com` | Domaine de l'instance Lightsail |
| `BACKUP_BUCKET` | `mon-marswalk-backups` | Bucket S3 pour les sauvegardes |
| `FRONTEND_BUCKET` | `mon-marswalk-frontend` | Bucket S3 pour le frontend |
| `CF_DIST_ID` | `E1A2B3C4D5E6F7` | ID de la distribution CloudFront |
| `LIGHTSAIL_HOST` | `54.12.34.56` | IP ou DNS de l'instance Lightsail |

---

## Étape 1 — Création des ressources AWS

### 1.1 Instance Lightsail

1. Dans la console AWS Lightsail → **Create instance**
2. Platform : **Linux/Unix**, Blueprint : **Ubuntu 24.04 LTS**
3. Instance plan : **2 GB RAM** (2 vCPU, 60 GB SSD) — $10/mois
4. Instance name : `marswalk-prod`
5. **Enable static IP** et note l'IP publique → c'est `LIGHTSAIL_HOST`

### 1.2 Firewall Lightsail

Dans **Networking** de l'instance, ouvrir :
- TCP 80 (HTTP)
- TCP 443 (HTTPS)
- TCP 22 (SSH) — déjà ouvert par défaut

### 1.3 Bucket S3 frontend

```bash
aws s3 mb "s3://${FRONTEND_BUCKET}" --region us-east-1
# Désactiver "Block all public access"
aws s3api put-public-access-block \
  --bucket "${FRONTEND_BUCKET}" \
  --public-access-block-configuration \
  "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"
# Politique de lecture publique (CloudFront OAC préféré en production, mais voici la version simple)
aws s3api put-bucket-policy --bucket "${FRONTEND_BUCKET}" --policy '{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "PublicReadGetObject",
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::'"${FRONTEND_BUCKET}"'/*"
  }]
}'
# Activer l'hébergement statique (requis pour CloudFront origin)
aws s3 website "s3://${FRONTEND_BUCKET}" \
  --index-document index.html \
  --error-document index.html
```

### 1.4 Bucket S3 sauvegardes

```bash
aws s3 mb "s3://${BACKUP_BUCKET}" --region us-east-1
# Les sauvegardes restent privées, pas de politique publique
```

### 1.5 Distribution CloudFront

Crée la distribution **depuis la console AWS** (l'API CLI est plus verbeuse). Paramètres clés :

**Origin 1 — S3 frontend (défaut)**
- Origin domain : `${FRONTEND_BUCKET}.s3-website-us-east-1.amazonaws.com`
- Protocol : HTTP only (S3 website endpoint n'a pas HTTPS)
- Default behavior : `/` → Cache policy = CachingOptimized

**Origin 2 — Lightsail API**
- Origin domain : `${MARSWALK_DOMAIN}` (ou IP publique provisoirement)
- Protocol : HTTPS only
- Origin path : laisser vide

**Behaviors (dans cet ordre de priorité) :**

| Priorité | Path pattern | Origin | Cache | Options supplémentaires |
|---|---|---|---|---|
| 1 | `/ws/*` | Lightsail | CachingDisabled | Allow HTTP methods: GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE — **ne pas cocher "Compress"** |
| 2 | `/tiles/*` | Lightsail | CachingOptimized (TTL 86400 s) | GET/HEAD uniquement |
| 3 | `/api/*` | Lightsail | CachingDisabled | Tous les methods — Forward `Authorization` header |
| 4 | `/*` (défaut) | S3 | CachingOptimized | GET/HEAD |

**WebSocket sur CloudFront :** CloudFront supporte les WebSocket nativement depuis 2018 sur toute distribution. Aucune option spéciale à activer : il suffit que le behavior `/ws/*` ait **CachingDisabled** et autorise tous les HTTP methods. Nginx fait ensuite l'upgrade vers WebSocket.

**Note `evaSocketUrl()`** : le client TypeScript construit l'URL WebSocket depuis `window.location.host` et choisit `wss://` si la page est en HTTPS. Avec CloudFront en HTTPS, le WebSocket sera bien en `wss://`. Nginx reçoit le trafic sur le port 443 et fait l'upgrade.

---

## Étape 2 — Provisionnement de l'instance

```bash
# Depuis ta machine locale, dans le répertoire du dépôt
source .env.local.sh
ssh ubuntu@${LIGHTSAIL_HOST} "bash -s" < infra/scripts/bootstrap.sh
```

Le script `bootstrap.sh` :
- Installe Docker, git, awscli, Certbot
- Clone le dépôt dans `/opt/marswalk` (modifiable avec la variable `MARSWALK_DIR`)
- Configure UFW (80/443 ouverts)
- Enregistre les crons de sauvegarde et de renouvellement TLS

Après le bootstrap, copie le fichier de secrets sur l'instance :

```bash
scp .env.local.sh ubuntu@${LIGHTSAIL_HOST}:/opt/marswalk/.env.local.sh
ssh ubuntu@${LIGHTSAIL_HOST} "chmod 600 /opt/marswalk/.env.local.sh"
```

---

## Étape 3 — Démarrage initial des services

```bash
ssh ubuntu@${LIGHTSAIL_HOST}
cd /opt/marswalk

# Premier démarrage (db + api uniquement, sans nginx — TLS pas encore émis)
docker compose \
  --env-file /opt/marswalk/.env.local.sh \
  -f infra/compose.prod.yaml \
  up -d db api

# Attendre que l'API soit healthy (~30 s)
docker compose \
  --env-file /opt/marswalk/.env.local.sh \
  -f infra/compose.prod.yaml \
  ps
```

---

## Étape 4 — Certificat TLS Let's Encrypt

Le DNS de `MARSWALK_DOMAIN` doit pointer vers l'IP publique de l'instance avant cette étape.

```bash
ssh ubuntu@${LIGHTSAIL_HOST}

# Démarrer Nginx en HTTP uniquement (port 80) pour le challenge ACME.
# Temporairement, commenter le bloc server 443 dans nginx.conf ou utiliser --standalone.
# Option la plus simple avec --standalone (arrête nginx si actif) :
sudo certbot certonly \
  --standalone \
  -d ${MARSWALK_DOMAIN} \
  --agree-tos \
  -m admin@example.com \
  --non-interactive

# Les certificats sont dans /etc/letsencrypt/live/${MARSWALK_DOMAIN}/
# Note : nginx.conf utilise le token $MARSWALK_DOMAIN, substitué par envsubst au démarrage du conteneur.
# Les copier dans le volume Docker certbot_conf :
CERT_VOL=$(docker volume inspect marswalk-prod_certbot_conf --format '{{.Mountpoint}}')
sudo mkdir -p "${CERT_VOL}/live/${MARSWALK_DOMAIN}"
sudo cp /etc/letsencrypt/live/${MARSWALK_DOMAIN}/fullchain.pem "${CERT_VOL}/live/${MARSWALK_DOMAIN}/"
sudo cp /etc/letsencrypt/live/${MARSWALK_DOMAIN}/privkey.pem  "${CERT_VOL}/live/${MARSWALK_DOMAIN}/"
```

---

## Étape 5 — Démarrage de Nginx

```bash
ssh ubuntu@${LIGHTSAIL_HOST}
cd /opt/marswalk

docker compose \
  --env-file /opt/marswalk/.env.local.sh \
  -f infra/compose.prod.yaml \
  up -d nginx
```

Vérification :
```bash
curl -I https://${MARSWALK_DOMAIN}/api/health
# Doit retourner HTTP/2 200
```

---

## Étape 6 — Déploiement du frontend et des données

Depuis ta machine locale :

```bash
source .env.local.sh
# Déploie le frontend sur S3 + invalide CloudFront + déploie l'API + transfère Jezero
./infra/scripts/deploy.sh
```

Le script te demande une confirmation avant de transférer les 708 MB de données Jezero.

---

## Étape 7 — Vérifications finales

```bash
# Santé de l'API
curl https://${MARSWALK_DOMAIN}/api/health

# Réponse attendue (le champ database doit être "ok") :
# {"status":"ok","version":"0.1.0","database":"ok","sites":["jezero"],...}

# Une tuile
curl -I "https://${MARSWALK_DOMAIN}/tiles/jezero/hillshade/15/15232/13082.webp"
# Doit retourner 200 et Cache-Control: public, max-age=86400

# Frontend via CloudFront
curl -I "${CLOUDFRONT_URL}"
# Doit retourner 200

# WebSocket (nécessite wscat : npm i -g wscat)
wscat -c "wss://${MARSWALK_DOMAIN}/ws/eva/eva-demo"
# Doit retourner une connexion établie puis des messages JSON
```

---

## Mises à jour

```bash
# Depuis ta machine locale
source .env.local.sh
./infra/scripts/deploy.sh
# Les données Jezero ne sont retransférées que si tu réponds 'y' à la question.
# Pour ne mettre à jour que le backend :
./infra/scripts/deploy.sh --skip-frontend --skip-site-data
# Pour ne mettre à jour que le frontend :
./infra/scripts/deploy.sh --skip-site-data
```

La migration Alembic (`alembic upgrade head`) s'exécute automatiquement au redémarrage du conteneur API si `MARSWALK_DATABASE_URL` est défini. Elle est idempotente : si le schéma est déjà à jour, elle ne fait rien.

---

## Surveillance et logs

```bash
ssh ubuntu@${LIGHTSAIL_HOST}
cd /opt/marswalk

# Logs en temps réel
docker compose --env-file /opt/marswalk/.env.local.sh -f infra/compose.prod.yaml logs -f api
docker compose --env-file /opt/marswalk/.env.local.sh -f infra/compose.prod.yaml logs -f nginx

# Utilisation mémoire (surveiller que l'API reste sous ~1,2 GB)
docker stats

# Statut des services
docker compose --env-file /opt/marswalk/.env.local.sh -f infra/compose.prod.yaml ps
```

---

## Restauration depuis une sauvegarde

```bash
ssh ubuntu@${LIGHTSAIL_HOST}

# Télécharger un dump
aws s3 cp "s3://${BACKUP_BUCKET}/postgres/20260115_020000.dump" /tmp/restore.dump

# Restaurer (arrêt de l'API pour éviter les conflits)
docker compose --env-file /opt/marswalk/.env.local.sh -f infra/compose.prod.yaml stop api

docker compose --env-file /opt/marswalk/.env.local.sh -f infra/compose.prod.yaml \
  exec -T db \
  pg_restore -U ${POSTGRES_USER} -d ${POSTGRES_DB} --clean /tmp/restore.dump

docker compose --env-file /opt/marswalk/.env.local.sh -f infra/compose.prod.yaml start api
rm /tmp/restore.dump
```

---

## Résumé des fichiers créés

| Fichier | Rôle |
|---|---|
| `infra/compose.prod.yaml` | Compose de production (db + api + nginx) |
| `infra/docker/api.prod.Dockerfile` | Image API de production |
| `infra/docker/api.entrypoint.sh` | Wait-for-postgres + migration + uvicorn |
| `infra/nginx/nginx.conf` | Config Nginx (TLS, proxy, WebSocket) |
| `infra/scripts/bootstrap.sh` | Provisionnement initial de l'instance |
| `infra/scripts/deploy.sh` | Déploiement frontend + backend |
| `infra/scripts/backup.sh` | Sauvegarde PostgreSQL vers S3 |
| `.env.prod.example` | Référence des variables de production |
| `infra/DEPLOIEMENT.md` | Ce guide |

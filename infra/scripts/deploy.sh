#!/usr/bin/env bash
# =============================================================================
# deploy.sh — Déploiement complet de Marswalk sur AWS Lightsail + S3/CloudFront
#
# Usage :
#   ./infra/scripts/deploy.sh [--skip-frontend] [--skip-site-data]
#
# Prérequis locaux :
#   - awscli configuré (aws configure)
#   - pnpm installé
#   - ssh configuré vers l'instance Lightsail (~/.ssh/config ou LIGHTSAIL_HOST)
#   - Variables chargées localement : source .env.local.sh (modèle : .env.prod.example)
#
# Variables d'environnement requises en local :
#   LIGHTSAIL_HOST   IP ou nom DNS de l'instance Lightsail
#   LIGHTSAIL_USER   Utilisateur SSH (par défaut : ubuntu)
#   FRONTEND_BUCKET  Nom du bucket S3 du frontend
#   CF_DIST_ID       ID de la distribution CloudFront
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LIGHTSAIL_USER="${LIGHTSAIL_USER:-ubuntu}"
# Emplacement du dépôt sur l'instance
MARSWALK_DIR="${MARSWALK_DIR:-/opt/marswalk}"
# Fichier d'environnement sur l'instance (secrets, chmod 600)
MARSWALK_ENV_FILE="${MARSWALK_ENV_FILE:-${MARSWALK_DIR}/.env.local.sh}"
SKIP_FRONTEND=false
SKIP_SITE_DATA=false

for arg in "$@"; do
  case "$arg" in
    --skip-frontend)   SKIP_FRONTEND=true ;;
    --skip-site-data)  SKIP_SITE_DATA=true ;;
  esac
done

echo "=== Marswalk — déploiement de production ==="
echo "    Repo   : $REPO_ROOT"
echo "    Hôte   : ${LIGHTSAIL_HOST}"
echo "    Bucket : ${FRONTEND_BUCKET}"
echo ""

# ── 1. Build et déploiement du frontend sur S3 ──────────────────────────────
if [ "$SKIP_FRONTEND" = false ]; then
  echo "--- [1/4] Build du frontend React (pnpm build) ---"
  cd "$REPO_ROOT/web"
  PNPM="pnpm"; command -v pnpm >/dev/null || PNPM="npx -y pnpm@10.28.0"
  $PNPM install --frozen-lockfile
  $PNPM build
  cd "$REPO_ROOT"

  echo "--- [2/4] Synchronisation vers S3 ---"
  # Fichiers à nom fixe (index.html, service worker, manifeste) : no-cache, toujours refraîchis.
  NO_CACHE_FILES="index.html sw.js manifest.webmanifest mockServiceWorker.js"
  # Assets statiques (hash dans le nom) : cache longue durée.
  # Pas de --delete : les anciens assets restent servis aux onglets encore ouverts.
  aws s3 sync web/dist/ "s3://${FRONTEND_BUCKET}/" \
    $(for f in $NO_CACHE_FILES; do printf -- '--exclude %s ' "$f"; done) \
    --cache-control "public, max-age=31536000, immutable"
  for f in $NO_CACHE_FILES; do
    [ -f "web/dist/$f" ] || continue
    aws s3 cp "web/dist/$f" "s3://${FRONTEND_BUCKET}/$f" \
      --cache-control "no-cache, no-store, must-revalidate"
  done

  echo "--- [3/4] Invalidation CloudFront (index.html et sw.js) ---"
  aws cloudfront create-invalidation \
    --distribution-id "${CF_DIST_ID}" \
    --paths "/" "/index.html" "/sw.js" "/manifest.webmanifest"
  echo "    Invalidation envoyée (propagation ~60 s)."
else
  echo "--- [1-3/4] Frontend ignoré (--skip-frontend) ---"
fi

# ── 2. Déploiement du backend sur Lightsail ──────────────────────────────────
echo "--- [4/4] Déploiement du backend sur ${LIGHTSAIL_HOST} ---"
ssh "${LIGHTSAIL_USER}@${LIGHTSAIL_HOST}" "MARSWALK_DIR='${MARSWALK_DIR}' MARSWALK_ENV_FILE='${MARSWALK_ENV_FILE}' bash -s" << 'REMOTE'
set -euo pipefail
cd "$MARSWALK_DIR"

echo "[remote] git pull…"
git pull --ff-only

echo "[remote] Build de l'image API…"
sudo docker compose \
  --env-file "$MARSWALK_ENV_FILE" \
  -f infra/compose.prod.yaml \
  build api

echo "[remote] Redémarrage de l'API (zero-downtime : db et nginx restent actifs)…"
sudo docker compose \
  --env-file "$MARSWALK_ENV_FILE" \
  -f infra/compose.prod.yaml \
  up -d --no-deps api

echo "[remote] Attente du healthcheck API…"
attempt=0
until sudo docker compose \
  --env-file "$MARSWALK_ENV_FILE" \
  -f infra/compose.prod.yaml \
  exec -T api \
  python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" \
  2>/dev/null; do
  attempt=$((attempt + 1))
  [ $attempt -ge 20 ] && echo "[remote] API injoignable après 20 tentatives" && exit 1
  echo "[remote] tentative $attempt/20…"
  sleep 5
done

echo "[remote] Déploiement terminé."
REMOTE

# ── 3. Transfert optionnel des données Jezero ────────────────────────────────
if [ "$SKIP_SITE_DATA" = false ] && [ -d "$REPO_ROOT/data/packages/jezero" ]; then
  echo ""
  echo "--- [optionnel] Transfert du paquet Jezero (~708 MB) vers le volume Docker ---"
  echo "    Utilisez --skip-site-data pour ignorer cette étape."
  read -r -p "    Transférer maintenant ? [y/N] " confirm
  if [[ "$confirm" =~ ^[yY]$ ]]; then
    # Le volume Docker site_packages est dans /var/lib/docker/volumes/marswalk-prod_site_packages/_data/
    rsync -avz --progress \
      "$REPO_ROOT/data/packages/jezero/" \
      "${LIGHTSAIL_USER}@${LIGHTSAIL_HOST}:/tmp/jezero_transfer/"

    ssh "${LIGHTSAIL_USER}@${LIGHTSAIL_HOST}" "MARSWALK_DIR='${MARSWALK_DIR}' MARSWALK_ENV_FILE='${MARSWALK_ENV_FILE}' bash -s" << 'REMOTE_DATA'
set -euo pipefail
DEST=$(sudo docker volume inspect marswalk-prod_site_packages \
  --format '{{.Mountpoint}}' 2>/dev/null || echo "")
if [ -z "$DEST" ]; then
  echo "[remote] Volume marswalk-prod_site_packages introuvable." >&2
  echo "[remote] Lancez d'abord : docker compose ... up -d db api" >&2
  exit 1
fi
# /var/lib/docker n'est accessible qu'à root : sudo est requis pour écrire dans le volume.
sudo mkdir -p "$DEST/jezero"
sudo cp -r /tmp/jezero_transfer/. "$DEST/jezero/"
rm -rf /tmp/jezero_transfer
echo "[remote] Paquet Jezero installé dans $DEST/jezero/"
# L'API charge le catalogue des sites au démarrage : on la redémarre pour qu'elle voie Jezero.
cd "$MARSWALK_DIR"
sudo docker compose --env-file "$MARSWALK_ENV_FILE" -f infra/compose.prod.yaml restart api
echo "[remote] API redémarrée."
REMOTE_DATA
    echo "    Paquet Jezero transféré."
  else
    echo "    Transfert ignoré."
  fi
fi

echo ""
echo "=== Déploiement terminé. ==="
echo "    API  : https://${MARSWALK_DOMAIN:-<MARSWALK_DOMAIN>}/api/health"
echo "    Front: ${CLOUDFRONT_URL:-<CLOUDFRONT_URL>}"

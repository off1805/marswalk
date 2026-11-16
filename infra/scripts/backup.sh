#!/usr/bin/env bash
# =============================================================================
# backup.sh — Sauvegarde PostgreSQL vers S3
#
# Lancé par cron tous les jours à 02:00 (configuré par bootstrap.sh).
# Conserve les 30 derniers dumps, supprime les plus anciens.
#
# Prérequis :
#   - awscli configuré sur l'instance (aws configure, utilisateur IAM limité au bucket)
#   - Variable BACKUP_BUCKET dans $MARSWALK_DIR/.env.local.sh
# =============================================================================
set -euo pipefail

MARSWALK_DIR="${MARSWALK_DIR:-/opt/marswalk}"
ENV_FILE="${MARSWALK_ENV_FILE:-${MARSWALK_DIR}/.env.local.sh}"
export PATH="$PATH:/snap/bin"   # aws-cli installé par snap, absent du PATH de cron
if [ ! -f "$ENV_FILE" ]; then
  echo "Fichier $ENV_FILE introuvable." >&2
  exit 1
fi

# Charge uniquement les variables nécessaires (sans exporter tout le fichier)
BACKUP_BUCKET=$(grep '^BACKUP_BUCKET=' "$ENV_FILE" | cut -d= -f2 | tr -d '"' | tr -d "'")
POSTGRES_USER=$(grep '^POSTGRES_USER=' "$ENV_FILE" | cut -d= -f2 | tr -d '"' | tr -d "'")
POSTGRES_DB=$(grep '^POSTGRES_DB=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'"; true)
POSTGRES_DB="${POSTGRES_DB:-marswalk}"

if [ -z "$BACKUP_BUCKET" ]; then
  echo "BACKUP_BUCKET non défini dans $ENV_FILE." >&2
  exit 1
fi

DATE=$(date +%Y%m%d_%H%M%S)
DUMP_FILE="/tmp/marswalk_${DATE}.dump"

echo "[backup] Dump PostgreSQL ($POSTGRES_DB) → $DUMP_FILE"
sudo docker compose \
  --env-file "$ENV_FILE" \
  -f "$MARSWALK_DIR/infra/compose.prod.yaml" \
  exec -T db \
  pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB" > "$DUMP_FILE"

echo "[backup] Upload vers s3://${BACKUP_BUCKET}/postgres/${DATE}.dump"
aws s3 cp "$DUMP_FILE" "s3://${BACKUP_BUCKET}/postgres/${DATE}.dump"
rm -f "$DUMP_FILE"

echo "[backup] Rotation (conservation des 30 derniers dumps)…"
aws s3 ls "s3://${BACKUP_BUCKET}/postgres/" \
  | awk '{print $4}' \
  | grep '\.dump$' \
  | sort \
  | head -n -30 \
  | while read -r key; do
      echo "[backup] Suppression de s3://${BACKUP_BUCKET}/postgres/$key"
      aws s3 rm "s3://${BACKUP_BUCKET}/postgres/$key"
    done

echo "[backup] Terminé : $(date)"

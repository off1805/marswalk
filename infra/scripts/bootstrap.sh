#!/usr/bin/env bash
# =============================================================================
# bootstrap.sh — Provisionnement initial de l'instance Lightsail Ubuntu 24.04
#
# À exécuter UNE SEULE FOIS en SSH sur la nouvelle instance :
#   ssh ubuntu@<IP> "bash -s" < infra/scripts/bootstrap.sh
#
# Ce script :
#   1. Met à jour le système
#   2. Installe Docker + Docker Compose plugin + awscli
#   3. Clone le dépôt dans /home/ubuntu/marswalk
#   4. Crée le répertoire pour le fichier de secrets
#   5. Configure le pare-feu UFW (80/443 ouverts, 22 maintenu)
#   6. Installe Certbot pour Let's Encrypt
#   7. Prépare le cron de sauvegarde et de renouvellement du certificat
# =============================================================================
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/CHANGE_ME/marswalk.git}"
DEPLOY_DIR="/home/ubuntu/marswalk"

echo "=== [1/7] Mise à jour du système ==="
sudo apt-get update -y
sudo apt-get upgrade -y
sudo apt-get install -y curl git rsync awscli

echo "=== [2/7] Installation de Docker ==="
if ! command -v docker &>/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker ubuntu
  echo "Docker installé. Reconnectez-vous en SSH pour que le groupe docker prenne effet."
else
  echo "Docker déjà présent : $(docker --version)"
fi

echo "=== [3/7] Clone du dépôt ==="
if [ ! -d "$DEPLOY_DIR" ]; then
  git clone "$REPO_URL" "$DEPLOY_DIR"
else
  echo "Dépôt déjà présent dans $DEPLOY_DIR"
fi
chown -R ubuntu:ubuntu "$DEPLOY_DIR"

echo "=== [4/7] Répertoire des secrets ==="
touch /home/ubuntu/.env.prod
chmod 600 /home/ubuntu/.env.prod
echo "    Remplir /home/ubuntu/.env.prod en vous basant sur $DEPLOY_DIR/.env.prod.example"

echo "=== [5/7] Pare-feu UFW ==="
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
sudo ufw status

echo "=== [6/7] Certbot (Let's Encrypt) ==="
sudo apt-get install -y certbot
# Le renouvellement passe par le challenge webroot géré par Nginx.
# La première émission est effectuée manuellement après le premier démarrage de Nginx.

echo "=== [7/7] Crons (sauvegarde + renouvellement TLS) ==="
CRON_BACKUP="0 2 * * * /home/ubuntu/marswalk/infra/scripts/backup.sh >> /var/log/marswalk-backup.log 2>&1"
CRON_CERTBOT="0 4 * * * certbot renew --webroot -w /var/lib/docker/volumes/marswalk-prod_certbot_www/_data --quiet && docker compose --env-file /home/ubuntu/.env.prod -f /home/ubuntu/marswalk/infra/compose.prod.yaml exec nginx nginx -s reload"

(crontab -l 2>/dev/null | grep -v "marswalk"; echo "$CRON_BACKUP"; echo "$CRON_CERTBOT") | crontab -
echo "    Crons enregistrés."

echo ""
echo "=== Bootstrap terminé ==="
echo ""
echo "Étapes suivantes :"
echo "  1. Renseigner /home/ubuntu/.env.prod (voir $DEPLOY_DIR/.env.prod.example)"
echo "  2. Mettre à jour REPO_URL dans ce script si nécessaire, puis relancer"
echo "  3. Remplacer MARSWALK_DOMAIN dans infra/nginx/nginx.conf"
echo "  4. Lancer : docker compose --env-file /home/ubuntu/.env.prod \\"
echo "              -f /home/ubuntu/marswalk/infra/compose.prod.yaml up -d"
echo "  5. Émettre le certificat TLS :"
echo "     certbot certonly --webroot -w /var/lib/docker/volumes/marswalk-prod_certbot_www/_data \\"
echo "       -d \$MARSWALK_DOMAIN --agree-tos -m admin@example.com"
echo "  6. Redémarrer Nginx : docker compose ... restart nginx"

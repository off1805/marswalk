#!/bin/sh
# Hook de déploiement Certbot (à installer dans /etc/letsencrypt/renewal-hooks/deploy/).
# Copie le certificat renouvelé dans le volume Docker lu par nginx, puis recharge nginx.
set -e
D="${MARSWALK_DOMAIN:-marswalk-api.lecontineng.com}"
V=$(docker volume inspect marswalk-prod_certbot_conf --format '{{.Mountpoint}}')
mkdir -p "$V/live/$D"
cp -L "/etc/letsencrypt/live/$D/fullchain.pem" "/etc/letsencrypt/live/$D/privkey.pem" "$V/live/$D/"
docker exec marswalk-prod-nginx-1 nginx -s reload

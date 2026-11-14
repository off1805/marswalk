# Front Marswalk (Vite). Contexte de construction : racine du dépôt.
FROM node:22-slim
RUN corepack enable
WORKDIR /app
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY web/package.json web/
RUN pnpm install --frozen-lockfile
COPY contracts contracts
COPY fixtures fixtures
COPY web web
WORKDIR /app/web
EXPOSE 5173
CMD ["pnpm", "dev", "--host", "0.0.0.0"]

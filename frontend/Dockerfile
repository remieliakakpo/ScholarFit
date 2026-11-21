FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# Vide : le navigateur appelle /api sur le site, relayé vers l'API (même origine, cookie de session
# compris). Ne renseigner que si l'API est servie sur un autre domaine.
ARG NEXT_PUBLIC_API_URL=
# Adresse de l'API vue depuis le conteneur du site. Next.js l'inscrit dans le relais /api au moment
# de la compilation (next.config.mjs) : elle doit donc être connue ici, pas seulement au lancement.
ARG API_URL_INTERNAL=http://api:8000
# Adresse publique du site (aperçus des liens partagés)
ARG NEXT_PUBLIC_SITE_URL=http://localhost:3000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL API_URL_INTERNAL=$API_URL_INTERNAL NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]

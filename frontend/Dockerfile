# Multi-stage build dla produkcji

# Stage 1: Dependencies
FROM node:22-alpine AS deps
WORKDIR /app

# Kopiowanie plików package.json i package-lock.json (jeśli istnieje)
COPY package.json package-lock.json* ./

# Instalacja zależności - używamy install zamiast ci dla większej elastyczności
RUN npm install --frozen-lockfile --prefer-offline --no-audit || npm install --prefer-offline --no-audit

# Stage 2: Builder
FROM node:22-alpine AS builder
WORKDIR /app

# Kopiowanie zależności ze stage deps
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/package-lock.json ./package-lock.json

# Kopiowanie plików źródłowych
COPY . .

# Budowanie argumenty dla zmiennych środowiskowych w build time
ARG PUBLIC_API_URL
ENV PUBLIC_API_URL=$PUBLIC_API_URL

# Synchronizacja SvelteKit i build
RUN npm run build

# Stage 3: Runner
FROM node:22-alpine AS runner
WORKDIR /app

# Ustawienia środowiska produkcyjnego
ENV NODE_ENV=production

# Tworzenie użytkownika non-root dla bezpieczeństwa
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 sveltekit

# Kopiowanie zbudowanej aplikacji
COPY --from=builder --chown=sveltekit:nodejs /app/build ./build
COPY --from=builder --chown=sveltekit:nodejs /app/package.json ./package.json
COPY --from=builder --chown=sveltekit:nodejs /app/node_modules ./node_modules

# Przełączenie na użytkownika non-root
USER sveltekit

# Expose portu
EXPOSE 3000

# Zmienne środowiskowe runtime
ENV PORT=3000
ENV HOST=0.0.0.0

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3000', (r) => {process.exit(r.statusCode === 200 ? 0 : 1)})"

# Uruchomienie aplikacji
CMD ["node", "build"]

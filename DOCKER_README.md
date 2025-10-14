# Docker Configuration dla SPCloud

## Struktura

Projekt używa multi-container Docker setup z następującymi serwisami:

- **Frontend** (SvelteKit + Node.js 22)
- **Backend** (FastAPI + Python 3.13)
- **PostgreSQL** (baza danych)
- **MinIO** (S3-compatible storage)

## Dockerfile Frontend - Best Practices

Dockerfile frontendu został zbudowany z następującymi najlepszymi praktykami:

### 1. **Multi-stage Build**
- **Stage 1 (deps)**: Instalacja tylko zależności
- **Stage 2 (builder)**: Build aplikacji
- **Stage 3 (runner)**: Minimalny runtime image

### 2. **Bezpieczeństwo**
- Użycie non-root użytkownika (sveltekit:nodejs)
- Alpine Linux dla mniejszego footprint
- Health check dla monitorowania

### 3. **Optymalizacja**
- Cache layer dla node_modules
- `.dockerignore` eliminuje niepotrzebne pliki
- `npm ci` zamiast `npm install` dla deterministycznych builds
- Kompresja obrazu dzięki Alpine

### 4. **Zmienne środowiskowe**
- Build-time args dla PUBLIC_API_URL
- Runtime env variables z docker-compose
- Wszystkie zmienne w `.env`

## Konfiguracja

### 1. Skopiuj plik .env.example do .env:

```bash
cp .env.example .env
```

### 2. Edytuj .env według swoich potrzeb:

```env
# Frontend
PUBLIC_API_URL=http://localhost:8000
FRONTEND_PORT=3000

# Backend
DATABASE_URL=postgresql://user:password@db:5432/spcloud
SECRET_KEY=your-secret-key

# ... etc
```

## Uruchomienie

### Development (z hot-reload):

```bash
docker-compose up --build
```

### Production:

```bash
docker-compose up -d --build
```

### Tylko frontend:

```bash
docker-compose up frontend
```

### Sprawdzenie logów:

```bash
docker-compose logs -f frontend
```

### Zatrzymanie:

```bash
docker-compose down
```

### Czyszczenie volumes:

```bash
docker-compose down -v
```

## Porty

- **Frontend**: 3000 (konfigurowalny przez FRONTEND_PORT)
- **Backend**: 8000
- **PostgreSQL**: 5432 (konfigurowalny przez POSTGRES_PORT)
- **MinIO API**: 9000
- **MinIO Console**: 9001

## Network

Wszystkie serwisy są w dedykowanej sieci `spcloud_network` typu bridge, co umożliwia komunikację między kontenerami.

## Health Checks

Frontend ma skonfigurowany health check:
- Interval: 30s
- Timeout: 10s
- Start period: 40s
- Retries: 3

## Troubleshooting

### Problem z buildem frontendu:
```bash
docker-compose build --no-cache frontend
```

### Problem z połączeniem backend-frontend:
Upewnij się, że `PUBLIC_API_URL` w `.env` wskazuje na prawidłowy URL backendu.

### Problemy z permissions:
Dockerfile używa non-root user, więc wszystkie pliki muszą mieć odpowiednie uprawnienia.


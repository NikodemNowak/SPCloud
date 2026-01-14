# SPCloud - Dokumentacja Techniczna

## Architektura

SPCloud to chmura plików z autentykacją dwuskładnikową (TOTP), przechowywaniem na S3 i wersjonowaniem plików.

**Stack:** FastAPI + PostgreSQL + MinIO (S3-compatible) + Docker

---

## System Tokenów JWT

### Struktura Tokenów

| Token | Ważność | Przeznaczenie |
|-------|---------|---------------|
| **Access Token** | 15 minut | Autoryzacja requestów |
| **Refresh Token** | 1 dzień | Odświeżanie access tokena |
| **Setup Token** | 15 minut | Konfiguracja TOTP po rejestracji/logowaniu |

### Payload Tokenów

**Access Token:**
```
{
  "sub": "username",
  "iss": "SPCloud",
  "iat": 1736851200,
  "nbf": 1736851200,
  "exp": 1736852100,
  "jti": "abc123..."
}
```

**Refresh Token:**
```
{
  "sub": "username",
  "iss": "SPCloud",
  "iat": 1736851200,
  "nbf": 1736851200,
  "exp": 1736937600,
  "jti": "xyz789...",
  "type": "refresh"
}
```

**Setup Token (TOTP):**
```
{
  "sub": "username",
  "exp": 1736852100,
  "type": "totp_setup"
}
```

### Bezpieczeństwo

- Hashowanie haseł: **Argon2id** (time_cost=3, memory_cost=64MB, parallelism=2)
- Refresh tokeny przechowywane w bazie danych (tabela `refresh_tokens`)
- Wylogowanie = usunięcie wszystkich refresh tokenów użytkownika

---

## Flow Rejestracji i Logowania

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        REJESTRACJA / LOGOWANIE                              │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────┐     ┌──────────────────┐     ┌─────────────────────────┐
  │  POST        │     │  Sprawdź TOTP    │     │  Setup Token (15 min)   │
  │  /register   │────▶│  configured?     │────▶│  - type: "totp_setup"   │
  │              │     │  NIE             │     │  - sub: username        │
  └──────────────┘     └──────────────────┘     └─────────────────────────┘
                                                      │
                                                      ▼
                              ┌─────────────────────────────────────────────┐
                              │         KONFIGURACJA TOTP                    │
                              │  POST /totp/setup  →  QR Code + Secret      │
                              │  POST /totp/verify →  Access + Refresh Token │
                              └─────────────────────────────────────────────┘

  ┌──────────────┐     ┌──────────────────┐     ┌─────────────────────────┐
  │  POST        │     │  Sprawdź TOTP    │     │  Błąd 403               │
  │  /login      │────▶│  configured?     │────▶│  "TOTP verification     │
  │              │     │  TAK             │     │   required"             │
  └──────────────┘     └──────────────────┘     └─────────────────────────┘
                              │
                              │ NIE
                              ▼
                       ┌──────────────────┐
                       │  Setup Token     │  (ten sam flow co rejestracja)
                       └──────────────────┘

  ┌──────────────┐     ┌──────────────────┐     ┌─────────────────────────┐
  │  POST        │     │  Weryfikuj TOTP  │     │  Access + Refresh Token │
  │  /login/totp │────▶│  + zapisz w DB   │────▶│  (zapisz refresh token  │
  │              │     │  totp_configured │     │   w bazie)              │
  └──────────────┘     └──────────────────┘     └─────────────────────────┘
```

### Kluczowa specyfika: Setup Token

Setup Token to **jednorazowy token** służący wyłącznie do konfiguracji TOTP:

1. **Wygasa po 15 minutach** - jeśli użytkownik nie skonfiguruje TOTP, musi znowu przejść przez login
2. **Nie można go użyć do niczego innego** - dedykowany dependency `get_user_for_totp_setup` sprawdza `type: "totp_setup"`
3. **Blokuje ponowne użycie** - po skonfigurowaniu TOTP, token nie jest już ważny

---

## Przechowywanie Plików

### MinIO (S3-compatible)

- **Bucket per użytkownik:** `user-{username}` - izolacja danych
- **Struktura kluczy:** `{filename}_v{version}.{ext}` (np. `dokument_v3.txt`)

### Model danych

```
┌─────────────────┐     ┌──────────────────┐
│   FileStorage   │────▶│   FileVersion    │
│ (jeden wpis)    │     │ (wiele wersji)   │
├─────────────────┤     ├──────────────────┤
│ id (UUID)       │     │ id (UUID)        │
│ name            │     │ file_id (FK)     │
│ current_version │     │ version_number   │
│ size            │     │ path (S3 URL)    │
│ owner           │     │ size             │
│ is_favorite     │     │ created_by       │
└─────────────────┘     └──────────────────┘
```

### Wersjonowanie plików

| Akcja | Co się dzieje |
|-------|---------------|
| **Upload nowgo pliku** | Tworzy `FileStorage` + `FileVersion` (v1) |
| **Upload istniejącego** | Tworzy nową `FileVersion` (vN+1), aktualizuje `current_version` |
| **Restore** | Zmienia tylko `current_version` (bez kopii pliku!) |
| **Delete version** | Usuwa z S3 + bazy, nie pozwala usunąć current version |

### Limity

- **Domyślny storage:** 100 MiB na użytkownika
- **Liczenie użycia:** Sumuje rozmiar **wszystkich wersji** wszystkich plików

---

## Endpointy API

### Autentykacja

| Metoda | Endpoint | Opis |
|--------|----------|------|
| POST | `/api/v1/users/register` | Rejestracja → zwraca Setup Token |
| POST | `/api/v1/users/login` | Logowanie → Setup Token jeśli TOTP nie skonfigurowany |
| POST | `/api/v1/users/login/totp` | Logowanie z kodem TOTP → Access + Refresh |
| POST | `/api/v1/users/refresh` | Odśwież Access Token |
| POST | `/api/v1/users/logout` | Wylogowanie (usuwa refresh tokenty) |
| GET | `/api/v1/users/me` | Dane użytkownika |
| GET | `/api/v1/users/isadmin` | Sprawdź czy admin |

### TOTP

| Metoda | Endpoint | Opis |
|--------|----------|------|
| POST | `/api/v1/totp/setup` | Generuj QR Code + Secret (wymaga Setup Tokena) |
| POST | `/api/v1/totp/verify` | Weryfikuj TOTP → zwraca Access + Refresh Token |
| GET | `/api/v1/totp/status` | Sprawdź czy TOTP skonfigurowany |

### Pliki

| Metoda | Endpoint | Opis |
|--------|----------|------|
| POST | `/api/v1/files/upload` | Upload pliku |
| GET | `/api/v1/files/` | Lista plików |
| GET | `/api/v1/files/me` | Info o storage |
| GET | `/api/v1/files/download/{id}` | Download pliku |
| POST | `/api/v1/files/download` | Download wielu jako ZIP |
| DELETE | `/api/v1/files/{id}` | Usuń plik |
| POST | `/api/v1/files/change-is-favorite` | Oznacz/odznacz ulubiony |
| GET | `/api/v1/files/{id}/versions` | Lista wersji |
| GET | `/api/v1/files/{id}/versions/{n}` | Download konkretnej wersji |
| POST | `/api/v1/files/{id}/restore/{n}` | Przywróć wersję |
| DELETE | `/api/v1/files/{id}/versions/{n}` | Usuń wersję (nie current) |

### Admin

| Metoda | Endpoint | Opis |
|--------|----------|------|
| GET | `/api/v1/logs/download/{limit}` | Pobierz logi (tylko admin) |

---

## Logging

Każda akcja jest logowana do tabeli `logs`:

```python
LogAction = {
    "LOGIN", "LOGOUT", "REGISTER",
    "FILE_UPLOAD", "FILE_DOWNLOAD", "FILE_MANY_DOWNLOAD",
    "FILE_DELETE", "FILE_UPDATE", "FILE_RENAME",
    "FILE_FAVORITE", "FILE_UNFAVORITE",
    "FILE_VERSION_CREATE", "FILE_VERSION_RESTORE", "FILE_VERSION_DELETE",
    "LOG_DOWNLOAD"
}
```

Każdy log zawiera:
- timestamp (UTC)
- username
- action + status (SUCCESS/FAILED)
- file_id (opcjonalnie)
- details (JSON z IP, rozmiarem, błędami)

---

## Baza Danych

### Główne tabele

```sql
users (username PK)
  - hashed_password
  - user_type ('admin' | 'regular')
  - max_storage_mb (default 100)
  - used_storage_mb
  - totp_secret
  - totp_configured

files (id PK)
  - name
  - owner (FK → users.username)
  - current_version
  - size
  - is_favorite
  - created_at, updated_at

file_versions (id PK)
  - file_id (FK → files.id)
  - version_number
  - path (S3 URL)
  - size
  - created_by

refresh_tokens (id PK)
  - user_username (FK → users.username, CASCADE DELETE)
  - token (unique index)
  - expires_at
  - created_at

logs (id PK)
  - action
  - status
  - username (FK → users.username, CASCADE DELETE)
  - file_id
  - timestamp
  - details (JSON string)
```

---

## Konfiguracja (`.env`)

```bash
DB_URL=postgresql+asyncpg://user:secret@db:5432/mydb
JWT_SECRET=your-secret-key
JWT_EXPIRE_MIN=15
JWT_REFRESH_EXPIRE_DAYS=1
JWT_ISSUER=SPCloud
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false
```

---

## Specyficzne elementy warte uwagi

1. **Setup Token z TTL 15min** - wymusza szybką konfigurację TOTP, przeciwdziała "wiszącym" rejestracjom

2. **S3 bucket per user** - `user-{username}` zapewnia izolację na poziomie storage, nie trzeba sprawdzać uprawnień przy każdym operacji na pliku

3. **Restore bez kopiowania** - przywracanie wersji zmienia tylko `current_version` w bazie, nie kopiuje plików w S3

4. **Auto-recalculacja storage** - przy każdej operacji na plikach system przelicza rzeczywiste użycie storage (suma wszystkich wersji)

5. **Weryfikacja TOTP z valid_window=1** - akceptuje kod z przedziału ±30s, zwiększa UX kosztem minimalnego ryzyka bezpieczeństwa

6. **Argon2id z wysokim memory_cost** - 64MB RAM na operację hashowania znacząco utrudnia ataki brute-force

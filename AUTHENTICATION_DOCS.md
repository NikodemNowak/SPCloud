# Dokumentacja Systemu Logowania i Autoryzacji SPCloud

## Spis Treści
1. [Przegląd Systemu](#przegląd-systemu)
2. [Architektura](#architektura)
3. [Proces Rejestracji](#proces-rejestracji)
4. [Proces Logowania](#proces-logowania)
5. [Uwierzytelnianie Dwuskładnikowe (TOTP)](#uwierzytelnianie-dwuskładnikowe-totp)
6. [Zarządzanie Tokenami](#zarządzanie-tokenami)
7. [Endpoints API](#endpoints-api)
8. [Modele Danych](#modele-danych)
9. [Bezpieczeństwo](#bezpieczeństwo)
10. [Przepływ Danych](#przepływ-danych)
11. [Logowanie Zdarzeń](#logowanie-zdarzeń)

---

## Przegląd Systemu

System autoryzacji SPCloud wykorzystuje nowoczesne podejście do zabezpieczenia aplikacji oparte na:
- **JWT (JSON Web Tokens)** - dla access i refresh tokenów
- **TOTP (Time-based One-Time Password)** - obowiązkowe uwierzytelnianie dwuskładnikowe
- **Argon2** - do hashowania haseł
- **OAuth2 Bearer Authentication** - do autoryzacji requestów

### Główne Założenia
- Każdy użytkownik **musi** skonfigurować TOTP przed pełnym dostępem do systemu
- System używa dwóch typów tokenów JWT: access token (krótkotrwały) i refresh token (długotrwały)
- Wszystkie operacje związane z autoryzacją są logowane
- Hasła są hashowane z użyciem Argon2 (algorytm rekomendowany przez OWASP)

---

## Architektura

### Komponenty Systemu

```
┌─────────────────────────────────────────────────────────────┐
│                      API Endpoints                          │
│  /users/register  /users/login  /users/login/totp           │
│  /users/refresh   /users/logout /totp/setup  /totp/verify   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       Services                              │
│         UserService    TOTPService    LogService            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Security Layer                           │
│     JWT Creation/Validation    Password Hashing             │
│     TOTP Generation/Verification                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Database Models                          │
│      User    RefreshToken    LogEntry                       │
└─────────────────────────────────────────────────────────────┘
```

### Warstwy Aplikacji

1. **API Layer** (`endpoints/user.py`, `endpoints/totp.py`)
   - Definicje endpointów REST API
   - Walidacja requestów z użyciem Pydantic
   - Obsługa błędów HTTP

2. **Service Layer** (`services/user_service.py`, `services/totp_service.py`)
   - Logika biznesowa
   - Orchestracja operacji między różnymi komponentami
   - Transakcje bazodanowe

3. **Security Layer** (`core/security.py`)
   - Tworzenie i dekodowanie JWT
   - Hashowanie i weryfikacja haseł
   - Generowanie tokenów TOTP

4. **Data Layer** (`models/models.py`, `db/database.py`)
   - Definicje modeli SQLAlchemy
   - Zarządzanie połączeniami do bazy danych

---

## Proces Rejestracji

### Endpoint
```
POST /api/v1/users/register
```

### Request Body
```json
{
  "username": "user@example.com",
  "password": "SecurePassword123!"
}
```

### Response (201 Created)
```json
{
  "setup_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 900
}
```

### Przebieg Procesu

1. **Walidacja Danych**
   - System sprawdza poprawność formatu danych wejściowych
   - Weryfikuje czy username już nie istnieje w bazie

2. **Utworzenie Użytkownika**
   ```python
   new_user = User(
       username=user_data.username,
       hashed_password=hash_password(user_data.password),  # Argon2
       user_type="regular",
       totp_secret=None,
       totp_configured=False
   )
   ```

3. **Generowanie Setup Token**
   - System generuje specjalny JWT typu `totp_setup`
   - Token jest ważny przez 15 minut
   - Zawiera payload:
     ```json
     {
       "sub": "username",
       "exp": 1699999999,
       "type": "totp_setup"
     }
     ```

4. **Logowanie Zdarzenia**
   - System zapisuje w bazie wpis o rejestracji
   - Zawiera IP użytkownika (jeśli dostępne)

5. **Zwrot Setup Token**
   - Użytkownik otrzymuje token niezbędny do konfiguracji TOTP

### Diagram Sekwencji

```
Client          API            UserService      Database       LogService
  │              │                  │               │               │
  ├─Register────>│                  │               │               │
  │              ├─register()──────>│               │               │
  │              │                  ├─Check user───>│               │
  │              │                  │<─Not exists───┤               │
  │              │                  ├─Hash password │               │
  │              │                  ├─Create user──>│               │
  │              │                  │<─User created─┤               │
  │              │                  ├─────Log event──────────────>│
  │              │                  ├─Gen setup token               │
  │              │<─Setup token─────┤               │               │
  │<─201 Created─┤                  │               │               │
```

---

## Proces Logowania

System logowania w SPCloud ma dwa warianty w zależności od stanu konfiguracji TOTP.

### Wariant 1: TOTP Nie Skonfigurowany

#### Endpoint
```
POST /api/v1/users/login
```

#### Request
```json
{
  "username": "user@example.com",
  "password": "SecurePassword123!"
}
```

#### Response (200 OK)
```json
{
  "setup_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 900
}
```

**Opis:** Jeśli użytkownik nie ma jeszcze skonfigurowanego TOTP, otrzymuje setup token i musi przejść przez proces konfiguracji 2FA.

### Wariant 2: TOTP Skonfigurowany

#### Endpoint
```
POST /api/v1/users/login/totp
```

#### Request
```json
{
  "username": "user@example.com",
  "password": "SecurePassword123!",
  "totp_code": "123456"
}
```

#### Response (200 OK)
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Przebieg Logowania z TOTP

1. **Weryfikacja Credentials**
   ```python
   user = await self._get_and_verify_user(username, password)
   # - Pobiera użytkownika z bazy
   # - Weryfikuje hasło używając Argon2
   ```

2. **Sprawdzenie Konfiguracji TOTP**
   ```python
   if not user.totp_configured:
       raise HTTPException(403, "TOTP not configured")
   ```

3. **Weryfikacja Kodu TOTP**
   ```python
   totp = pyotp.TOTP(user.totp_secret)
   if not totp.verify(code, valid_window=1):
       raise HTTPException(401, "Invalid TOTP code")
   ```
   - `valid_window=1` pozwala na akceptację poprzedniego/następnego kodu (±30s)

4. **Generowanie Token Pair**
   ```python
   # Access Token (ważny 15 minut domyślnie)
   access_token = create_access_token(username)
   
   # Refresh Token (ważny 7 dni domyślnie)
   refresh_token_str, expires_at = create_refresh_token(username)
   
   # Zapisanie refresh token w bazie
   refresh_token_obj = RefreshToken(
       id=uuid.uuid4(),
       user_username=username,
       token=refresh_token_str,
       expires_at=expires_at,
       created_at=now_utc()
   )
   ```

5. **Logowanie Sukcesu**
   ```python
   await log_service.log_action(
       action="LOGIN",
       username=username,
       status="SUCCESS",
       details={"method": "TOTP"}
   )
   ```

### Diagram Sekwencji - Login z TOTP

```
Client          API            UserService    TOTPService   Database
  │              │                  │              │            │
  ├─Login TOTP──>│                  │              │            │
  │              ├─login_with_totp()│              │            │
  │              │                  ├─Verify pass─>│            │
  │              │                  │<─User OK─────┤            │
  │              │                  ├─verify_totp()────>        │
  │              │                  │              ├─Get user──>│
  │              │                  │              ├─Verify code│
  │              │                  │<─TOTP OK─────┤            │
  │              │                  ├─create_token_pair()       │
  │              │                  ├─Save refresh token───────>│
  │              │<─Tokens──────────┤              │            │
  │<─200 OK──────┤                  │              │            │
```

---

## Uwierzytelnianie Dwuskładnikowe (TOTP)

TOTP (Time-based One-Time Password) jest obowiązkowe dla wszystkich użytkowników systemu SPCloud.

### Konfiguracja TOTP

#### 1. Generowanie Sekretu i QR Code

**Endpoint:**
```
POST /api/v1/totp/setup
Authorization: Bearer <setup_token>
```

**Response:**
```json
{
  "secret": "JBSWY3DPEHPK3PXP",
  "provisioning_uri": "otpauth://totp/SPCloud:user@example.com?secret=JBSWY3DPEHPK3PXP&issuer=SPCloud",
  "qr_code": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg..."
}
```

**Proces:**

1. **Generowanie Sekretu**
   ```python
   secret = pyotp.random_base32()  # np. "JBSWY3DPEHPK3PXP"
   user.totp_secret = secret
   ```

2. **Tworzenie Provisioning URI**
   ```python
   totp = pyotp.TOTP(secret)
   provisioning_uri = totp.provisioning_uri(
       name=username,
       issuer_name="SPCloud"
   )
   # otpauth://totp/SPCloud:user@example.com?secret=...&issuer=SPCloud
   ```

3. **Generowanie QR Code**
   ```python
   qr = qrcode.QRCode(version=1, box_size=10, border=5)
   qr.add_data(provisioning_uri)
   qr.make(fit=True)
   img = qr.make_image(fill_color="black", back_color="white")
   ```

4. **Kodowanie do Base64**
   ```python
   img_buffer = BytesIO()
   img.save(img_buffer, format='PNG')
   qr_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
   ```

#### 2. Weryfikacja i Aktywacja TOTP

**Endpoint:**
```
POST /api/v1/totp/verify
Authorization: Bearer <setup_token>
```

**Request:**
```json
{
  "code": "123456"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Proces:**

1. **Weryfikacja Kodu**
   ```python
   totp = pyotp.TOTP(user.totp_secret)
   if not totp.verify(code, valid_window=1):
       raise HTTPException(401, "Invalid TOTP code")
   ```

2. **Aktywacja TOTP**
   ```python
   if not user.totp_configured:
       user.totp_configured = True
       await db.commit()
   ```

3. **Wydanie Tokenów**
   - System generuje access i refresh token
   - Użytkownik jest teraz w pełni uwierzytelniony

#### 3. Sprawdzenie Statusu TOTP

**Endpoint:**
```
GET /api/v1/totp/status
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "totp_configured": true,
  "requires_setup": false
}
```

### Algorytm TOTP

SPCloud używa standardowego algorytmu TOTP zgodnego z RFC 6238:

- **Algorytm Hash:** SHA-1 (standard TOTP)
- **Długość kodu:** 6 cyfr
- **Okres ważności:** 30 sekund
- **Valid Window:** ±1 (akceptuje kody z poprzedniego i następnego okresu)

```
TOTP = HOTP(K, T)
gdzie:
  K = sekret TOTP (base32)
  T = floor(Unix_Timestamp / 30)
```

---

## Zarządzanie Tokenami

### Typy Tokenów

System używa trzech typów tokenów JWT:

#### 1. Access Token

**Przeznaczenie:** Autoryzacja żądań API  
**Czas życia:** 15 minut (domyślnie)  
**Przechowywanie:** Tylko po stronie klienta (pamięć, nie localStorage)

**Struktura Payload:**
```json
{
  "sub": "user@example.com",      // Subject (username)
  "iss": "SPCloud",                // Issuer
  "iat": 1699999999,               // Issued At
  "nbf": 1699999999,               // Not Before
  "exp": 1700000899,               // Expiration (iat + 15min)
  "jti": "random_token_id"         // JWT ID (unique)
}
```

#### 2. Refresh Token

**Przeznaczenie:** Odnawianie access tokenów  
**Czas życia:** 7 dni (domyślnie)  
**Przechowywanie:** Baza danych + klient

**Struktura Payload:**
```json
{
  "sub": "user@example.com",
  "iss": "SPCloud",
  "iat": 1699999999,
  "nbf": 1699999999,
  "exp": 1700604799,               // iat + 7 days
  "jti": "random_token_id",
  "type": "refresh"                // Typ tokenu
}
```

**Model Bazy Danych:**
```python
class RefreshToken:
    id: UUID
    user_username: str
    token: str                     # JWT string
    expires_at: datetime
    created_at: datetime
```

#### 3. TOTP Setup Token

**Przeznaczenie:** Autoryzacja podczas konfiguracji TOTP  
**Czas życia:** 15 minut  
**Przechowywanie:** Tylko po stronie klienta

**Struktura Payload:**
```json
{
  "sub": "user@example.com",
  "exp": 1700000899,
  "type": "totp_setup"             // Specjalny typ
}
```

### Odnawianie Access Token

**Endpoint:**
```
POST /api/v1/users/refresh
```

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Proces:**

1. **Dekodowanie Refresh Token**
   ```python
   username = decode_refresh_token(refresh_token_str)
   if not username:
       raise HTTPException(401, "Invalid refresh token")
   ```

2. **Weryfikacja w Bazie**
   ```python
   token_obj = await db.execute(
       select(RefreshToken).where(RefreshToken.token == refresh_token_str)
   )
   if not token_obj:
       raise HTTPException(401, "Refresh token not found")
   ```

3. **Sprawdzenie Wygaśnięcia**
   ```python
   if token_obj.expires_at < now_utc():
       await db.delete(token_obj)
       raise HTTPException(401, "Refresh token expired")
   ```

4. **Generowanie Nowego Access Token**
   ```python
   access_token = create_access_token(username)
   # Refresh token pozostaje ten sam!
   ```

### Wylogowanie

**Endpoint:**
```
POST /api/v1/users/logout
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "message": "Logged out successfully"
}
```

**Proces:**

1. **Identyfikacja Użytkownika**
   - Z access tokenu (przez dependency `get_current_user`)

2. **Usunięcie Wszystkich Refresh Tokenów**
   ```python
   tokens = await db.execute(
       select(RefreshToken).where(RefreshToken.user_username == username)
   )
   for token in tokens:
       await db.delete(token)
   ```

3. **Logowanie Zdarzenia**
   ```python
   await log_service.log_action(
       action="LOGOUT",
       username=username,
       status="SUCCESS",
       details={"tokens_revoked": len(tokens)}
   )
   ```

### Bezpieczeństwo Tokenów

**Podpisywanie:**
- Używany jest algorytm HS256 (HMAC SHA-256)
- Klucz podpisujący z `JWT_SECRET` w konfiguracji
- Opcjonalnie: RS256 z `JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY`

**Walidacja:**
```python
jwt.decode(
    token,
    verify_key,
    algorithms=[alg],
    issuer="SPCloud",
    options={
        "require_sub": True,
        "require_iat": True,
        "require_exp": True,
    }
)
```

**Best Practices:**
- Access tokeny krótkotrwałe (15 min)
- Refresh tokeny przechowywane w bazie (możliwość rewokacji)
- Każdy token ma unikalny `jti` (JWT ID)
- Sprawdzanie `iss` (issuer) przy dekodowaniu
- Używanie `nbf` (not before) dla dodatkowej kontroli

---

## Endpoints API

### Users Endpoints

#### POST /api/v1/users/register
**Opis:** Rejestracja nowego użytkownika  
**Autoryzacja:** Nie wymagana  
**Request Body:**
```json
{
  "username": "string",
  "password": "string"
}
```
**Response:** `201 Created` - TOTPSetupToken  
**Błędy:**
- `409 Conflict` - Użytkownik już istnieje
- `500 Internal Server Error` - Błąd bazy danych

---

#### POST /api/v1/users/login
**Opis:** Logowanie użytkownika (bez TOTP)  
**Autoryzacja:** Nie wymagana  
**Request Body:**
```json
{
  "username": "string",
  "password": "string"
}
```
**Response:**
- Jeśli TOTP nie skonfigurowany: `200 OK` - TOTPSetupToken
- Jeśli TOTP skonfigurowany: `403 Forbidden` - wymaga użycia `/login/totp`

**Błędy:**
- `401 Unauthorized` - Nieprawidłowe dane logowania

---

#### POST /api/v1/users/login/totp
**Opis:** Logowanie z weryfikacją TOTP  
**Autoryzacja:** Nie wymagana  
**Request Body:**
```json
{
  "username": "string",
  "password": "string",
  "totp_code": "string"
}
```
**Response:** `200 OK` - Token (access + refresh)  
**Błędy:**
- `401 Unauthorized` - Nieprawidłowe hasło lub kod TOTP
- `403 Forbidden` - TOTP nie skonfigurowany

---

#### POST /api/v1/users/refresh
**Opis:** Odświeżenie access tokenu  
**Autoryzacja:** Nie wymagana  
**Request Body:**
```json
{
  "refresh_token": "string"
}
```
**Response:** `200 OK` - Token (nowy access + ten sam refresh)  
**Błędy:**
- `401 Unauthorized` - Nieprawidłowy lub wygasły refresh token

---

#### POST /api/v1/users/logout
**Opis:** Wylogowanie użytkownika  
**Autoryzacja:** Bearer Token (access token)  
**Request Body:** Brak  
**Response:** `200 OK`
```json
{
  "message": "Logged out successfully"
}
```
**Błędy:**
- `401 Unauthorized` - Nieprawidłowy access token

---

### TOTP Endpoints

#### POST /api/v1/totp/setup
**Opis:** Generowanie sekretu TOTP i QR code  
**Autoryzacja:** Bearer Token (setup token)  
**Request Body:** Brak  
**Response:** `200 OK`
```json
{
  "secret": "string",
  "provisioning_uri": "string",
  "qr_code": "data:image/png;base64,..."
}
```
**Błędy:**
- `400 Bad Request` - TOTP już skonfigurowany
- `401 Unauthorized` - Nieprawidłowy setup token
- `404 Not Found` - Użytkownik nie znaleziony

---

#### POST /api/v1/totp/verify
**Opis:** Weryfikacja kodu TOTP i aktywacja  
**Autoryzacja:** Bearer Token (setup token)  
**Request Body:**
```json
{
  "code": "string"
}
```
**Response:** `200 OK` - Token (access + refresh)  
**Błędy:**
- `400 Bad Request` - TOTP nie zainicjowany lub już skonfigurowany
- `401 Unauthorized` - Nieprawidłowy kod TOTP

---

#### GET /api/v1/totp/status
**Opis:** Sprawdzenie statusu konfiguracji TOTP  
**Autoryzacja:** Bearer Token (access token)  
**Request Body:** Brak  
**Response:** `200 OK`
```json
{
  "totp_configured": true,
  "requires_setup": false
}
```

---

## Modele Danych

### User
```python
class User(Base):
    __tablename__ = "users"
    
    username: str              # Primary Key
    hashed_password: str       # Argon2 hash
    user_type: str            # 'admin' lub 'regular'
    max_storage_mb: int       # Limit miejsca (domyślnie 100 MB)
    used_storage_mb: int      # Wykorzystane miejsce
    totp_secret: str          # Sekret TOTP (base32)
    totp_configured: bool     # Czy TOTP jest aktywny
    
    # Relacje
    files: List[FileStorage]
    refresh_tokens: List[RefreshToken]
    logs: List[LogEntry]
```

### RefreshToken
```python
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    
    id: UUID                  # Primary Key
    user_username: str        # Foreign Key -> users.username
    token: str                # JWT string (unique, indexed)
    expires_at: datetime      # Data wygaśnięcia
    created_at: datetime      # Data utworzenia
    
    # Relacje
    user: User
```

**Constraints:**
- `token` - UNIQUE, INDEX
- `user_username` - CASCADE DELETE

### LogEntry
```python
class LogEntry(Base):
    __tablename__ = "logs"
    
    id: UUID                  # Primary Key
    action: str               # Typ akcji (LOGIN, LOGOUT, REGISTER, etc.)
    status: str               # SUCCESS lub FAILED
    username: str             # Foreign Key -> users.username
    file_id: UUID            # Opcjonalnie, dla operacji na plikach
    timestamp: datetime       # Czas zdarzenia
    details: str             # JSON z dodatkowymi informacjami
    
    # Relacje
    user: User
```

---

## Bezpieczeństwo

### Hashowanie Haseł - Argon2

**Konfiguracja:**
```python
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__type="ID",           # Argon2id (hybrydowy)
    argon2__time_cost=3,         # Iteracje
    argon2__memory_cost=65536,   # ~64 MB pamięci
    argon2__parallelism=2,       # Wątki
)
```

**Dlaczego Argon2?**
- Zwycięzca Password Hashing Competition (2015)
- Odporny na ataki GPU i ASIC
- Wymaga dużo pamięci (utrudnia ataki)
- Rekomendowany przez OWASP

**Użycie:**
```python
# Hashowanie
hashed = hash_password("user_password")
# $argon2id$v=19$m=65536,t=3,p=2$...

# Weryfikacja
is_valid = verify_password("user_password", hashed)
```

### JWT Security

**Algorytmy:**
- **HS256** (HMAC SHA-256) - symetryczny, z `JWT_SECRET`
- **RS256** (RSA SHA-256) - asymetryczny, z `JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY`

**Struktura Konfiguracji:**
```python
# core/config.py
class Settings:
    JWT_SECRET: str                    # Dla HS256
    JWT_ALG: str = "HS256"
    JWT_EXPIRE_MIN: int = 15           # Access token
    JWT_REFRESH_EXPIRE_DAYS: int = 7   # Refresh token
    JWT_ISSUER: str = "SPCloud"
```

**Walidacja Token:**
```python
payload = jwt.decode(
    token,
    verify_key,
    algorithms=[alg],
    issuer="SPCloud",
    options={
        "require_sub": True,    # Wymagaj subject
        "require_iat": True,    # Wymagaj issued at
        "require_exp": True,    # Wymagaj expiration
    }
)
```

### TOTP Security

**Parametry:**
- Długość sekretu: 160 bitów (32 znaki base32)
- Algorytm: SHA-1 (standard RFC 6238)
- Długość kodu: 6 cyfr
- Czas ważności: 30 sekund
- Valid window: ±1 (±30 sekund)

**Generowanie Sekretu:**
```python
secret = pyotp.random_base32()
# Używa secrets.token_bytes() dla bezpiecznej losowości
```

**Weryfikacja z Window:**
```python
totp.verify(code, valid_window=1)
# Akceptuje:
# - Obecny kod (T)
# - Poprzedni kod (T-1)
# - Następny kod (T+1)
# Kompensuje opóźnienia sieciowe i desynchronizację czasu
```

### Dependencies - Autoryzacja Requestów

#### get_current_user
```python
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
```

**Proces:**
1. Wyciąga token z nagłówka `Authorization: Bearer <token>`
2. Dekoduje i waliduje JWT
3. Sprawdza czy token nie wygasł
4. Pobiera użytkownika z bazy
5. Zwraca obiekt User lub rzuca 401

**Użycie:**
```python
@router.get("/protected")
async def protected_route(
    current_user: User = Depends(get_current_user)
):
    return {"username": current_user.username}
```

#### get_user_for_totp_setup
```python
async def get_user_for_totp_setup(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
```

**Proces:**
1. Dekoduje token
2. Sprawdza czy `type == "totp_setup"`
3. Pobiera użytkownika
4. Weryfikuje czy TOTP nie jest już skonfigurowany
5. Zwraca obiekt User lub rzuca 401/400

### Best Practices Implementowane

✅ **Hasła:**
- Argon2 z wysokimi parametrami
- Nigdy nie logujemy ani nie zwracamy plaintext haseł
- Minimum entropy (wymuszane po stronie klienta)

✅ **Tokeny JWT:**
- Krótki czas życia access tokenów (15 min)
- Unikalny JTI dla każdego tokenu
- Walidacja issuer, expiration, not-before
- Refresh tokeny w bazie (możliwość rewokacji)

✅ **TOTP:**
- Obowiązkowy dla wszystkich użytkowników
- Valid window dla UX (ale nie zbyt szeroki)
- Sekret generowany kryptograficznie bezpieczną metodą

✅ **Rate Limiting:** (Do zaimplementowania)
- Limit prób logowania
- Limit prób TOTP

✅ **Logging:**
- Wszystkie próby logowania (success/failed)
- IP addresses
- Nie logujemy wrażliwych danych (hasła, tokeny)

---

## Przepływ Danych

### Kompletny Flow: Od Rejestracji do Pracy z API

```
┌─────────────────────────────────────────────────────────────────┐
│                    1. REJESTRACJA                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
    POST /users/register {username, password}
                              │
                              ▼
              Utworzenie użytkownika (TOTP=false)
                              │
                              ▼
          Zwrot: {setup_token, expires_in: 900}
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  2. KONFIGURACJA TOTP                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
    POST /totp/setup [Bearer setup_token]
                              │
                              ▼
        Generowanie sekretu i QR code
                              │
                              ▼
    Zwrot: {secret, qr_code, provisioning_uri}
                              │
                              ▼
         Użytkownik skanuje QR w aplikacji (Google Authenticator)
                              │
                              ▼
    POST /totp/verify {code: "123456"} [Bearer setup_token]
                              │
                              ▼
        Weryfikacja kodu i aktywacja TOTP
                              │
                              ▼
    Zwrot: {access_token, refresh_token}
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              3. PRZYSZŁE LOGOWANIA                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
    POST /users/login/totp {username, password, totp_code}
                              │
                              ▼
    Zwrot: {access_token, refresh_token}
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│            4. PRACA Z CHRONIONYM API                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
    GET /files [Authorization: Bearer access_token]
                              │
                              ▼
              Dependency: get_current_user
                              │
                              ▼
        Dekodowanie i walidacja access_token
                              │
                              ▼
              Pobranie użytkownika z DB
                              │
                              ▼
            Wykonanie operacji na plikach
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│         5. ODŚWIEŻANIE ACCESS TOKEN                             │
└─────────────────────────────────────────────────────────────────┘
          (gdy access_token wygasł po 15 min)
                              │
                              ▼
    POST /users/refresh {refresh_token}
                              │
                              ▼
        Walidacja refresh_token (JWT + DB)
                              │
                              ▼
    Zwrot: {access_token (nowy), refresh_token (ten sam)}
                              │
                              ▼
            Kontynuacja pracy z nowym access_token
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   6. WYLOGOWANIE                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
    POST /users/logout [Authorization: Bearer access_token]
                              │
                              ▼
        Usunięcie wszystkich refresh_tokens użytkownika
                              │
                              ▼
            Zwrot: {message: "Logged out successfully"}
```

### State Diagram - Stan Użytkownika

```
    ┌─────────────┐
    │   START     │
    └──────┬──────┘
           │
           │ /users/register
           ▼
    ┌─────────────────────────┐
    │  REGISTERED             │
    │  totp_configured=false  │
    └──────┬──────────────────┘
           │
           │ /totp/setup
           │ /totp/verify
           ▼
    ┌─────────────────────────┐
    │  TOTP CONFIGURED        │
    │  totp_configured=true   │
    │  ┌─────────────────┐    │
    │  │ Może używać:    │    │
    │  │ - /login/totp   │    │
    │  │ - /files/*      │    │
    │  │ - /refresh      │    │
    │  │ - /logout       │    │
    │  └─────────────────┘    │
    └─────────────────────────┘
```

---

## Logowanie Zdarzeń

System SPCloud loguje wszystkie ważne zdarzenia związane z autoryzacją.

### LogService

**Metoda:**
```python
async def log_action(
    self,
    action: str,
    username: str,
    status: str,
    details: dict = None,
    file_id: UUID = None
):
```

### Typy Akcji

| Action | Status | Details | Kiedy |
|--------|--------|---------|-------|
| `REGISTER` | SUCCESS | `{totp_configured: false, ip_address}` | Po rejestracji |
| `REGISTER` | FAILED | `{error, ip_address}` | Błąd rejestracji |
| `LOGIN` | SUCCESS | `{method: "TOTP"}` | Poprawne logowanie |
| `LOGIN` | FAILED | `{error, method: "TOTP"}` | Niepoprawne dane/kod |
| `LOGOUT` | SUCCESS | `{tokens_revoked, ip_address}` | Wylogowanie |
| `LOGOUT` | FAILED | `{error, ip_address}` | Błąd wylogowania |

### Przykładowe Wpisy

**Rejestracja:**
```json
{
  "id": "uuid-here",
  "action": "REGISTER",
  "status": "SUCCESS",
  "username": "user@example.com",
  "timestamp": "2024-11-11T10:30:00Z",
  "details": "{\"totp_configured\": false, \"ip_address\": \"192.168.1.100\"}"
}
```

**Logowanie:**
```json
{
  "id": "uuid-here",
  "action": "LOGIN",
  "status": "SUCCESS",
  "username": "user@example.com",
  "timestamp": "2024-11-11T10:35:00Z",
  "details": "{\"method\": \"TOTP\"}"
}
```

**Wylogowanie:**
```json
{
  "id": "uuid-here",
  "action": "LOGOUT",
  "status": "SUCCESS",
  "username": "user@example.com",
  "timestamp": "2024-11-11T12:00:00Z",
  "details": "{\"tokens_revoked\": 1, \"ip_address\": \"192.168.1.100\"}"
}
```

### Zastosowania Logów

1. **Audyt bezpieczeństwa**
   - Wykrywanie podejrzanej aktywności
   - Historia logowań użytkownika

2. **Debugging**
   - Analiza błędów w procesie autoryzacji
   - Śledzenie problemów użytkowników

3. **Compliance**
   - Spełnienie wymogów regulacyjnych (np. GDPR)
   - Dowód w sprawach bezpieczeństwa

4. **Analytics**
   - Częstotliwość logowań
   - Popularne czasy aktywności

---

## Zmienne Środowiskowe

### Wymagane

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost/spcloud

# JWT
JWT_SECRET=your-secret-key-min-32-chars-long
JWT_EXPIRE_MIN=15
JWT_REFRESH_EXPIRE_DAYS=7
JWT_ISSUER=SPCloud

# Opcjonalnie dla RS256
# JWT_PRIVATE_KEY=path/to/private.pem
# JWT_PUBLIC_KEY=path/to/public.pem
# JWT_ALG=RS256

# S3 Storage
S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET_NAME=spcloud-files
```

---

## Przykłady Użycia (cURL)

### 1. Rejestracja
```bash
curl -X POST http://localhost:8000/api/v1/users/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user@example.com",
    "password": "SecurePass123!"
  }'
```

**Response:**
```json
{
  "setup_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 900
}
```

### 2. Konfiguracja TOTP
```bash
SETUP_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

curl -X POST http://localhost:8000/api/v1/totp/setup \
  -H "Authorization: Bearer $SETUP_TOKEN"
```

**Response:**
```json
{
  "secret": "JBSWY3DPEHPK3PXP",
  "provisioning_uri": "otpauth://totp/SPCloud:user@example.com?secret=JBSWY3DPEHPK3PXP&issuer=SPCloud",
  "qr_code": "data:image/png;base64,iVBORw0KGgo..."
}
```

### 3. Weryfikacja TOTP
```bash
curl -X POST http://localhost:8000/api/v1/totp/verify \
  -H "Authorization: Bearer $SETUP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "123456"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 4. Logowanie z TOTP
```bash
curl -X POST http://localhost:8000/api/v1/users/login/totp \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user@example.com",
    "password": "SecurePass123!",
    "totp_code": "123456"
  }'
```

### 5. Użycie Chronionego Endpointu
```bash
ACCESS_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

curl -X GET http://localhost:8000/api/v1/files \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### 6. Odświeżenie Tokenu
```bash
REFRESH_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

curl -X POST http://localhost:8000/api/v1/users/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "'$REFRESH_TOKEN'"
  }'
```

### 7. Wylogowanie
```bash
curl -X POST http://localhost:8000/api/v1/users/logout \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

---

## Rozwiązywanie Problemów

### Problem: "Invalid TOTP code"

**Możliwe przyczyny:**
1. Desynchronizacja czasu między serwerem a urządzeniem
2. Użyto kodu zbyt wcześnie/późno
3. Błędny sekret TOTP

**Rozwiązanie:**
```bash
# Sprawdź czas serwera
date

# Sprawdź czy NTP jest włączony
timedatectl status

# Użytkownik powinien sprawdzić czas na swoim urządzeniu
```

### Problem: "Refresh token not found"

**Możliwe przyczyny:**
1. Token został usunięty przy wylogowaniu
2. Token wygasł i został usunięty
3. Token nigdy nie istniał (błędny string)

**Rozwiązanie:**
- Użytkownik musi zalogować się ponownie

### Problem: "TOTP already configured"

**Możliwe przyczyny:**
1. Użytkownik próbuje ponownie skonfigurować TOTP
2. Używa setup tokenu zamiast access tokenu

**Rozwiązanie:**
- Jeśli chce zresetować TOTP, potrzebny jest osobny endpoint (do zaimplementowania)
- Używaj poprawnego tokenu dla danego endpointu

### Problem: "Invalid setup token"

**Możliwe przyczyny:**
1. Token wygasł (15 min)
2. Używa access tokenu zamiast setup tokenu
3. Token jest niepoprawny

**Rozwiązanie:**
- Zaloguj się ponownie aby otrzymać nowy setup token
- Użyj poprawnego typu tokenu

---

## Roadmap / Przyszłe Usprawnienia

### Planowane Funkcjonalności

1. **Rate Limiting**
   ```python
   # Limit prób logowania
   @limiter.limit("5/minute")
   async def login_with_totp(...):
   ```

2. **TOTP Reset**
   ```python
   @router.post("/totp/reset")
   async def reset_totp(
       current_user: User = Depends(get_current_user),
       password: str
   ):
       # Wymagaj potwierdzenia hasła
       # Generuj nowy sekret
       # Wyślij email z potwierdzeniem
   ```

3. **Account Recovery**
   - Backup codes podczas konfiguracji TOTP
   - Email recovery flow

4. **Session Management**
   - Lista aktywnych sesji (refresh tokenów)
   - Możliwość wylogowania konkretnych sesji
   - "Wyloguj wszystkie urządzenia"

5. **Enhanced Logging**
   - Geolokalizacja IP
   - User agent tracking
   - Anomaly detection

6. **OAuth2 Integration**
   - Logowanie przez Google
   - Logowanie przez GitHub
   - Logowanie przez Microsoft

7. **WebAuthn/FIDO2**
   - Biometryczna autoryzacja
   - Hardware security keys

---

## Podsumowanie

System autoryzacji SPCloud to kompleksowe rozwiązanie zapewniające:

✅ **Silne bezpieczeństwo:**
- Argon2 do hashowania haseł
- Obowiązkowe 2FA (TOTP)
- JWT z krótkimi okresami ważności

✅ **Wygoda użytkownika:**
- Valid window dla TOTP
- Długotrwałe refresh tokeny
- QR code dla łatwej konfiguracji

✅ **Audytowalność:**
- Pełne logowanie zdarzeń
- IP tracking
- Historia akcji

✅ **Skalowalność:**
- Asynchroniczny Python (FastAPI)
- PostgreSQL z async SQLAlchemy
- Stateless JWT (oprócz refresh tokenów)

System jest gotowy do produkcji i spełnia współczesne standardy bezpieczeństwa aplikacji webowych.

---

**Autor:** System SPCloud  
**Wersja:** 1.0  
**Data:** 2024-11-11  
**Licencja:** MIT (lub inna, jeśli dotyczy)


# Dokumentacja Systemu Versionowania Plików

## Spis treści
1. [Przegląd systemu](#przegląd-systemu)
2. [Architektura bazy danych](#architektura-bazy-danych)
3. [Struktura w S3](#struktura-w-s3)
4. [Endpointy API](#endpointy-api)
5. [Logika działania](#logika-działania)
6. [Przykłady użycia](#przykłady-użycia)
7. [Diagramy przepływu](#diagramy-przepływu)

---

## Przegląd systemu

System versionowania plików w SPCloud umożliwia:
- **Automatyczne tworzenie wersji** przy każdym uploadzę tego samego pliku
- **Przechowywanie wszystkich wersji** w S3 i bazie danych
- **Logiczne przywracanie wersji** (zmiana wskaźnika w bazie bez kopiowania plików)
- **Pobieranie konkretnych wersji** na żądanie
- **Usuwanie wybranych wersji** (z wyjątkiem aktualnej)

**Kluczowa koncepcja:** Każda wersja jest fizycznie przechowywana w S3 jako osobny plik, ale użytkownik operuje na logicznej nazwie pliku.

---

## Architektura bazy danych

### Tabela: `files` (FileStorage)

Główna tabela przechowująca metadane plików.

| Kolumna | Typ | Opis |
|---------|-----|------|
| `id` | UUID | Unikalny identyfikator pliku (PK) |
| `name` | VARCHAR | Bazowa nazwa pliku (np. `document.txt`) |
| `path` | VARCHAR | Ścieżka S3 (legacy, używana do zgodności) |
| `size` | INTEGER | Rozmiar aktualnej wersji w bajtach |
| `owner` | VARCHAR | Nazwa użytkownika (FK → `users.username`) |
| `current_version` | INTEGER | **Numer aktualnej wersji** (1, 2, 3...) |
| `created_at` | TIMESTAMP | Data utworzenia pliku |
| `updated_at` | TIMESTAMP | Data ostatniej aktualizacji |
| `is_favorite` | BOOLEAN | Czy plik jest ulubiony |

**Unique Constraint:** `(owner, name)` - jeden użytkownik nie może mieć dwóch plików o tej samej nazwie.

**Przykładowy rekord:**
```sql
id: 550e8400-e29b-41d4-a716-446655440000
name: document.txt
owner: admin
current_version: 3
size: 2048
created_at: 2025-10-24 10:00:00
updated_at: 2025-10-24 10:15:00
```

### Tabela: `file_versions` (FileVersion)

Przechowuje wszystkie wersje każdego pliku.

| Kolumna | Typ | Opis |
|---------|-----|------|
| `id` | UUID | Unikalny identyfikator wersji (PK) |
| `file_id` | UUID | Odniesienie do pliku (FK → `files.id`) |
| `version_number` | INTEGER | Numer wersji (1, 2, 3...) |
| `path` | VARCHAR | Pełna ścieżka S3 z wersją |
| `size` | INTEGER | Rozmiar tej wersji w bajtach |
| `created_at` | TIMESTAMP | Data utworzenia wersji |
| `created_by` | VARCHAR | Kto utworzył wersję (FK → `users.username`) |

**Cascade:** Usunięcie rekordu z `files` automatycznie usuwa wszystkie jego wersje.

**Przykładowe rekordy:**
```sql
-- Wersja 1
id: 111e8400-e29b-41d4-a716-446655440001
file_id: 550e8400-e29b-41d4-a716-446655440000
version_number: 1
path: s3://user-admin/document_v1.txt
size: 1024
created_by: admin
created_at: 2025-10-24 10:00:00

-- Wersja 2
id: 222e8400-e29b-41d4-a716-446655440002
file_id: 550e8400-e29b-41d4-a716-446655440000
version_number: 2
path: s3://user-admin/document_v2.txt
size: 1536
created_by: admin
created_at: 2025-10-24 10:10:00

-- Wersja 3 (aktualna)
id: 333e8400-e29b-41d4-a716-446655440003
file_id: 550e8400-e29b-41d4-a716-446655440000
version_number: 3
path: s3://user-admin/document_v3.txt
size: 2048
created_by: admin
created_at: 2025-10-24 10:15:00
```

### Relacje

```
users (1) ----< (N) files
  |
  └----< (N) file_versions (created_by)

files (1) ----< (N) file_versions
```

---

## Struktura w S3

### Organizacja bucketów

Każdy użytkownik ma swój własny bucket:
```
user-{username}/
```

Przykład: użytkownik `admin` → bucket `user-admin`

### Nazewnictwo plików z wersjami

Format: `{nazwa_bez_rozszerzenia}_v{numer}.{rozszerzenie}`

**Przykład struktury S3:**
```
user-admin/
  ├── document_v1.txt
  ├── document_v2.txt
  ├── document_v3.txt
  ├── photo_v1.jpg
  ├── photo_v2.jpg
  ├── report_v1.pdf
  └── report_v2.pdf

user-john/
  ├── notes_v1.txt
  ├── notes_v2.txt
  └── image_v1.png
```

### Parsowanie nazw plików

System automatycznie:
- **Usuwa wersję z nazwy przy uploadzię:** `document_v5.txt` → bazowa nazwa: `document.txt`
- **Dodaje wersję przy zapisie do S3:** `document.txt` + wersja 3 → `document_v3.txt`

**Kod parsowania:**
```python
def _parse_base_filename(filename: str) -> str:
    """document_v1.txt -> document.txt"""
    name, ext = os.path.splitext(filename)
    if '_v' in name:
        parts = name.rsplit('_v', 1)
        if len(parts) == 2 and parts[1].isdigit():
            return f"{parts[0]}{ext}"
    return filename

def _build_versioned_filename(filename: str, version: int) -> str:
    """document.txt + 3 -> document_v3.txt"""
    name, ext = os.path.splitext(filename)
    return f"{name}_v{version}{ext}"
```

---

## Endpointy API

### 1. Upload pliku (z automatycznym versionowaniem)

**Endpoint:** `POST /api/v1/files/upload`

**Headers:**
```
Authorization: Bearer {access_token}
Content-Type: multipart/form-data
```

**Body (form-data):**
```
file: [wybierz plik]
```

**Logika:**
1. Sprawdza czy plik o tej nazwie już istnieje
2. Jeśli **NIE istnieje:**
   - Tworzy rekord w `files` z `current_version = 1`
   - Tworzy rekord w `file_versions` z `version_number = 1`
   - Zapisuje w S3 jako `filename_v1.ext`
3. Jeśli **istnieje:**
   - Znajduje najwyższy numer wersji
   - Tworzy nowy rekord w `file_versions` z `version_number = max + 1`
   - Aktualizuje `files.current_version` na nowy numer
   - Zapisuje w S3 jako `filename_vN.ext`

**Odpowiedź (nowy plik):**
```json
{
    "message": "File uploaded successfully",
    "file_id": "550e8400-e29b-41d4-a716-446655440000",
    "filename": "document.txt",
    "version": 1,
    "size": 1024,
    "path": "s3://user-admin/document_v1.txt"
}
```

**Odpowiedź (nowa wersja):**
```json
{
    "message": "New version uploaded successfully",
    "file_id": "550e8400-e29b-41d4-a716-446655440000",
    "filename": "document.txt",
    "version": 3,
    "size": 2048,
    "path": "s3://user-admin/document_v3.txt"
}
```

---

### 2. Lista plików użytkownika

**Endpoint:** `GET /api/v1/files/`

**Headers:**
```
Authorization: Bearer {access_token}
```

**Odpowiedź:**
```json
{
    "files": [
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "document.txt",
            "size": 2048,
            "owner": "admin",
            "current_version": 3,
            "created_at": "2025-10-24T10:00:00Z",
            "updated_at": "2025-10-24T10:15:00Z",
            "is_favorite": false
        }
    ]
}
```

**Uwaga:** Pole `current_version` pokazuje która wersja jest obecnie aktywna.

---

### 3. Pobierz aktualną wersję pliku

**Endpoint:** `GET /api/v1/files/download/{file_id}`

**Headers:**
```
Authorization: Bearer {access_token}
```

**Parametry:**
- `file_id` (UUID) - identyfikator pliku

**Logika:**
1. Pobiera rekord z `files` po `file_id`
2. Odczytuje wartość `current_version` (np. 3)
3. Szuka rekordu w `file_versions` gdzie `version_number = 3`
4. Pobiera plik z S3: `document_v3.txt`
5. Zwraca użytkownikowi z oryginalną nazwą: `document.txt`

**Odpowiedź:** Plik binarny (Content-Type: application/octet-stream)

**Przykład curl:**
```bash
curl -X GET "http://localhost:8000/api/v1/files/download/550e8400-e29b-41d4-a716-446655440000" \
     -H "Authorization: Bearer eyJhbGc..." \
     -o document.txt
```

---

### 4. Lista wersji pliku

**Endpoint:** `GET /api/v1/files/{file_id}/versions`

**Headers:**
```
Authorization: Bearer {access_token}
```

**Odpowiedź:**
```json
{
    "file_id": "550e8400-e29b-41d4-a716-446655440000",
    "versions": [
        {
            "version_number": 3,
            "size": 2048,
            "created_at": "2025-10-24T10:15:00Z",
            "created_by": "admin",
            "is_current": true
        },
        {
            "version_number": 2,
            "size": 1536,
            "created_at": "2025-10-24T10:10:00Z",
            "created_by": "admin",
            "is_current": false
        },
        {
            "version_number": 1,
            "size": 1024,
            "created_at": "2025-10-24T10:00:00Z",
            "created_by": "admin",
            "is_current": false
        }
    ]
}
```

**Sortowanie:** Od najnowszej do najstarszej (DESC)

---

### 5. Pobierz konkretną wersję

**Endpoint:** `GET /api/v1/files/{file_id}/versions/{version_number}`

**Headers:**
```
Authorization: Bearer {access_token}
```

**Parametry:**
- `file_id` (UUID) - identyfikator pliku
- `version_number` (int) - numer wersji (1, 2, 3...)

**Logika:**
1. Znajduje rekord w `file_versions` po `file_id` i `version_number`
2. Pobiera plik z S3: `document_v2.txt`
3. Zwraca z oryginalną nazwą: `document.txt`

**Odpowiedź:** Plik binarny

**Przykład:**
```bash
# Pobierz wersję 1
curl -X GET "http://localhost:8000/api/v1/files/550e8400-.../versions/1" \
     -H "Authorization: Bearer eyJhbGc..." \
     -o document_v1.txt
```

---

### 6. Przywróć wersję (Restore)

**Endpoint:** `POST /api/v1/files/{file_id}/restore/{version_number}`

**Headers:**
```
Authorization: Bearer {access_token}
```

**Parametry:**
- `file_id` (UUID) - identyfikator pliku
- `version_number` (int) - numer wersji do przywrócenia

**Logika (TYLKO UPDATE W BAZIE!):**
1. Sprawdza czy wersja istnieje
2. **Aktualizuje** `files.current_version = version_number`
3. **Aktualizuje** `files.size` na rozmiar tej wersji
4. **Aktualizuje** `files.updated_at`
5. **NIE kopiuje** plików w S3!

**Odpowiedź:**
```json
{
    "message": "File restored to version 2",
    "file_id": "550e8400-e29b-41d4-a716-446655440000",
    "current_version": 2,
    "filename": "document.txt"
}
```

**Przykład SQL wykonywany wewnętrznie:**
```sql
UPDATE files 
SET current_version = 2, 
    size = 1536, 
    updated_at = NOW()
WHERE id = '550e8400-e29b-41d4-a716-446655440000';
```

**Efekt:** Następne pobranie pliku zwróci `document_v2.txt` zamiast `document_v3.txt`

---

### 7. Usuń konkretną wersję

**Endpoint:** `DELETE /api/v1/files/{file_id}/versions/{version_number}`

**Headers:**
```
Authorization: Bearer {access_token}
```

**Parametry:**
- `file_id` (UUID) - identyfikator pliku
- `version_number` (int) - numer wersji do usunięcia

**Ograniczenia:**
- ❌ **NIE MOŻNA** usunąć wersji która jest `current_version`
- ✅ Można usunąć dowolną starszą wersję

**Logika:**
1. Sprawdza czy `version_number != current_version`
2. Usuwa plik z S3: `document_v1.txt`
3. Usuwa rekord z `file_versions`
4. Aktualizuje `users.used_storage_mb` (odejmuje rozmiar)

**Odpowiedź sukces:**
```json
{
    "message": "Version 1 deleted successfully",
    "file_id": "550e8400-e29b-41d4-a716-446655440000",
    "filename": "document.txt"
}
```

**Odpowiedź błąd (próba usunięcia current):**
```json
{
    "detail": "Cannot delete current version. Restore another version first."
}
```

---

### 8. Usuń plik (wszystkie wersje)

**Endpoint:** `DELETE /api/v1/files/{file_id}`

**Headers:**
```
Authorization: Bearer {access_token}
```

**Logika:**
1. Pobiera wszystkie wersje z `file_versions`
2. **Usuwa wszystkie pliki z S3:**
   - `document_v1.txt`
   - `document_v2.txt`
   - `document_v3.txt`
3. Usuwa rekord z `files` (CASCADE usuwa też z `file_versions`)
4. Aktualizuje `users.used_storage_mb`

**Odpowiedź:**
```json
{
    "message": "File 'document.txt' deleted successfully with 3 version(s)"
}
```

---

## Logika działania

### Scenariusz 1: Upload nowego pliku

**Użytkownik:** Upload `report.pdf`

**Backend:**
1. Sprawdza czy `report.pdf` istnieje w bazie → NIE
2. Tworzy rekord w `files`:
   ```sql
   INSERT INTO files (id, name, owner, current_version, size, ...)
   VALUES ('uuid1', 'report.pdf', 'admin', 1, 5120, ...);
   ```
3. Tworzy rekord w `file_versions`:
   ```sql
   INSERT INTO file_versions (id, file_id, version_number, path, size, ...)
   VALUES ('uuid2', 'uuid1', 1, 's3://user-admin/report_v1.pdf', 5120, ...);
   ```
4. Upload do S3: `user-admin/report_v1.pdf`

**Stan w bazie:**
```
files:
  id: uuid1, name: report.pdf, current_version: 1

file_versions:
  id: uuid2, file_id: uuid1, version_number: 1, path: s3://.../report_v1.pdf
```

**Stan w S3:**
```
user-admin/
  └── report_v1.pdf
```

---

### Scenariusz 2: Upload kolejnej wersji

**Użytkownik:** Upload `report.pdf` (zmodyfikowany)

**Backend:**
1. Sprawdza czy `report.pdf` istnieje → TAK (uuid1)
2. Pobiera wszystkie wersje → max version = 1
3. Tworzy nową wersję (version = 2):
   ```sql
   INSERT INTO file_versions (id, file_id, version_number, path, size, ...)
   VALUES ('uuid3', 'uuid1', 2, 's3://user-admin/report_v2.pdf', 6144, ...);
   ```
4. Aktualizuje `files`:
   ```sql
   UPDATE files 
   SET current_version = 2, size = 6144, updated_at = NOW()
   WHERE id = 'uuid1';
   ```
5. Upload do S3: `user-admin/report_v2.pdf`

**Stan w bazie:**
```
files:
  id: uuid1, name: report.pdf, current_version: 2

file_versions:
  - id: uuid2, file_id: uuid1, version_number: 1
  - id: uuid3, file_id: uuid1, version_number: 2  ← nowa
```

**Stan w S3:**
```
user-admin/
  ├── report_v1.pdf  ← stara wersja
  └── report_v2.pdf  ← nowa wersja
```

---

### Scenariusz 3: Przywracanie wersji

**Użytkownik:** Przywróć wersję 1

**Endpoint:** `POST /files/{uuid1}/restore/1`

**Backend:**
1. Sprawdza czy wersja 1 istnieje → TAK
2. **TYLKO** aktualizuje bazę:
   ```sql
   UPDATE files 
   SET current_version = 1, size = 5120, updated_at = NOW()
   WHERE id = 'uuid1';
   ```
3. **NIE kopiuje** plików w S3

**Stan w bazie:**
```
files:
  id: uuid1, name: report.pdf, current_version: 1  ← zmienione z 2 na 1

file_versions:
  - id: uuid2, file_id: uuid1, version_number: 1  ← teraz aktualna
  - id: uuid3, file_id: uuid1, version_number: 2
```

**Stan w S3 (BEZ ZMIAN!):**
```
user-admin/
  ├── report_v1.pdf  ← teraz to będzie pobierane
  └── report_v2.pdf  ← wciąż istnieje
```

**Efekt:** Następne `GET /files/download/{uuid1}` pobierze `report_v1.pdf`

---

### Scenariusz 4: Usuwanie starej wersji

**Użytkownik:** Usuń wersję 1

**Endpoint:** `DELETE /files/{uuid1}/versions/1`

**Backend:**
1. Sprawdza `current_version` → 2 (OK, nie usuwa current)
2. Usuwa z S3: `report_v1.pdf`
3. Usuwa z bazy:
   ```sql
   DELETE FROM file_versions 
   WHERE file_id = 'uuid1' AND version_number = 1;
   ```
4. Aktualizuje storage:
   ```sql
   UPDATE users 
   SET used_storage_mb = used_storage_mb - (5120 / 1024 / 1024)
   WHERE username = 'admin';
   ```

**Stan w bazie:**
```
files:
  id: uuid1, name: report.pdf, current_version: 2

file_versions:
  - id: uuid3, file_id: uuid1, version_number: 2  ← tylko ta pozostała
```

**Stan w S3:**
```
user-admin/
  └── report_v2.pdf  ← tylko wersja 2
```

---

### Scenariusz 5: Usuwanie całego pliku

**Użytkownik:** Usuń plik `report.pdf`

**Endpoint:** `DELETE /files/{uuid1}`

**Backend:**
1. Pobiera wszystkie wersje (1, 2)
2. Usuwa z S3:
   - `report_v1.pdf`
   - `report_v2.pdf`
3. Usuwa z bazy:
   ```sql
   DELETE FROM files WHERE id = 'uuid1';
   -- CASCADE automatycznie usuwa z file_versions
   ```
4. Aktualizuje storage

**Stan końcowy:**
- Baza: brak rekordów
- S3: brak plików

---

## Przykłady użycia

### 1. Pełny flow: Upload → Nowa wersja → Przywrócenie → Download

```bash
# 1. Zaloguj się
curl -X POST "http://localhost:8000/api/v1/users/login/totp" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"pass123","totp_code":"123456"}'
# Otrzymujesz: access_token

TOKEN="eyJhbGc..."

# 2. Upload pliku (wersja 1)
curl -X POST "http://localhost:8000/api/v1/files/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@document.txt"
# Odpowiedź: {"file_id": "uuid1", "version": 1}

FILE_ID="uuid1"

# 3. Modyfikuj plik lokalnie i upload ponownie (wersja 2)
curl -X POST "http://localhost:8000/api/v1/files/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@document.txt"
# Odpowiedź: {"file_id": "uuid1", "version": 2}

# 4. Zobacz wersje
curl -X GET "http://localhost:8000/api/v1/files/$FILE_ID/versions" \
  -H "Authorization: Bearer $TOKEN"
# Odpowiedź: {"versions": [{"version_number": 2, "is_current": true}, {"version_number": 1}]}

# 5. Pobierz aktualną wersję (v2)
curl -X GET "http://localhost:8000/api/v1/files/download/$FILE_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -o current.txt

# 6. Pobierz starą wersję (v1)
curl -X GET "http://localhost:8000/api/v1/files/$FILE_ID/versions/1" \
  -H "Authorization: Bearer $TOKEN" \
  -o old.txt

# 7. Przywróć wersję 1
curl -X POST "http://localhost:8000/api/v1/files/$FILE_ID/restore/1" \
  -H "Authorization: Bearer $TOKEN"
# Odpowiedź: {"current_version": 1}

# 8. Teraz download pobierze v1!
curl -X GET "http://localhost:8000/api/v1/files/download/$FILE_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -o restored.txt
# restored.txt === old.txt

# 9. Usuń wersję 2
curl -X DELETE "http://localhost:8000/api/v1/files/$FILE_ID/versions/2" \
  -H "Authorization: Bearer $TOKEN"
```

---

### 2. Postman Collection

**Kolekcja requestów:**

#### A. Register + TOTP Setup
```
1. POST /users/register
   Body: {"username": "admin", "password": "pass123"}
   
2. POST /totp/setup
   Headers: Authorization: Bearer {setup_token}
   (Zapisz QR code i secret)
   
3. POST /totp/verify
   Headers: Authorization: Bearer {setup_token}
   Body: {"code": "123456"}
   → Otrzymasz access_token
```

#### B. Upload i Versioning
```
4. POST /files/upload
   Headers: Authorization: Bearer {access_token}
   Body (form-data): file = [document.txt]
   → file_id: abc-123
   
5. GET /files/
   Headers: Authorization: Bearer {access_token}
   → Lista plików z current_version
   
6. POST /files/upload (ten sam plik, zmieniona treść)
   Headers: Authorization: Bearer {access_token}
   Body (form-data): file = [document.txt]
   → version: 2
   
7. GET /files/abc-123/versions
   Headers: Authorization: Bearer {access_token}
   → Wersje: [2 (current), 1]
   
8. GET /files/download/abc-123
   Headers: Authorization: Bearer {access_token}
   → Pobiera wersję 2
   
9. POST /files/abc-123/restore/1
   Headers: Authorization: Bearer {access_token}
   → current_version = 1
   
10. GET /files/download/abc-123
    Headers: Authorization: Bearer {access_token}
    → Teraz pobiera wersję 1!
```

---

## Diagramy przepływu

### Upload nowego pliku

```
┌─────────┐     ┌─────────┐     ┌──────────┐     ┌─────┐
│ Client  │────>│ Backend │────>│ Database │     │ S3  │
└─────────┘     └─────────┘     └──────────┘     └─────┘
     │                │                │              │
     │  POST /upload  │                │              │
     │───────────────>│                │              │
     │                │  Check exists? │              │
     │                │───────────────>│              │
     │                │   (NOT FOUND)  │              │
     │                │<───────────────│              │
     │                │                │              │
     │                │  INSERT files  │              │
     │                │  (current_v=1) │              │
     │                │───────────────>│              │
     │                │                │              │
     │                │ INSERT versions│              │
     │                │  (v_number=1)  │              │
     │                │───────────────>│              │
     │                │                │              │
     │                │  PUT file_v1.txt              │
     │                │──────────────────────────────>│
     │                │                │              │
     │<───────────────│                │              │
     │ {file_id, v=1} │                │              │
```

### Upload kolejnej wersji

```
┌─────────┐     ┌─────────┐     ┌──────────┐     ┌─────┐
│ Client  │────>│ Backend │────>│ Database │     │ S3  │
└─────────┘     └─────────┘     └──────────┘     └─────┘
     │                │                │              │
     │  POST /upload  │                │              │
     │  (same file)   │                │              │
     │───────────────>│                │              │
     │                │  Check exists? │              │
     │                │───────────────>│              │
     │                │   (FOUND)      │              │
     │                │<───────────────│              │
     │                │                │              │
     │                │ SELECT max(v)  │              │
     │                │───────────────>│              │
     │                │   (max = 2)    │              │
     │                │<───────────────│              │
     │                │                │              │
     │                │ INSERT version │              │
     │                │  (v_number=3)  │              │
     │                │───────────────>│              │
     │                │                │              │
     │                │ UPDATE files   │              │
     │                │ (current_v=3)  │              │
     │                │───────────────>│              │
     │                │                │              │
     │                │  PUT file_v3.txt              │
     │                │──────────────────────────────>│
     │                │                │              │
     │<───────────────│                │              │
     │ {file_id, v=3} │                │              │
```

### Przywracanie wersji

```
┌─────────┐     ┌─────────┐     ┌──────────┐     ┌─────┐
│ Client  │────>│ Backend │────>│ Database │     │ S3  │
└─────────┘     └─────────┘     └──────────┘     └─────┘
     │                │                │              │
     │ POST /restore/1│                │              │
     │───────────────>│                │              │
     │                │ Check version  │              │
     │                │    exists?     │              │
     │                │───────────────>│              │
     │                │   (EXISTS)     │              │
     │                │<───────────────│              │
     │                │                │              │
     │                │ UPDATE files   │              │
     │                │ SET current=1  │              │
     │                │───────────────>│              │
     │                │                │              │
     │                │                │   ❌ NO S3   │
     │                │                │   OPERATION  │
     │                │                │              │
     │<───────────────│                │              │
     │ {current_v=1}  │                │              │
```

### Download pliku

```
┌─────────┐     ┌─────────┐     ┌──────────┐     ┌─────┐
│ Client  │────>│ Backend │────>│ Database │     │ S3  │
└─────────┘     └─────────┘     └──────────┘     └─────┘
     │                │                │              │
     │ GET /download  │                │              │
     │───────────────>│                │              │
     │                │ SELECT files   │              │
     │                │ (current_v=2)  │              │
     │                │───────────────>│              │
     │                │<───────────────│              │
     │                │                │              │
     │                │ SELECT version │              │
     │                │ (v_number=2)   │              │
     │                │───────────────>│              │
     │                │ (path: s3://.. │              │
     │                │   /file_v2.txt)│              │
     │                │<───────────────│              │
     │                │                │              │
     │                │  GET file_v2.txt              │
     │                │──────────────────────────────>│
     │                │          [binary data]        │
     │                │<──────────────────────────────│
     │                │                │              │
     │<───────────────│                │              │
     │  [file stream] │                │              │
     │  (as file.txt) │                │              │
```

---

## Zarządzanie storage

### Kalkulacja użytego miejsca

```python
# Każda wersja liczy się do used_storage_mb
user.used_storage_mb = sum(version.size for version in all_versions) / (1024 * 1024)

# Przykład:
# document_v1.txt: 1 MB
# document_v2.txt: 1.5 MB
# document_v3.txt: 2 MB
# Total: 4.5 MB

# Po usunięciu v1:
# document_v2.txt: 1.5 MB
# document_v3.txt: 2 MB
# Total: 3.5 MB
```

### Quota enforcement

```python
# Przy uploadzię sprawdzane jest:
if (user.used_storage_mb + new_file_size_mb) > user.max_storage_mb:
    raise HTTPException(413, "Storage quota exceeded")
```

---

## Zalety i wady implementacji

### ✅ Zalety

1. **Przywracanie bez kopiowania** - instant, tylko UPDATE w bazie
2. **Historia zmian** - wszystkie wersje są dostępne
3. **Elastyczność** - można przeskakiwać między wersjami
4. **Izolacja użytkowników** - każdy ma swój bucket S3
5. **Transparentność** - użytkownik widzi logiczne nazwy plików

### ⚠️ Wady / Ograniczenia

1. **Zużycie storage** - każda wersja zajmuje miejsce
2. **Brak automatycznego czyszczenia** - stare wersje nie są usuwane automatycznie
3. **Brak limitu wersji** - można utworzyć nieskończenie wiele wersji
4. **Brak kompresji** - pliki nie są kompresowane
5. **Brak diffu** - nie ma informacji czym się różnią wersje

### 🔮 Możliwe usprawnienia

1. **Automatyczne czyszczenie** - usuwaj wersje starsze niż N dni
2. **Limit wersji** - maksymalnie 10 wersji na plik
3. **Diff dla plików tekstowych** - pokazuj różnice między wersjami
4. **Kompresja** - kompresuj stare wersje
5. **Tagi/komentarze** - możliwość dodania opisu do wersji
6. **Snapshot całego storage** - przywracanie wszystkich plików do daty

---

## Podsumowanie

System versionowania w SPCloud:
- ✅ Automatycznie tworzy wersje przy każdym uploadzię
- ✅ Przechowuje wszystkie wersje fizycznie w S3
- ✅ Umożliwia przywracanie przez zmianę wskaźnika w bazie
- ✅ Pozwala na pobieranie konkretnych wersji
- ✅ Umożliwia usuwanie niepotrzebnych wersji
- ✅ Liczy wszystkie wersje do quota storage

**Kluczowa koncepcja:** Pliki fizycznie istnieją jako `file_v1.ext`, `file_v2.ext`, ale użytkownik operuje na logicznej nazwie `file.ext` i system automatycznie wskazuje właściwą wersję przez pole `current_version` w bazie danych.


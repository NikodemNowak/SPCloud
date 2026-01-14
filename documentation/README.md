# Dokumentacja projektu SPCloud

Folder zawiera kompletną dokumentację projektu podzieloną na dwie główne sekcje:

## Struktura katalogów

### `/technical`
Dokumentacja techniczna dla programistów, zawierająca:
- `TECHNICAL_DOCUMENTATION.md` - Główna dokumentacja techniczna
- `AUTHENTICATION_DOCS.md` - Szczegóły implementacji autoryzacji (JWT, TOTP)
- `FILE_VERSIONING_DOCS.md` - Opis systemu wersjonowania plików
- `DOCKER_README.md` - Instrukcje dotyczące konteneryzacji
- Diagramy procesów (Logowanie, Rejestracja)

### `/report`
Sprawozdanie z projektu w formacie LaTeX:
- Źródła LaTeX (`.tex`)
- Skompilowany plik PDF (`documentation.pdf`)
- Pliki pomocnicze kompilacji

### `/assets`
Zasoby graficzne używane w dokumentacji (logo, schematy).

## Kompilacja sprawozdania (LaTeX)

### Wymagania
Do kompilacji dokumentacji wymagany jest zainstalowany system LaTeX:
- **TeX Live** (Linux)
- **MiKTeX** (Windows)
- **MacTeX** (macOS)

### Instrukcja kompilacji
Przejdź do katalogu `report/` i uruchom:

```bash
cd report
pdflatex documentation.tex
pdflatex documentation.tex # Uruchom dwukrotnie dla wygenerowania spisu treści
```

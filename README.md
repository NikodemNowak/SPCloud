## 1. Utworzenie i aktywacja wirtualnego środowiska

### Linux / RPi / macOS:
```bash
python3 -m venv venv
source venv/bin/activate
```

### Windows:
```bash
python -m venv venv
venv\Scripts\activate
```

---

## 2. Instalacja zależności

```bash
pip install -r requirements.txt
```

---

## 3. Ustawienie interpretera w PyCharm

1. Otwórz **Settings / Preferences → Project → Python Interpreter**
2. Kliknij **⚙️ → Add → Existing environment**
3. Wskaż Pythona z `venv`:
    - Linux/macOS: `/ścieżka/do/projektu/venv/bin/python`
    - Windows: `C:\ścieżka\do\projektu\venv\Scripts\python.exe`
4. Zastosuj i zatwierdź

---

## 4. Uruchomienie aplikacji

Przykładowy serwer FastAPI:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Aplikacja będzie dostępna na:
```
http://<IP_RPi>:8000
```

---

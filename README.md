# MilionerzyOCR

Desktopowy system wizyjny i analityczny do wsadowej detekcji plansz, ekstrakcji tekstu (OCR), pełnego zarządzania bazą (CRUD) oraz wieloformatowego eksportu pytań z teleturnieju *Milionerzy* (edycje TVN oraz Polsat).

---

## Prezentacja interfejsu

### 1. Przetwarzanie odcinków i podgląd klatek na żywo
Kolejka wideo z podglądem postępu, logami detekcji w czasie rzeczywistym oraz klatkami: bazową (pytanie) i wynikową (rozstrzygnięcie).

![Panel analizy wideo](assets/MilionerzyAnaliza.png)

---

### 2. Baza pytań, filtrowanie i operacje masowe
Zestawienie rozpoznanych pozycji z podziałem na edycje TVN / Polsat, statusem weryfikacji, selekcją checkboxami oraz paginacją.

![Widok bazy pytań](assets/MilionerzyBaza.png)

---

### 3. Weryfikacja i edycja rekordu
Okno edycji z bezpośrednim podglądem zapisanej klatki wideo, umożliwiające szybką korektę tekstu OCR, zmianę stacji oraz oznaczenie poprawnej litery.

![Okno edycji pytania](assets/MilionerzyEdycjaPytania.png)

---

## Architektura systemu i pipeline przetwarzania

Program działa w architekturze wielowątkowej, oddzielając warstwę wizualną interfejsu użytkownika od ciężkich obliczeń numerycznych, dekodowania wideo i inferencji modeli uczenia maszynowego.

```text
               +----------------------------------------------------+
               |                PySide6 Main Window                 |
               | (Kolejka zadań, kontrolki, widok bazy, modal CRUD) |
               +-------------------------+--------------------------+
                                         |  Sygnały i sloty (Qt)
                                         v
       +---------------------------------+----------------------------------+
       |                  VideoWorker Thread (QThread)                     |
       |                                                                    |
       |   +-----------------------+           +------------------------+   |
       |   |   OpenCV VideoCapture |           |  Presety geometrii ROI |   |
       |   |  (Dekodowanie klatek) |           |  (presets.py: TVN/POL) |   |
       |   +-----------+-----------+           +-----------+------------+   |
       |               |                                   |                |
       |               v                                   v                |
       |   +-----------------------------------------------+------------+   |
       |   |               VisionEngine (Maszyna Stanów)                |   |
       |   |  - Stan 1: SEARCH_QUESTION (detekcja krawędzi i konturów)  |   |
       |   |  - Stan 2: SEARCH_RESOLVE (analiza barw HSV zieleni)       |   |
       |   +-------------------------------+----------------------------+   |
       |                                   |                                |
       |                                   v                                |
       |   +-------------------------------+----------------------------+   |
       |   |                      Silnik EasyOCR                        |   |
       |   |  - Model detekcji CRAFT -> Model rozpoznawania CRNN        |   |
       |   |  - Post-processing: czyszczenie artefaktów i parsowanie    |   |
       |   +-------------------------------+----------------------------+   |
       +-----------------------------------+--------------------------------+
                                           |
                                           v
       +-----------------------------------+--------------------------------+
       |                  Warstwa danych i eksportu                         |
       |  - db_manager.py: Walidacja, deduplikacja, auto-reindeksacja ID    |
       |  - captures/: Magazyn klatek wideo powiązanych z wpisami           |
       |  - export_service.py: Konwersja do XLSX, CSV, DOCX/PDF, Anki       |
       +--------------------------------------------------------------------+
```

---

## Szczegółowa specyfikacja funkcjonalności

### 1. Silnik Computer Vision i maszyna stanów (`core/`)
* **Maszyna stanów detektora:** Przetwarzanie materiału wideo opiera się na deterministycznej maszynie stanów (`SEARCH_QUESTION` $\to$ `SEARCH_RESOLVE`), eliminującej analizowanie zbędnych klatek w momentach, gdy na ekranie pokazywane są ujęcia studyjne lub zbliżenia na uczestnika.
* **Presety geometrii stacji (`presets.py`):** Dedykowane maski ROI dla plansz TVN oraz Polsatu. System uwzględnia odmienne proporcje, grubości ramek oraz warianty kompaktowe (np. profil `POLSAT_SLIM` rejestrowany w dzienniku zdarzeń).
* **Segmentacja w przestrzeni HSV:** Wykrywanie rozstrzygnięcia pytania polega na ciągłej analizie progowej nasycenia i odcienia barwy zielonej wewnątrz prostokątów ograniczających wariantów odpowiedzi. Rozwiązanie to jest odporne na wahania oświetlenia w studiu telewizyjnym.
* **Tryb awaryjny (`DO WERYFIKACJI`):** W przypadku rezygnacji zawodnika, wyczerpania czasu odcinka lub nagłego cięcia montażowego system nie zgaduje odpowiedzi — rekord otrzymuje żółtą flagę ostrzegawczą i zostaje przekazany do manualnej weryfikacji.
* **Niezależne podglądy klatek:** Interfejs wyświetla dwa niezależne bufory obrazu: klatkę referencyjną z treścią pytania oraz klatkę z rozstrzygnięciem graficznym.

### 2. Ekstrakcja tekstu i normalizacja językowa (OCR)
* **Modele głębokie:** Zastosowanie sieci detekcyjnej CRAFT (*Character Region Awareness for Text Detection*) oraz sieci rekurencyjno-splotowej CRNN (*ResNet + BiLSTM + CTC*) zoptymalizowanej pod kątem polskich znaków diakrytycznych (`ą`, `ć`, `ę`, `ł`, `ń`, `ó`, `ś`, `ź`, `ż`).
* **Post-processing tekstu:** Automatyczne usuwanie szumów optycznych, normalizacja białych znaków, korekta typowych błędów odczytu cyfr jako liter oraz stripowanie etykiet wariantów (`A:`, `B:`, `C:`, `D:`) w celu zachowania czystego tekstu w bazie.
* **Separacja strefowa:** Tekst pytania oraz poszczególne warianty są przetwarzane w izolowanych wycinkach ROI, co zapobiega sklejaniu sąsiadujących linii tekstu.

### 3. Asynchroniczne przetwarzanie i kolejkowanie zadań
* **Separacja procesów przez `QThread`:** Ciężkie operacje dekodowania OpenCV oraz inferencja sieci neuronowych są w całości oddelegowane do wątku pobocznego. Pętla zdarzeń głównego okna Qt zachowuje płynność (brak efektu zawieszenia interfejsu).
* **Przetwarzanie wsadowe (Batch Queue):** Możliwość załadowania całej serii odcinków (`.mp4`, `.mkv`, `.avi`). Każdy plik posiada niezależny znacznik stanu (`OCZEKUJE`, `W TRAKCIE...`, `UKOŃCZONO`, `PRZERWANO`).
* **Bezpieczne zatrzymywanie:** Przycisk `PRZERWIJ ANALIZĘ` przesyła flagę przerwania do pętli workera, bezpiecznie zamyka strumień wideo i zachowuje dotychczasowy postęp w pliku bazy bez ryzyka uszkodzenia pliku JSON.
* **Dziennik zdarzeń (Live Diagnostics):** Szczegółowy rejestr z sygnaturami czasowymi odcinka (`MM:SS`), raportujący wykryte formaty stacji, zdarzenia detekcji oraz finalne rozstrzygnięcia.

### 4. Warstwa danych i pełny model CRUD (`database/`)
* **Deduplikacja wpisów:** Przed zapisaniem rekordu moduł `db_manager.py` weryfikuje unikalność treści pytania i zestawu odpowiedzi, zapobiegając duplikowaniu danych przy ponownym przetwarzaniu tego samego materiału.
* **Auto-reindeksacja kluczy głównych:** Usunięcie dowolnego wpisu uruchamia procedurę `reindex_database`, która naprawia ciągłość identyfikatorów (`#001`, `#002`, ...), chroniąc bazę przed powstawaniem pustych luk.
* **Modalny edytor rekordu:** Wbudowane okno edycji wyświetla zrzut klatki wprost z nagrania, umożliwiając skorygowanie literówek OCR, zmianę wariantu poprawnego (A, B, C, D, BRAK) lub modyfikację przypisania stacji (TVN / Polsat).
* **Kaskadowe czyszczenie dysku:** Usunięcie pytania z bazy (zarówno pojedyncze, jak i masowe) automatycznie kasuje powiązany plik `.jpg` z katalogu `captures/`.

### 5. Wyszukiwanie, filtrowanie i nawigacja
* **Wyszukiwarka pełnotekstowa:** Błyskawiczny filtr live-search przeszukujący jednocześnie treść pytań i wszystkie warianty odpowiedzi.
* **Wielokryterialne filtry:**
  * Stacja: Wszystkie, TVN, Polsat.
  * Status: Wszystkie rekordy, Poprawna: A, Poprawna: B, Poprawna: C, Poprawna: D, Do weryfikacji.
  * Ulubione: Szybkie filtrowanie pytań oznaczonych gwiazdką (`★ Ulubione`).
* **Sortowanie:** Układanie chronologiczne (Najnowsze / Najstarsze) oraz alfabetyczne (A-Z).
* **Bezpieczna paginacja:** Podział bazy na strony po 25 rekordów z jawnym niszczeniem niewidocznych widżetów Qt, co zapobiega wyciekom pamięci podręcznej i błędom segmentacji (`0xC0000005`) przy bazach liczących tysiące pozycji.
* **Zarządzanie masowe:** Opcje `Zaznacz wszystkie`, `Odznacz` oraz `Usuń zaznaczone`.

### 6. Silnik wieloformatowego eksportu (`exporters/`)
* **Fiszki Anki (`.txt` / `.tsv`):** Profil zoptymalizowany pod kątem nauki pamięciowej — treść pytania na awersie karty, warianty odpowiedzi z wyraźnym oznaczeniem poprawnego wyboru na rewersie.
* **Arkusz kalkulacyjny Excel (`.xlsx`):** Strukturyzowany skoroszyt z nagłówkami kolumn, wyśrodkowanymi identyfikatorami i przygotowanymi szerokościami komórek.
* **Format CSV (`.csv`):** Standardowy plik tekstowy w kodowaniu UTF-8 z separatorem przecinkowym, gotowy do importu w bazach SQL lub narzędziach BI.
* **Dokument Word / PDF (`.docx` / `.pdf`):** Gotowe szablony testów wiedzy generowane na podstawie bazy (wersje z kluczem odpowiedzi na końcu lub w formie arkusza egzaminacyjnego).

---

## Struktura katalogów projektu

```text
MilionerzyOCR/
├── assets/                    # Zrzuty ekranu interfejsu na potrzeby dokumentacji
│   ├── MilionerzyAnaliza.png
│   ├── MilionerzyBaza.png
│   └── MilionerzyEdycjaPytania.png
├── core/                      # Silnik analityczny i wizyjny
│   ├── config.py              # Konfiguracja progów HSV, parametrów OCR i ścieżek
│   ├── presets.py             # Presety współrzędnych ROI dla stacji (TVN, Polsat)
│   ├── video_worker.py        # Asynchroniczny worker QThread analizujący strumień wideo
│   └── vision_engine.py       # Segmentacja klatek, detekcja plansz i ekstrakcja ROI
├── database/                  # Warstwa zarządzania danymi
│   ├── db_manager.py          # Logika CRUD, deduplikacja, wyszukiwanie i reindeksacja ID
│   └── models.py              # Struktura danych rekordu pytania
├── exporters/                 # Moduły konwersji i eksportu bazy
│   └── export_service.py      # Generowanie formatów XLSX, CSV, DOCX/PDF oraz fiszek Anki
├── templates/                 # Szablony dokumentów eksportowych
├── tools/                     # Narzędzia pomocnicze (kalibratory ROI, testy barw)
├── ui/                        # Warstwa prezentacji PySide6
│   ├── dialogs/               # Okna modalne (edytor rekordu, potwierdzenia)
│   ├── views/                 # Główne widoki (panel analizy, przeglądarka bazy)
│   ├── widgets/               # Komponenty wielokrotnego użytku (karty pytań, paginator)
│   ├── main_window.py         # Główne okno aplikacji i zarządzanie sygnałami
│   └── styles.qss             # Autorski arkusz stylów CSS/QSS (Dark Theme)
├── .gitignore                 # Reguły wykluczeń gita
├── main.py                    # Punkt startowy aplikacji
├── README.md                  # Dokumentacja techniczna projektu
└── requirements.txt           # Zależności biblioteczne projektu
```

---

## Stos technologiczny

| Komponent | Narzędzie | Rola w projekcie |
| :--- | :--- | :--- |
| **Środowisko** | Python 3.11 | Środowisko uruchomieniowe (zalecana wersja pod biblioteki deep learning) |
| **Interfejs GUI** | PySide6 (Qt 6.6+) | Wielowątkowy interfejs, autorski system stylów QSS |
| **Wizja komputerowa** | OpenCV (`opencv-python`) | Dekodowanie wideo, ekstrakcja ROI, filtracja kolorów w HSV |
| **Silnik OCR** | EasyOCR | Sieć CRAFT (detekcja tekstu) + CRNN (rozpoznawanie znaków) |
| **Backend AI** | PyTorch & Torchvision | Środowisko inferencyjne modeli detekcji i odczytu |
| **Baza danych** | Silnik JSON + system plików | Przechowywanie danych strukturalnych i klatek referencyjnych |
| **Eksport danych** | Pandas, OpenPyXL, python-docx | Generowanie arkuszy XLSX, plików CSV, dokumentów testowych |
| **Dystrybucja** | PyInstaller | Kompilacja do autonomicznej paczki wykonywalnej Windows (.exe) |

---

## Uruchomienie lokalne

Do uruchomienia projektu wymagany jest **Python 3.11.x**. Nowsze wersje (3.12+) mogą powodować błędy kompilacji zależności C++ powiązanych z PyTorchem na systemie Windows.

### 1. Sklonowanie repozytorium
```bash
git clone https://github.com/TomaszMarek/MilionerzyOCR.git
cd MilionerzyOCR
```

### 2. Utworzenie i aktywacja wirtualnego środowiska
```bash
python -m venv .venv

# Windows (PowerShell):
.venv\Scripts\Activate.ps1

# Windows (CMD):
.venv\Scripts\activate.bat

# Linux / macOS:
source .venv/bin/activate
```

### 3. Instalacja zależności
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Uruchomienie programu
```bash
python main.py
```

---

## Budowanie wersji wykonywalnej (.exe)

Aplikację można skompilować do postaci autonomicznego katalogu dystrybucyjnego Windows (`--onedir`), który nie wymaga obecności Pythona na maszynie docelowej. 

Ze względu na dynamiczne ładowanie bibliotek C++ przez `torchvision` oraz specyficzne pliki stylów Qt, polecenie kompilacji uwzględnia metadane i dodatkowe zasoby:

```bash
pyinstaller --noconfirm --onedir --windowed \
    --name "MilionerzyOCR" \
    --add-data "ui/styles.qss;ui" \
    --collect-all easyocr \
    --collect-all torchvision \
    --copy-metadata torchvision \
    --copy-metadata torch \
    main.py
```

Wynikowy program zostanie utworzony w ścieżce `dist/MilionerzyOCR/`. Gotowy katalog można spakować do archiwum `.zip` i uruchamiać bezpośrednio za pomocą pliku `MilionerzyOCR.exe`.

---

## Format bazy danych (`milionerzy_baza.json`)

Struktura rekordu w pliku magazynu danych:

```json
[
  {
    "id": "001",
    "pytanie": "Do czworonogów czyli tetrapodów, nie zaliczamy:",
    "warianty": {
      "A": "gadów",
      "B": "płazów",
      "C": "ptaków",
      "D": "owadów"
    },
    "poprawna_odpowiedz": "D",
    "station": "TVN",
    "is_favorite": false,
    "screenshot_path": "captures/question_001.jpg"
  }
]
```

---

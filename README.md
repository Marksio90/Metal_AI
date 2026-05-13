# Metal_AI

AI assistant dla **metal manufacturing** i procesu **RFQ (Request for Quotation)**.
Projekt pomaga zespołom handlowym, technologicznym i operacyjnym szybciej przechodzić od zapytania klienta do wyceny, standaryzując analizę danych wejściowych oraz wspierając decyzje produkcyjne.

---

## Spis treści

- [Czym jest Metal_AI](#czym-jest-metal_ai)
- [Quickstart](#quickstart)
- [URL-e lokalnych usług](#url-e-lokalnych-usług)
- [Architektura projektu](#architektura-projektu)
- [Konfiguracja środowiska (.env)](#konfiguracja-środowiska-env)
- [Zmiana modelu AI](#zmiana-modelu-ai)
- [Troubleshooting](#troubleshooting)
- [Security notes](#security-notes)

---

## Czym jest Metal_AI

Metal_AI to asystent AI zaprojektowany pod potrzeby firm produkcyjnych (szczególnie obróbka metalu), który:

- wspiera analizę zapytań RFQ,
- pomaga w interpretacji wymagań klienta,
- umożliwia szybsze przygotowanie odpowiedzi ofertowej,
- centralizuje logikę domenową związaną z kalkulacją i analizą danych produkcyjnych.

Docelowo projekt ma skracać czas reakcji na zapytania, zwiększać spójność procesu wyceny i ograniczać błędy wynikające z ręcznej analizy.

---

## Quickstart

```bash
git clone https://github.com/Marksio90/Metal_AI
cd Metal_AI
cp .env.example .env
docker compose up --build
```

Po uruchomieniu kontenerów aplikacja będzie dostępna lokalnie pod adresami opisanymi poniżej.

---

## URL-e lokalnych usług

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- Health endpoint: `http://localhost:8000/health`

---

## Architektura projektu

Projekt jest podzielony na trzy główne obszary:

- `apps/backend`  
  Warstwa backendowa API (obsługa requestów, integracja z modelem AI, endpointy aplikacyjne i health-check).

- `apps/frontend`  
  Interfejs użytkownika do pracy z asystentem (formularze, widoki wyników, komunikacja z backendem).

- `src/metal_calc`  
  Logika domenowa związana z kalkulacjami i regułami biznesowymi dla procesów metal manufacturing / RFQ.

Taki podział pozwala niezależnie rozwijać UI, API i core domenowy oraz ułatwia testowanie i utrzymanie.

---

## Konfiguracja środowiska (.env)

1. Skopiuj plik przykładowy:
   ```bash
   cp .env.example .env
   ```
2. Uzupełnij wymagane zmienne środowiskowe (zwłaszcza klucz API i konfigurację modelu).

Typowe grupy zmiennych:

- **Dostęp do modelu AI** (np. klucz API, nazwa modelu),
- **Konfiguracja backendu** (host, port, CORS),
- **Konfiguracja frontendu** (URL backendu),
- **Flagi środowiskowe** (`dev` / `prod`).

> Szczegóły i dokładne nazwy zmiennych znajdziesz w `.env.example`.

---

## Zmiana modelu AI

Aby zmienić model:

1. Otwórz plik `.env`.
2. Znajdź zmienną odpowiedzialną za nazwę modelu (zgodnie z `.env.example`).
3. Ustaw docelową wartość modelu.
4. Zrestartuj usługi:
   ```bash
   docker compose down
   docker compose up --build
   ```

Jeśli ustawisz model nieobsługiwany przez dostawcę lub przez implementację backendu, backend może zwracać błąd walidacji lub błąd wywołania API.

---

## Troubleshooting

### 1) Brak / nieprawidłowy API key

**Objawy:** błędy autoryzacji (401/403), brak odpowiedzi modelu.  
**Co sprawdzić:**

- czy `.env` istnieje i zawiera poprawny klucz,
- czy klucz nie wygasł,
- czy usługa została zrestartowana po zmianie `.env`.

### 2) Problemy z CORS

**Objawy:** frontend nie może wywołać backendu z przeglądarki.  
**Co sprawdzić:**

- czy backend ma poprawnie ustawioną listę dozwolonych originów,
- czy frontend używa poprawnego URL API (`http://localhost:8000`).

### 3) Konflikty portów

**Objawy:** `port is already allocated` podczas startu Dockera.  
**Co sprawdzić:**

- czy port 3000 i 8000 nie są zajęte przez inne procesy,
- ewentualnie zmień mapowanie portów w `docker-compose` i zaktualizuj URL-e.

### 4) Invalid model

**Objawy:** błędy typu `invalid model`, `model not found`, `unsupported model`.  
**Co sprawdzić:**

- czy nazwa modelu w `.env` jest poprawna,
- czy dany model jest dostępny dla Twojego konta,
- czy backend obsługuje ten model.

---

## Security notes

- **Nigdy nie commituj kluczy API ani żadnych sekretów do repozytorium.**
- Przechowuj sekrety wyłącznie lokalnie w pliku `.env`.
- Upewnij się, że `.env` jest ignorowany przez Git (`.gitignore`).
- Jeśli klucz wyciekł, natychmiast go zrotuj (unieważnij i wygeneruj nowy).

---

## Status

Projekt rozwijany iteracyjnie. Wraz z rozwojem funkcji RFQ i kalkulacji domenowej dokumentacja będzie rozszerzana o szczegółowe flow, przykłady payloadów API oraz scenariusze integracyjne.

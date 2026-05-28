# IPIP-NEO-120 — Test osobowości

Aplikacja webowa do samodiagnozy osobowości na bazie inwentarza IPIP-NEO-120 (Johnson, 2014).  
Wyniki w percentylach → sformatowany raport gotowy do analizy przez LLM.

## Pliki projektu

```
├── app.py                  # Główna aplikacja Streamlit
├── scoring_engine.py       # Silnik obliczeniowy (surowe punkty)
├── normalization_engine.py # Normalizacja (percentyle)
├── output_formatter.py     # Formatowanie raportu dla LLM
├── questions.json          # 120 pytań z kluczem punktacyjnym
├── norms.json              # Normy statystyczne (Johnson 2014, Table 2)
└── requirements.txt
```

## Uruchomienie lokalne

```bash
git clone https://github.com/TWOJ_LOGIN/NAZWA_REPO.git
cd NAZWA_REPO
pip install -r requirements.txt
streamlit run app.py
```

Aplikacja otworzy się pod adresem `http://localhost:8501`.

## Wdrożenie na Streamlit Community Cloud (darmowe, publiczny URL)

1. Utwórz konto na [share.streamlit.io](https://share.streamlit.io)
2. Połącz z GitHubem i wskaż repozytorium
3. Ustaw `app.py` jako plik główny
4. Kliknij **Deploy** — aplikacja dostępna pod `https://TWOJ_LOGIN-NAZWA_REPO-app-XXXXX.streamlit.app`

## Podstawa naukowa

- **Test:** IPIP-NEO-120, publiczna pula pozycji [ipip.ori.org](https://ipip.ori.org)
- **Normy:** Johnson, J.A. (2014). *Measuring thirty facets of the Five Factor Model with a 120-item public domain inventory.* Journal of Research in Personality, 51, 78–89. Table 2. Próba internetowa N=619,150.
- **Uwaga:** Tłumaczenie pytań jest robocze. Brak oficjalnej polskiej normalizacji dla tej wersji.

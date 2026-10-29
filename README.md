# huskebasi.github.io — Maree

Pagina statica con gli orari di **alta e bassa marea** per le località configurate.

La pagina **non contiene la chiave RapidAPI**. I dati vengono generati da un workflow GitHub Actions e salvati in `tides.json`.

## File

| File | Uso |
|---|---|
| `index.html` | Pagina: orologio, mappa Leaflet/OSM, prossimi eventi, selettore località |
| `spots.json` | Località da aggiornare (nome + lat/lon) |
| `tides.json` | Dati generati dal workflow (non modificare a mano) |
| `tools/fetch_tides.py` | Script che chiama RapidAPI e scrive `tides.json` |
| `.github/workflows/tides.yml` | Workflow ogni 3 giorni + run manuale |

## Aggiungere o cambiare una località

Modifica `spots.json`:

```json
[
  { "name": "Fiumicino", "lat": 41.7713, "lon": 12.2298 },
  { "name": "Anzio", "lat": 41.4479, "lon": 12.6288 }
]
```

Poi esegui il workflow manualmente (Actions → Update tides → Run workflow) oppure committa: al prossimo run `tides.json` verrà aggiornato.

La pagina seleziona automaticamente lo spot più vicino alla posizione del browser, se disponibile; altrimenti usa il primo della lista. Puoi anche scegliere lo spot dal menu.

## Configurazione del workflow

Nel repo GitHub:

1. **Settings → Secrets and variables → Actions → New repository secret**
2. Nome: `RAPIDAPI_KEY`
3. Valore: la chiave RapidAPI (quella nuova, non quella vecchia pubblica)

Il workflow:

- gira ogni 3 giorni alle 03:00 UTC;
- può essere lanciato a mano con `workflow_dispatch`;
- chiama `tools/fetch_tides.py` per ogni spot;
- aggiorna `tides.json` e fa commit se ci sono differenze;
- se una chiamata fallisce, mantiene i dati precedenti per quello spot (marcato `stale: true`);
- se tutte falliscono e non esiste un `tides.json` precedente, non sovrascrive nulla.

## Test locale

```bash
# con la chiave in una variabile d'ambiente
RAPIDAPI_KEY=... python3 tools/fetch_tides.py spots.json tides.json

# server statico locale
python3 -m http.server 8080
# apri http://localhost:8080/
```

## Nota sulla chiave

La vecchia chiave era in chiaro in `index.html` ed è rimasta nella storia git del repository pubblico: va considerata compromessa. Dopo aver verificato che la pagina funziona con `tides.json`, **ruota la chiave** nel dashboard RapidAPI e aggiorna il secret `RAPIDAPI_KEY`. La pagina non si rompe perché non usa più la chiave.

## Attribuzione

Dati maree: `©2019 API Hood. Generated using AVISO+ Products.` (via RapidAPI `tides.p.rapidapi.com`).

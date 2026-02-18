# esslingen.de-calendar-fetcher

Dieses Projekt lädt strukturierte Kalenderdaten von `esslingen.de` nach `./structured-data`.

## Dateien

- `main.py`: empfohlener Einstieg über vordefinierte Profile.
- `app/fetch_structured_data.py`: Downloader-Implementierung (JSON, ICS, erzeugtes JSON-LD, History-Snapshots).
- `requirements.txt`: keine externen Python-Abhängigkeiten erforderlich.

## Standardnutzung (empfohlen)

`main.py` steuert den Download über Profile und ruft intern `app/fetch_structured_data.py` auf.

```bash
python3 main.py --profile every_date
python3 main.py --profile frauentage
```

Optional anderes Ausgabeverzeichnis:

```bash
python3 main.py --profile frauentage --out-dir structured-data
```

## Profile in `main.py`

- `DOWNLOAD_EVERY_DATE`
  - entspricht: `--series-id=-1 --anz=-1`
- `DOWNLOAD_FRAUENTAGE`
  - entspricht: `--series-id=330100 --anz=-1`

## Advanced: Direkter Scriptaufruf

```bash
python3 app/fetch_structured_data.py --series-id=-1 --anz=-1
python3 app/fetch_structured_data.py --series-id=330100 --anz=-1
```

## Output und Versionierung

Bei jedem Lauf werden die aktuellen Dateien im Zielordner überschrieben:

- `loadData_20307012.json`
- `ical_20307012.ics`
- `jsonld_20307012_generated.json`

Zusätzlich wird bei jedem Lauf ein Snapshot in `structured-data/history/` erstellt.
Dateinamen enthalten einen Zeitstempel im Format `YYYY-MM-DD_HH-MM-SS`, z. B.:

- `loadData_20307012__2026-02-18_16-30-10.json`

## Kalender API

### Endpoints

- JSON-Feed:
  - `https://www.esslingen.de/site/Esslingen_Layout_2022/VXC/20307012/loadData/loadData.json`
- ICS-Feed:
  - `https://www.esslingen.de/site/Esslingen_Layout_2022/zmservice/20307012/ical/ical.ics`

### Relevante Query-Parameter (JSON)

| Parameter | Bedeutung |
|---|---|
| `action=pre` | lädt Eventdaten im JSON-Format |
| `q.sammelbegrif.id` | Serienfilter (`-1` = alle, `330100` = Frauenwochen) |
| `anz` | Anzahl (`-1` = alle verfügbaren Einträge) |
| `xstart` | Offset für Paging (`0` = ab Anfang) |
| `SORT=2` | Sortierung wie im Kalender-Frontend |
| `dateformat=XDATE` | Datumsformat-Option des Endpoints |
| `q.z.von`, `q.z.bis` | Zeitraumfilter |
| `q` | Freitextsuche |
| `loadgruppe` | Frontend-Parameter (`geg`, `dhhd`, `kkfjfj`) |

### Beispiel-Requests

#### cURL

Alle Termine:

```bash
curl --noproxy '*' -sS \
  'https://www.esslingen.de/site/Esslingen_Layout_2022/VXC/20307012/loadData/loadData.json?action=pre&q.sammelbegrif.id=-1&anz=-1&SORT=2&dateformat=XDATE&xstart=0&loadgruppe=geg&loadgruppe=dhhd&loadgruppe=kkfjfj'
```

Frauenwochen:

```bash
curl --noproxy '*' -sS \
  'https://www.esslingen.de/site/Esslingen_Layout_2022/VXC/20307012/loadData/loadData.json?action=pre&q.sammelbegrif.id=330100&anz=-1&SORT=2&dateformat=XDATE&xstart=0&loadgruppe=geg&loadgruppe=dhhd&loadgruppe=kkfjfj'
```

#### Python (`urllib`, ohne Zusatzpakete)

```python
from urllib.request import ProxyHandler, Request, build_opener

url = (
    "https://www.esslingen.de/site/Esslingen_Layout_2022/"
    "VXC/20307012/loadData/loadData.json"
    "?action=pre&q.sammelbegrif.id=330100&anz=-1&SORT=2"
    "&dateformat=XDATE&xstart=0&loadgruppe=geg&loadgruppe=dhhd&loadgruppe=kkfjfj"
)

req = Request(url, headers={"User-Agent": "example-client/1.0"})
opener = build_opener(ProxyHandler({}))
with opener.open(req, timeout=60) as resp:
    payload = resp.read().decode("utf-8", "replace")
print(payload[:500])
```

#### Python (`requests`, optional)

```python
import requests

url = "https://www.esslingen.de/site/Esslingen_Layout_2022/VXC/20307012/loadData/loadData.json"
params = {
    "action": "pre",
    "q.sammelbegrif.id": "330100",
    "anz": "-1",
    "SORT": "2",
    "dateformat": "XDATE",
    "xstart": "0",
}
params_list = [(k, v) for k, v in params.items()] + [
    ("loadgruppe", "geg"),
    ("loadgruppe", "dhhd"),
    ("loadgruppe", "kkfjfj"),
]

r = requests.get(url, params=params_list, timeout=60)
r.raise_for_status()
print(r.text[:500])
```

#### JavaScript (`fetch`)

```javascript
const url = new URL("https://www.esslingen.de/site/Esslingen_Layout_2022/VXC/20307012/loadData/loadData.json");
url.searchParams.set("action", "pre");
url.searchParams.set("q.sammelbegrif.id", "330100");
url.searchParams.set("anz", "-1");
url.searchParams.set("SORT", "2");
url.searchParams.set("dateformat", "XDATE");
url.searchParams.set("xstart", "0");
url.searchParams.append("loadgruppe", "geg");
url.searchParams.append("loadgruppe", "dhhd");
url.searchParams.append("loadgruppe", "kkfjfj");

const res = await fetch(url, { method: "GET" });
const text = await res.text();
console.log(text.slice(0, 500));
```

### JSON-Antwort (Kurzform)

Der JSON-Endpoint liefert ein Array von Events, typischerweise mit Feldern wie:

- `id`
- `titel`
- `von`, `bis`, `zeit`
- `location`, `location_plz`, `location_ortsname`, `location_strasse`, `location_hausnr`
- `kategorie`, `kat`, `sammel`
- `beschreibung`

## curl-Hinweis

Der Downloader prüft, ob `curl` als Systembefehl verfügbar ist.

- Wenn `curl` vorhanden ist, wird für Downloads `curl` verwendet.
- Wenn `curl` nicht vorhanden ist, nutzt das Skript automatisch einen Python-`urllib`-Fallback.

## Troubleshooting

### `Could not resolve host: www.esslingen.de`

Ursache: DNS-/Netzwerkproblem.

Checks:

```bash
curl --noproxy '*' -sS 'https://www.esslingen.de' | head
```

Wenn das fehlschlägt, später erneut versuchen oder lokale DNS/Netzwerk-Konfiguration prüfen.

### `curl` nicht vorhanden

Das Skript erkennt das automatisch und nutzt den Python-`urllib`-Fallback.
Du kannst den aktiven Backend-Hinweis im Skript-Output sehen:

- `Download backend: curl`
- `Download backend: urllib fallback (curl nicht gefunden)`

### Zu wenige/unerwartete Termine im JSON

Achte auf die Parameter:

- `anz=-1` lädt alle verfügbaren Einträge.
- `q.sammelbegrif.id=-1` lädt alle Reihen.
- `q.sammelbegrif.id=330100` lädt Frauenwochen.

Beispiel (Frauenwochen komplett):

```bash
python3 app/fetch_structured_data.py --series-id=330100 --anz=-1
```

### Aktuelle Dateien wurden überschrieben

Das ist beabsichtigt.
Die jeweils letzte Version liegt in `structured-data/`, ältere Stände in `structured-data/history/` mit Zeitstempel.

### `requests`-Beispiel aus README funktioniert nicht

`requests` ist optional und nicht in `requirements.txt` enthalten.
Installieren bei Bedarf:

```bash
python3 -m pip install requests
```

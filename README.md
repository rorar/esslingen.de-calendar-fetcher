# esslingen.de-calendar-fetcher

Dieses Projekt lädt strukturierte Kalenderdaten von `esslingen.de` nach `./structured-data`.

## Dateien

- `main.py`: empfohlener Einstieg über vordefinierte Profile.
- `app/fetch_structured_data.py`: Downloader-Implementierung (JSON, ICS, erzeugtes JSON-LD, History-Snapshots).
- `app/preprocess_data.py`: nur Pre-Processing (bereinigt Daten und erzeugt Boilerplate-JSON in `output/boilerplate/`).
- `app/postprocess_output.py`: Pre- + Post-Processing (CSV/XML Export in `output/`).
- `app/process_data_pipeline.py`: gemeinsame Pipeline-Implementierung.
- `config/processing_config.json`: Best-Practice-Konfiguration fuer Pre-/Post-Processing.
- `requirements.txt`: keine externen Python-Abhängigkeiten erforderlich.

## Standardnutzung (empfohlen)

`main.py` steuert den Download über Profile und ruft intern `app/fetch_structured_data.py` auf.

### Schritt 1 (empfohlen): Filter-Optionen aktualisieren

```bash
python3 main.py --update-filters
```

Warum zuerst?
Damit Label- und ID-Mappings aktuell sind und du das Programm korrekt konfigurieren kannst.

Label entsprechen z. B. den Kategorienamen wie bspw. `Begegnung` im Kalender-Frontend, IDs sind die korrespondierenden internen Werte für API-Parameter.

**Hinweis:** 
Bei fehlenden Cache-Dateien wird automatisch ein Update versucht. Für reproduzierbare Ergebnisse sollte `--update-filters` trotzdem zuerst ausgeführt werden.

### Schritt 2: Profil ausführen

```bash
python3 main.py --profile every_date
python3 main.py --profile frauentage
```

Optional anderes Ausgabeverzeichnis:

```bash
python3 main.py --profile frauentage --out-dir structured-data
```

## Profile in `main.py`

Hardcoded Profile:

- `DOWNLOAD_EVERY_DATE`
  - entspricht: `--series-id=-1 --anz=-1`
- `DOWNLOAD_FRAUENTAGE`
  - entspricht: `--series-id=330100 --anz=-1`

Simple-Filter:

- `DOWNLOAD_CAT_<ID|LABEL>`
  - setzt genau einen Kategorie-Filter (`q.kat.id`) und lädt mit `--series-id=-1 --anz=-1`
- `DOWNLOAD_SAMMEL_<ID|LABEL>`
  - setzt genau einen Sammelbegriff-Filter (`q.sammelbegrif.id`) und lädt mit `--anz=-1`

Advanced-Filter (Multi-Werte):

- `DOWNLOAD_CAT_ID=<ID[,ID2...]>`
- `DOWNLOAD_CAT_LABEL=<LABEL[,LABEL2...]>`
- `DOWNLOAD_SAMMEL_ID=<ID[,ID2...]>`
- `DOWNLOAD_SAMMEL_LABEL=<LABEL[,LABEL2...]>`

Unterstützte Delimiter für Multi-Werte: `,` `;` `|` `+`

Beispiele:

```bash
python3 main.py --profile DOWNLOAD_CAT_908119
```

```bash
python3 main.py --profile DOWNLOAD_CAT_BÜHNE_THEATER
```

```bash
python3 main.py --profile DOWNLOAD_SAMMEL_Frauenwochen
```

```bash
python3 main.py --profile 'DOWNLOAD_CAT_ID=908119,908120|908121'
```

```bash
python3 main.py --profile 'DOWNLOAD_CAT_LABEL=Bühne · Theater;Vorträge Diskussion'
```

```bash
python3 main.py --profile 'DOWNLOAD_SAMMEL_ID=330100|11602300'
```

```bash
python3 main.py --profile 'DOWNLOAD_SAMMEL_LABEL=Frauenwochen,Welcome Service Region Stuttgart'
```

Hinweise zur Label-Auflösung:

- Für ADVANCED-Label werden Varianten wie `Bühne · Theater` und `Bühne Theater` gleich behandelt.
- Für SIMPLE-Label werden normalisierte Schreibweisen wie `BÜHNE_THEATER` akzeptiert.

## Copy/Paste Profile

```bash
# 1) Filter-Listen aktualisieren
python3 main.py --update-filters

# 2) Alle Termine (Default-Kalender)
python3 main.py --profile DOWNLOAD_EVERY_DATE

# 3) Nur Frauenwochen
python3 main.py --profile DOWNLOAD_FRAUENTAGE

# 4) SIMPLE Kategorie per normalisiertem Label
python3 main.py --profile DOWNLOAD_CAT_BÜHNE_THEATER

# 5) ADVANCED Kategorien per Label (mehrere Werte mit Delimiter)
python3 main.py --profile 'DOWNLOAD_CAT_LABEL=Bühne · Theater;Vorträge Diskussion'

# 6) ADVANCED Kategorien per IDs (mehrere Werte)
python3 main.py --profile 'DOWNLOAD_CAT_ID=908119,908120|908121'

# 7) ADVANCED Sammelbegriffe per Labels (mehrere Werte)
python3 main.py --profile 'DOWNLOAD_SAMMEL_LABEL=Frauenwochen,Welcome Service Region Stuttgart'

# 8) Kombination Serie + Kategorie (Direktaufruf des Fetchers)
python3 app/fetch_structured_data.py --series-id=330100 --cat-id=908106 --anz=-1
```

## Advanced: Direkter Scriptaufruf

```bash
python3 app/fetch_structured_data.py --series-id=-1 --anz=-1
python3 app/fetch_structured_data.py --series-id=330100 --anz=-1
```

## Verarbeitung und Export (Pre-/Post-Processing)

Die Pipeline verarbeitet `loadData_20307012.json` und `jsonld_20307012_generated.json`,
bereinigt Textfelder und erzeugt daraus Boilerplate-JSON sowie optional CSV/XML.

### Nur Pre-Processing

```bash
python3 app/preprocess_data.py --config config/processing_config.json
```

### Pre- + Post-Processing (CSV/XML)

```bash
python3 app/postprocess_output.py --config config/processing_config.json
```

Alternativ direkt ueber die kombinierte Pipeline:

```bash
python3 app/process_data_pipeline.py --config config/processing_config.json
```

### Konfiguration

Best-Practice Default:

- `config/processing_config.json`

Wichtige Optionen in der Config:

- Pre-Processing:
  - `preprocessing.text_fields`
  - `preprocessing.remove_line_breaks_and_tabs`
  - `preprocessing.remove_html_tags`
  - `preprocessing.remove_html_entities`
  - `preprocessing.trim_whitespace`
- Export:
  - `export.formats` (`csv`, `xml`)
  - `export.field_mappings` (JSON-Label -> CSV-Spalte/XML-Tag)
  - `export.fields` (zu exportierende Felder)
  - `export.csv.delimiter`, `export.csv.quotechar`, `export.csv.escapechar`
  - `export.encoding`, `export.line_ending`
  - `export.date_output_format`
  - `export.rows_per_file.enabled` (Chunking ein/aus)
  - `export.rows_per_file.value` (Zeilen pro Datei, nur relevant wenn enabled=true)
  - `export.filename_template`
  - `export.output_dir`

Dateinamen-Template:

- Empfohlen: `"{source}_{format}_{timestamp}{_part{part}}.{ext}"`
- Bedeutung:
  - Bei `rows_per_file.enabled=true` wird `{_part{part}}` zu z. B. `_part1`.
  - Bei `rows_per_file.enabled=false` wird der Block komplett entfernt.

### ENV-Overrides (Beispiele)

```bash
# Formate und Zielverzeichnis
PROCESS_EXPORT_FORMATS=csv,xml PROCESS_OUTPUT_DIR=output python3 app/postprocess_output.py

# CSV-Formatierung (Tab-Delimiter, Windows-Zeilenende)
PROCESS_CSV_DELIMITER='\t' PROCESS_LINE_ENDING='\r\n' python3 app/postprocess_output.py

# Dateisplitting deaktivieren (rows_per_file.value wird ignoriert)
PROCESS_ROWS_PER_FILE_ENABLED=false python3 app/postprocess_output.py

# Feldauswahl und Mapping
PROCESS_EXPORT_FIELDS='title,start_date,location_name' \
PROCESS_EXPORT_FIELD_MAPPINGS='title:Titel,start_date:Startdatum,location_name:Ort' \
python3 app/postprocess_output.py
```

Unterstuetzte ENV-Keys:

- Input/Pre-Processing:
  - `PROCESS_INPUT_FILES`
  - `PROCESS_TEXT_FIELDS`
  - `PROCESS_CLEAN_REMOVE_LINE_BREAKS`
  - `PROCESS_CLEAN_REMOVE_HTML_TAGS`
  - `PROCESS_CLEAN_REMOVE_HTML_ENTITIES`
  - `PROCESS_CLEAN_TRIM_WHITESPACE`
- Export:
  - `PROCESS_EXPORT_FORMATS`
  - `PROCESS_EXPORT_FIELDS`
  - `PROCESS_EXPORT_FIELD_MAPPINGS`
  - `PROCESS_CSV_DELIMITER`
  - `PROCESS_CSV_QUOTECHAR`
  - `PROCESS_CSV_ESCAPECHAR`
  - `PROCESS_CSV_DOUBLEQUOTE`
  - `PROCESS_CSV_QUOTING`
  - `PROCESS_EXPORT_ENCODING`
  - `PROCESS_DATE_OUTPUT_FORMAT`
  - `PROCESS_LINE_ENDING`
  - `PROCESS_ROWS_PER_FILE`
  - `PROCESS_ROWS_PER_FILE_ENABLED`
  - `PROCESS_FILENAME_TEMPLATE`
  - `PROCESS_FILENAME_CATEGORY`
  - `PROCESS_OUTPUT_DIR`
  - `PROCESS_XML_ROOT_TAG`
  - `PROCESS_XML_ITEM_TAG`
  - `PROCESS_XML_DECLARATION`

## Filter-Optionen aktualisieren

Über `main.py`:

```bash
python3 main.py --update-filters
```

Oder direkt über das Skript:

```bash
python3 app/fetch_filter_options.py
```

Output-Dateien:

- `filter/q.sammelbegrif.id.json`
- `filter/q.kat.id.json`

### Woher kommen Labels und IDs?

- Primärquelle ist die Kalenderseite:
  - `https://www.esslingen.de/freizeit-und-engagement/veranstaltungskalender`
- Extraktion erfolgt in `app/fetch_filter_options.py`:
  - `extract_series_options`: liest `<select name="q.sammelbegrif.id">` für Sammelbegriff-IDs.
  - `extract_category_options`: liest `q.kat.id`-Checkboxen/Labels für Kategorie-IDs.
- Diese JSON-Dateien werden von `main.py` für Label/ID-Auflösung genutzt (`DOWNLOAD_CAT_*`, `DOWNLOAD_SAMMEL_*` und Advanced-Varianten).

### Für Maintainer: Seitenänderungen / Break-Fix

1. Filter neu laden:
   - `python3 main.py --update-filters`
2. Ergebnis prüfen:
   - `filter/q.sammelbegrif.id.json` und `filter/q.kat.id.json` müssen `items` mit Einträgen enthalten.
3. Bei leerem/fehlerhaftem Ergebnis Parser anpassen:
   - `app/fetch_filter_options.py` Funktionen `extract_series_options` und `extract_category_options`.
4. Regression prüfen:
   - `python3 -m unittest discover -s tests -p 'test_*.py'`
5. Kurz-Smoke-Test mit README-Befehlen:
   - z. B. `python3 main.py --profile DOWNLOAD_FRAUENTAGE`

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

### Aktuelle Dateien in `structured-data/` wurden überschrieben

Das ist beabsichtigt.
Die jeweils letzte Version liegt in `structured-data/`, ältere Stände in `structured-data/history/` mit Zeitstempel.

### `requests`-Beispiel aus README funktioniert nicht

`requests` ist optional und nicht in `requirements.txt` enthalten.
Installieren bei Bedarf:

```bash
python3 -m pip install requests
```

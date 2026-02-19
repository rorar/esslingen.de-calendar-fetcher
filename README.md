# esslingen.de-calendar-fetcher

Dieses Projekt lädt strukturierte Kalenderdaten von `esslingen.de` nach `./structured-data`.

## 5-Minuten-Quickstart

| Phase | Zweck | Befehl | Ergebnis | Internet |
|---|---|---|---|---|
| -1. Clone | Repository lokal holen | `git clone https://github.com/rorar/esslingen.de-calendar-fetcher.git && cd esslingen.de-calendar-fetcher` | Projekt lokal vorhanden | Ja |
| 0. Setup | Laufzeit vorbereiten | `python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt` | Python-Umgebung bereit | Nein |
| 1. Doctor | Umgebung prüfen | `python3 main.py --doctor` | Check für Python, Config, Ordner, DNS, optionale Pakete | Teilweise |
| 2. Filter-Refresh | aktuelle Labels/IDs holen | `python3 main.py --update-filters` | `filter/q.sammelbegrif.id.json`, `filter/q.kat.id.json` | Ja |
| 3. Filter-Discovery | IDs/Labels anzeigen | `python3 main.py --list-filters` | Sicht auf nutzbare Filterwerte | Nein (bei vorhandenem Cache) |
| 4. Ingestion | Kalenderdaten laden | `python3 main.py --profile DOWNLOAD_FRAUENTAGE` | `structured-data/loadData_20307012.json`, `ical_20307012.ics`, `jsonld_20307012_generated.json` + `structured-data/history/*` | Ja |
| 5. Pre-Processing | Daten bereinigen/normalisieren | `python3 main.py --preprocess` | `output/boilerplate/runtime-snapshots/*` (Schemaquelle: `config/schema/canonical_event_v1.json`) | Nein |
| 6. Post-Processing | CSV/XML exportieren | `python3 main.py --postprocess --from-boilerplate` | `output/*.csv`, `output/*.xml` | Nein |
| 7. QA | Exporte validieren | `python3 main.py --lint-csv --lint-recursive` | Lint-Report (OK/FAIL) | Nein |

### Copy/Paste Ablauf

Repository Herunterladen:
```bash
git clone https://github.com/rorar/esslingen.de-calendar-fetcher.git
cd esslingen.de-calendar-fetcher
``` 
*Alternative per SSH:*

```bash
git clone git@github.com:rorar/esslingen.de-calendar-fetcher.git
cd esslingen.de-calendar-fetcher
```

Python-Umgebung einrichten und Abhängigkeiten installieren:
```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Programm ausführen inkl. Check-up, Filter-Refresh, Daten-Download, Pre-/Post-Processing und CSV-Linting:

```bash
python3 main.py --doctor
python3 main.py --update-filters
python3 main.py --list-filters
python3 main.py --profile DOWNLOAD_FRAUENTAGE
python3 main.py --preprocess
python3 main.py --postprocess --from-boilerplate
python3 main.py --lint-csv --lint-recursive
```



### Wichtige Varianten

```bash
python3 main.py --profile DOWNLOAD_EVERY_DATE
python3 main.py --profile DOWNLOAD_CAT_BÜHNE_THEATER
python3 main.py --profile 'DOWNLOAD_SAMMEL_LABEL=Frauenwochen,Welcome Service Region Stuttgart'
python3 main.py --profile DOWNLOAD_FRAUENTAGE --backend auto
```

### Wo liegt was?

- Rohdaten aktuell: `structured-data/`
- Rohdaten-Historie: `structured-data/history/`
- Laufzeit-Snapshots: `output/boilerplate/runtime-snapshots/`
- Kanonisches Schema (versioniert): `config/schema/canonical_event_v1.json`
- Source-nahe Schema-Boilerplates (optional): `output/boilerplate/schema-boilerplates/source_*.json`
- Exportdateien: `output/*.csv`, `output/*.xml`

## Dateien

- `main.py`: empfohlener Einstieg über vordefinierte Profile.
- `app/fetch_structured_data.py`: Downloader-Implementierung (JSON, ICS, erzeugtes JSON-LD, History-Snapshots).
- `app/preprocess_data.py`: nur Pre-Processing (bereinigt Daten, erzeugt Runtime-Snapshots; source-nahe Schema-Boilerplates optional).
- `app/postprocess_output.py`: Post-Processing (CSV/XML Export in `output/`) aus Rohdaten oder Boilerplate.
- `app/lint_csv.py`: CSV-Linting via Frictionless (Struktur + optional Header-Schema-Check).
- `app/process_data_pipeline.py`: gemeinsame Pipeline-Implementierung.
- `config/processing_config.json`: Best-Practice-Konfiguration fuer Pre-/Post-Processing.
- `requirements.txt`: keine Pflicht-Abhängigkeiten; das optionale Python-Paket `stealth_requests` aktiviert zusätzlich das `stealth-requests`-Backend.

## Setup (VENV + optionale Pakete)

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Fish-Shell:

```fish
source .venv/bin/activate.fish
python3 -m pip install -r requirements.txt
```

Shell-neutral ohne Aktivierung:

```bash
.venv/bin/python -m pip install -r requirements.txt
```

Optional für DNS-/Anti-Bot-Workarounds das zusätzliche Backend installieren:

```bash
.venv/bin/python -m pip install stealth_requests
```

Optional für CSV-Linting:

```bash
.venv/bin/python -m pip install frictionless
```

Hinweis: Wenn Installation wegen DNS fehlschlägt, funktionieren Downloads weiterhin über `curl` oder `urllib`.

## Standardnutzung (empfohlen)

`main.py` steuert den Download über Profile und ruft intern `app/fetch_structured_data.py` auf.

### Schritt 0 (optional): Doctor-Check ausführen

```bash
python3 main.py --doctor
```

Der Doctor prüft Python-Version, Verzeichnisse, optionale Pakete, `curl`, Filter-Cache und Netzwerkbasischecks.

### Schritt 1 (empfohlen): Filter-Optionen aktualisieren

```bash
python3 main.py --update-filters
```

Optional mit explizitem Download-Backend:

```bash
python3 main.py --update-filters --backend stealth
```

**Warum zuerst?**
Damit Label- und ID-Mappings aktuell sind und du das Programm korrekt konfigurieren kannst.

Label entsprechen z. B. den Kategorienamen wie bspw. `Begegnung` im Kalender-Frontend, IDs sind die korrespondierenden internen Werte für API-Parameter.

**Netzwerk-Hinweis:**
`--update-filters` und alle Download/Profile-Aufrufe (`--profile ...`) benötigen Internetzugriff auf `www.esslingen.de`.
Die lokalen Processing-Schritte (`--preprocess` / `--postprocess`) funktionieren auch ohne Internet, sofern Eingaben vorhanden sind:
Rohdaten in `structured-data/` oder Runtime-Snapshots in `output/boilerplate/runtime-snapshots/`.

**Hinweis:** 
Bei fehlenden Cache-Dateien wird automatisch ein Update versucht. Für reproduzierbare Ergebnisse sollte `--update-filters` trotzdem zuerst ausgeführt werden.
Automatische Refreshes bei Label-Auflösung laufen intern leise; der explizite Aufruf `--update-filters` zeigt den vollen Output.

### Schritt 1b (optional): Filter anzeigen

```bash
python3 main.py --list-filters
```

Gibt `q.sammelbegrif.id` und `q.kat.id` mit IDs/Labels aus, damit Profile leichter konfiguriert werden können.

### Schritt 2: Profil ausführen

```bash
python3 main.py --profile every_date
python3 main.py --profile frauentage
```

Optional anderes Ausgabeverzeichnis:

```bash
python3 main.py --profile frauentage --out-dir structured-data
```

Optional mit Backend-Auswahl (`auto`, `stealth`, `stealth-requests`, `curl`, `urllib`):

```bash
python3 main.py --profile frauentage --backend auto
```

## Profile in `main.py`

### Hardcoded Profile:

- `DOWNLOAD_EVERY_DATE`
  - entspricht: `--series-id=-1 --anz=-1`
- `DOWNLOAD_FRAUENTAGE`
  - entspricht: `--series-id=330100 --anz=-1`

### Simple-Filter:

- `DOWNLOAD_CAT_<ID|LABEL>`
  - setzt genau einen Kategorie-Filter (`q.kat.id`) und lädt mit `--series-id=-1 --anz=-1`
- `DOWNLOAD_SAMMEL_<ID|LABEL>`
  - setzt genau einen Sammelbegriff-Filter (`q.sammelbegrif.id`) und lädt mit `--anz=-1`

### Advanced-Filter (Multi-Werte):

- `DOWNLOAD_CAT_ID=<ID[,ID2...]>`
- `DOWNLOAD_CAT_LABEL=<LABEL[,LABEL2...]>`
- `DOWNLOAD_SAMMEL_ID=<ID[,ID2...]>`
- `DOWNLOAD_SAMMEL_LABEL=<LABEL[,LABEL2...]>`

Unterstützte Delimiter für Multi-Werte: `,` `;` `|` `+`

Hinweise:

- Werte mit Delimiter-Zeichen im Label können in Quotes gesetzt werden, z. B. `"Alpha, Beta"+"C++ Kurs"`.
- Delimiter können alternativ escaped werden, z. B. `Alpha\, Beta+C\+\+ Kurs`.
- Apostrophe innerhalb von Labels (z. B. `L'art`) werden als normale Zeichen behandelt.
- Unbalancierte Quotes führen zu einer klaren Fehlermeldung.

### Beispiele:

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
python3 main.py --profile 'DOWNLOAD_CAT_ID=908106,908119|908120'
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

### Hinweise zur Label-Auflösung:

- Für ADVANCED-Label werden Varianten wie `Bühne · Theater` und `Bühne Theater` gleich behandelt.
- Für SIMPLE-Label werden normalisierte Schreibweisen wie `BÜHNE_THEATER` akzeptiert.

## Copy/Paste Profile

1. Doctor-Check

```bash
python3 main.py --doctor
```

2. Filter-Listen aktualisieren

```bash
python3 main.py --update-filters
```

3. Filter-IDs/Labels anzeigen

```bash
python3 main.py --list-filters
```

4. Alle Termine (Default-Kalender)

```bash
python3 main.py --profile DOWNLOAD_EVERY_DATE
```

5. Nur Frauenwochen

```bash
python3 main.py --profile DOWNLOAD_FRAUENTAGE
```

6. Nur Frauenwochen mit automatischer Backend-Reihenfolge

```bash
python3 main.py --profile DOWNLOAD_FRAUENTAGE --backend auto
```

7. SIMPLE Kategorie per normalisiertem Label

```bash
python3 main.py --profile DOWNLOAD_CAT_BÜHNE_THEATER
```

8. ADVANCED Kategorien per Label (mehrere Werte mit Delimiter)

```bash
python3 main.py --profile 'DOWNLOAD_CAT_LABEL=Bühne · Theater;Vorträge Diskussion'
```

9. ADVANCED Kategorien per IDs (mehrere Werte)

```bash
python3 main.py --profile 'DOWNLOAD_CAT_ID=908106,908119|908120'
```

10. ADVANCED Sammelbegriffe per Labels (mehrere Werte)

```bash
python3 main.py --profile 'DOWNLOAD_SAMMEL_LABEL=Frauenwochen,Welcome Service Region Stuttgart'
```

11. Kombination Serie + Kategorie (Direktaufruf des Fetchers)

```bash
python3 app/fetch_structured_data.py --series-id=330100 --cat-id=908106 --anz=-1 --backend auto
```

12. Nur Pre-Processing über `main.py`

```bash
python3 main.py --preprocess
```

13. Nur Post-Processing über `main.py`

```bash
python3 main.py --postprocess
```

14. Post-Processing mit eigener Config über `main.py`

```bash
python3 main.py --postprocess --process-config config/processing_config.json
```

15. Download + Post-Processing in einem Lauf

```bash
python3 main.py --profile frauentage --postprocess
```

16. 2-Phasen-Flow: Preprocess und danach Export aus Boilerplate

```bash
python3 main.py --preprocess
```

```bash
python3 main.py --postprocess --from-boilerplate
```

17. CSV-Linting der Exportdateien (Frictionless)

```bash
python3 main.py --lint-csv
```

## Advanced: Direkter Scriptaufruf

```bash
python3 app/fetch_structured_data.py --series-id=-1 --anz=-1 --backend auto
python3 app/fetch_structured_data.py --series-id=330100 --anz=-1 --backend stealth
python3 app/fetch_filter_options.py --backend auto
```

## Verarbeitung und Export (Pre-/Post-Processing)

Die Pipeline kann in zwei Modi arbeiten:

- `input.mode=raw`:
  - liest Rohdaten aus `structured-data/*.json`
  - führt Normalisierung + Pre-Processing aus (kanonisches Datums-/Zeitformat)
  - schreibt Runtime-Snapshots nach `output/boilerplate/runtime-snapshots/`
  - nutzt standardmäßig das versionierte Schema aus `config/schema/canonical_event_v1.json`
  - erzeugt optional pro Eingangsdatei source-nahe Schema-Boilerplates (`source_<datei>.json`)
  - erzeugt optional CSV/XML
- `input.mode=boilerplate`:
  - liest bereits bereinigte Datensätze aus `output/boilerplate/runtime-snapshots/boilerplate_*.json`
  - erzeugt CSV/XML ohne erneute Rohdaten-Normalisierung

Voraussetzung bei `raw`:
Die Eingabedateien in `structured-data/` müssen vorhanden sein (z. B. durch einen früheren Download-Lauf).

Voraussetzung bei `boilerplate`:
Es müssen Runtime-Snapshot-Dateien in `output/boilerplate/runtime-snapshots/` (oder per Config/ENV gesetzt) vorhanden sein.

Schema-Hinweis:
Die Felddefinitionen (Reihenfolge/Namen) kommen primär aus der Schema-Boilerplate.
`export.fields` und `export.field_mappings` in der Config sind damit optional und dienen als Override.
Im Projekt zeigt `schema.file` auf `config/schema/canonical_event_v1.json` (versionierte Source of Truth).
Source-nahe Schema-Boilerplates sind optional und standardmäßig deaktiviert.
Zeit-Hinweis:
Wenn `time` einen Bereich enthält (z. B. `18:00-20:00`), werden zusätzlich `start_time=18:00` und `end_time=20:00` exportiert.

### Artefakte unter `output/boilerplate/`

- `output/boilerplate/runtime-snapshots/`
  - enthält die bereinigten Laufzeitdaten (`boilerplate_<source>.json`) für den Export-Flow.
- `output/boilerplate/schema-boilerplates/source_<source>.json`
  - optionale source-nahe Felddefinitionen aus den Rohdateien (nur wenn `schema.source_boilerplates.enabled=true`).

### Kanonisches Schema unter `config/schema/`

- `config/schema/canonical_event_v1.json`
  - versionierte Felddefinition für Export-Reihenfolge und Standard-Labels (empfohlene Source of Truth).

### Empfohlener 2-Phasen-Flow (echte Übergabe)

1. Pre-Processing erzeugt Boilerplates

```bash
python3 main.py --preprocess
```

2. Post-Processing exportiert aus Boilerplates

```bash
python3 main.py --postprocess --from-boilerplate
```

### Nur Pre-Processing

Ueber `main.py` (empfohlen):

```bash
python3 main.py --preprocess
```

Mit eigener Config:

```bash
python3 main.py --preprocess --process-config config/processing_config.json
```

Direktes Skript:

```bash
python3 app/preprocess_data.py --config config/processing_config.json
```

### Pre- + Post-Processing (CSV/XML)

Ueber `main.py` (empfohlen):

```bash
python3 main.py --postprocess
```

Aus Boilerplates (2-Phasen-Flow):

```bash
python3 main.py --postprocess --from-boilerplate
```

Mit eigener Config:

```bash
python3 main.py --postprocess --process-config config/processing_config.json
```

Kombiniert mit Download in einem Lauf (Download + Post-Processing):

```bash
python3 main.py --profile frauentage --postprocess
```

Direktes Skript:

```bash
python3 app/postprocess_output.py --config config/processing_config.json
```

Direktes Skript aus Boilerplates:

```bash
python3 app/postprocess_output.py --config config/processing_config.json --from-boilerplate
```

CSV-Linting über `main.py`:

```bash
python3 main.py --lint-csv
```

CSV-Linting mit rekursiver Suche und explizitem Output-Verzeichnis:

```bash
python3 main.py --lint-csv --lint-output-dir output --lint-recursive
```

CSV-Linting für eine einzelne Datei:

```bash
python3 main.py --lint-csv --lint-csv-file output/loadData_20307012_csv_<TIMESTAMP>.csv
```

CSV-Linting für die zuletzt erzeugten CSV-Dateien:

```bash
python3 main.py --lint-csv \
  --lint-csv-file "$(ls -t output/loadData_20307012_csv_*.csv | head -n 1)" \
  --lint-csv-file "$(ls -t output/jsonld_20307012_generated_csv_*.csv | head -n 1)"
```

CSV-Linting mit Header-Schema-Check:

```bash
python3 main.py --lint-csv --lint-schema-check
```

CSV-Linting im strikten Config-Modus (Delimiter/Encoding aus Config + Schema-Check):

```bash
python3 main.py --lint-csv --lint-strict-config
```

Direktes Lint-Skript:

```bash
python3 app/lint_csv.py --config config/processing_config.json
```

Alternativ direkt ueber die kombinierte Pipeline:

```bash
python3 app/process_data_pipeline.py --config config/processing_config.json
```

### CSV Lint (Frictionless)

`app/lint_csv.py` validiert exportierte CSV-Dateien mit Frictionless.

- Standardlauf:
  - scannt `export.output_dir` aus der Config nach `*.csv`.
  - validiert strukturell (Frictionless Auto-Erkennung für CSV-Dialekt).
  - Delimiter/Encoding aus Config werden nur im strikten Modus erzwungen.
  - berücksichtigt auch ältere Historien-Dateien im `output/`-Ordner.
- Optional:
  - `--schema-check` bzw. `--lint-schema-check`: erwartete Header aus Schema/Config prüfen.
  - `--strict-config` bzw. `--lint-strict-config`: Config-Dialekt erzwingen und Schema-Check aktivieren.
  - `--no-schema-check` bzw. `--lint-no-schema-check`: Schema-Check explizit deaktivieren.
- Exit-Codes:
  - `0`: alle CSV-Dateien valide
  - `1`: mindestens eine CSV-Datei fehlerhaft oder nicht gefunden
  - `2`: Setup-/Konfigurationsproblem (z. B. `frictionless` nicht installiert)

### Konfiguration

Best-Practice Default:

- `config/processing_config.json`

Wichtige Optionen in der Config:

- Input:
  - `input.mode` (`raw` oder `boilerplate`)
  - `input.files` (Rohdaten-Dateien für `raw`)
  - `input.boilerplate_dir` (Quelle für Runtime-Snapshots `boilerplate_*.json`)
  - `input.boilerplate_files` (optionale explizite Dateiliste statt `boilerplate_dir`)
- Schema:
  - `schema.enabled`
  - `schema.file` (im Projekt standardmäßig `config/schema/canonical_event_v1.json`; leer = automatische Datei unter `output/boilerplate/schema-boilerplates/`)
  - `schema.source_boilerplates.enabled` (erzeugt source-nahe Schema-Boilerplates pro Input-Datei)
  - `schema.source_boilerplates.dir` (leer = automatisch `output/boilerplate/schema-boilerplates/`)
- Pre-Processing:
  - `preprocessing.text_fields`
  - `preprocessing.remove_line_breaks_and_tabs`
  - `preprocessing.remove_html_tags`
  - `preprocessing.remove_html_entities`
  - `preprocessing.trim_whitespace`
- Export:
  - `export.formats` (`csv`, `xml`)
  - `export.field_mappings` (optional: Override für Spalten-/Tag-Namen)
  - `export.fields` (optional: Override für Feldauswahl/Reihenfolge)
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
PROCESS_EXPORT_FORMATS=csv,xml PROCESS_OUTPUT_DIR=output python3 main.py --postprocess

# Post-Processing direkt aus Boilerplates
PROCESS_INPUT_MODE=boilerplate PROCESS_BOILERPLATE_DIR=output/boilerplate/runtime-snapshots python3 main.py --postprocess

# Eigenes Schema-Boilerplate verwenden
PROCESS_SCHEMA_FILE=config/schema/canonical_event_v1.json python3 main.py --postprocess

# Source-nahe Schema-Boilerplates deaktivieren
PROCESS_SCHEMA_SOURCE_BOILERPLATES_ENABLED=false python3 main.py --preprocess

# CSV-Formatierung (Tab-Delimiter, Windows-Zeilenende)
PROCESS_CSV_DELIMITER='\t' PROCESS_LINE_ENDING='\r\n' python3 main.py --postprocess

# Dateisplitting deaktivieren (rows_per_file.value wird ignoriert)
PROCESS_ROWS_PER_FILE_ENABLED=false python3 main.py --postprocess

# Feldauswahl und Mapping
PROCESS_EXPORT_FIELDS='title,start_date,location_name' \
PROCESS_EXPORT_FIELD_MAPPINGS='title:Titel,start_date:Startdatum,location_name:Ort' \
python3 main.py --postprocess
```

Unterstuetzte ENV-Keys:

- Input/Pre-Processing:
  - `PROCESS_INPUT_MODE`
  - `PROCESS_INPUT_FILES`
  - `PROCESS_BOILERPLATE_DIR`
  - `PROCESS_BOILERPLATE_FILES`
  - `PROCESS_SCHEMA_ENABLED`
  - `PROCESS_SCHEMA_FILE`
  - `PROCESS_SCHEMA_SOURCE_BOILERPLATES_ENABLED`
  - `PROCESS_SCHEMA_SOURCE_BOILERPLATES_DIR`
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

Optional mit Backend:

```bash
python3 main.py --update-filters --backend auto
```

Oder direkt über das Skript:

```bash
python3 app/fetch_filter_options.py --backend auto
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
   - `python3 main.py --update-filters --backend auto`
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

#### Python (`stealth-requests`, optional)

```python
import stealth_requests as stealth

url = (
    "https://www.esslingen.de/site/Esslingen_Layout_2022/"
    "VXC/20307012/loadData/loadData.json"
    "?action=pre&q.sammelbegrif.id=330100&anz=-1&SORT=2"
    "&dateformat=XDATE&xstart=0&loadgruppe=geg&loadgruppe=dhhd&loadgruppe=kkfjfj"
)

resp = stealth.get(url, timeout=60, impersonate="chrome")
if resp.status_code >= 400:
    raise RuntimeError(f"HTTP {resp.status_code}")
print(resp.text[:500])
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

## Backend-Hinweis

Die Downloader (`main.py`, `app/fetch_structured_data.py`, `app/fetch_filter_options.py`) unterstützen:

- `--backend auto` (Standard):
  - versucht zuerst `stealth-requests` (wenn installiert),
  - dann `curl` (wenn vorhanden),
  - dann `urllib` als Fallback.
- `--backend stealth` oder `--backend stealth-requests`: startet mit `stealth-requests`, fällt bei Fehlern auf `curl` und dann `urllib` zurück.
- `--backend curl`: startet mit `curl`, fällt bei Fehlern auf `urllib` zurück.
- `--backend urllib`: erzwingt Python-`urllib`.

Der tatsächlich verwendete Backend-Pfad wird ausgegeben, z. B. `Download backend(s): curl`.

## Troubleshooting

Allgemeiner Schnellcheck:

```bash
python3 main.py --doctor
```

### `Could not resolve host: www.esslingen.de`

Ursache: DNS-/Netzwerkproblem.

Checks:

```bash
curl --noproxy '*' -sS 'https://www.esslingen.de' | head
```

Wenn das fehlschlägt, später erneut versuchen oder lokale DNS/Netzwerk-Konfiguration prüfen.

### `stealth-requests` nicht installiert

Das ist unkritisch, solange `curl` oder `urllib` verfügbar sind.
Bei Bedarf nachinstallieren:

```bash
.venv/bin/python -m pip install stealth_requests
```

### `curl` nicht vorhanden

Das Skript erkennt das automatisch und nutzt den Python-`urllib`-Fallback (oder `stealth-requests`, falls verfügbar).
Du kannst den aktiven Backend-Hinweis im Skript-Output sehen, z. B.:

- `Download backend(s): stealth-requests`
- `Download backend(s): curl`
- `Download backend(s): urllib`

### Zu wenige/unerwartete Termine im JSON

Achte auf die Parameter:

- `anz=-1` lädt alle verfügbaren Einträge.
- `q.sammelbegrif.id=-1` lädt alle Reihen.
- `q.sammelbegrif.id=330100` lädt Frauenwochen.

Beispiel (Frauenwochen komplett):

```bash
python3 app/fetch_structured_data.py --series-id=330100 --anz=-1 --backend auto
```

### Aktuelle Dateien in `structured-data/` wurden überschrieben

Das ist beabsichtigt.
Die jeweils letzte Version liegt in `structured-data/`, ältere Stände in `structured-data/history/` mit Zeitstempel.

### Optionales Python-Paket aus den Beispielen fehlt

`requests` und `stealth-requests` sind optional und nicht zwingend für den Haupt-Workflow.
Installieren bei Bedarf in der VENV:

```bash
.venv/bin/python -m pip install requests
.venv/bin/python -m pip install stealth_requests
```

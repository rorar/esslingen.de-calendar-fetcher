# 🚀 Einsteiger-Guide: Esslingen.de Calendar Fetcher

Willkommen! Dieses Tool hilft dir, Veranstaltungen von der Webseite *esslingen.de* herunterzuladen, zu bereinigen und als Tabelle (CSV) zu speichern. Ideal für Datenanalysen, eigene Kalender oder Programmübersichten.

## 📋 Voraussetzungen

Du benötigst lediglich:
1.  **Python** (Version 3.10 oder neuer).
2.  Ein Terminal (Eingabeaufforderung/Konsole).
3.  Eine Internetverbindung.

---

## 1. Installation & Umgebung einrichten

Um das Projekt sauber auszuführen, erstellen wir eine isolierte Umgebung (Virtual Environment) und installieren dort die Abhängigkeiten.

```bash
# 1. In das Verzeichnis wechseln
cd esslingen.de-calendar-fetcher

# 2. Virtuelle Umgebung (.venv) erstellen
python3 -m venv .venv

# 3. Umgebung aktivieren
# Auf Linux/Mac:
source .venv/bin/activate
# Auf Windows (PowerShell):
# .venv\Scripts\Activate.ps1

# 4. Abhängigkeiten INNERHALB der Umgebung installieren
pip install -r requirements.txt
```
*(Hinweis: Wenn du später weiterarbeiten willst, denke immer daran, vorher `source .venv/bin/activate` auszuführen.)*

---

## 2. Der System-Check (Der "Doctor") 🩺

Bevor wir starten, lassen wir das Tool prüfen, ob alles bereit ist.

```bash
python3 main.py --doctor
```

**Was du sehen solltest:**
Eine Liste mit `[OK]`.
*   Wenn bei `Netzwerk/DNS` oder `Python` ein `[FAIL]` steht, musst du das beheben.
*   Warnungen (`[WARN]`) sind okay, solange "Python" und "Config" grün sind.

---

## 3. Der erste Test (Profil "Frauentage")

Für den schnellen Start gibt es im Code **fest hinterlegte (hardcoded) Profile**. Das Profil `frauentage` ist so ein Beispiel – es ist fest im Code (`main.py`) definiert, damit du sofort testen kannst, ohne lange Parameter suchen zu müssen.

Führe folgenden Befehl aus, um Daten zu laden, zu bereinigen und zu exportieren:

```bash
python3 main.py --profile frauentage --preprocess --postprocess
```

---

## 4. Eigene Filter & Kategorien nutzen 🔍

Du möchtest bestimmt nicht immer nur die Frauentage sehen. Hier lernst du, wie du gezielt Konzerte, Führungen oder andere Events lädst.

**Schritt A: Herausfinden, was es gibt**
Lade die aktuelle Liste aller Kategorien von der Webseite:
```bash
python3 main.py --update-filters --list-filters
```
Du erhältst eine Liste wie:
*   `- 336100: Esslinger Meisterkonzerte` (Sammelbegriff)
*   `- 908107: Konzerte · Musik` (Kategorie)
*   `- 908112: Stadtführung` (Kategorie)

**Schritt B: Gezielt herunterladen**
Nutze nun `DOWNLOAD_CAT_LABEL=` (für Themen) oder `DOWNLOAD_SAMMEL_LABEL=` (für Serien) gefolgt von den gewünschten Begriffen.

*   **Beispiel 1: Musik & Konzerte (Kategorie)**
    ```bash
    python3 main.py --profile DOWNLOAD_CAT_LABEL="Konzerte · Musik" --preprocess --postprocess
    ```

*   **Beispiel 2: Stadtführungen (Kategorie)**
    ```bash
    python3 main.py --profile DOWNLOAD_CAT_LABEL=Stadtführung --preprocess --postprocess
    ```

*   **Beispiel 3: Esslinger Meisterkonzerte (Serie)**
    Hier nutzen wir `DOWNLOAD_SAMMEL_LABEL`, da es sich um eine Eventserie handelt.
    ```bash
    python3 main.py --profile DOWNLOAD_SAMMEL_LABEL="Esslinger Meisterkonzerte" --preprocess --postprocess
    ```

*   **Profi-Tipp: Mehrere Filter gleichzeitig**
    Du kannst mehrere Begriffe mit Komma `,` trennen.
    ```bash
    # Lädt Konzerte UND Theater
    python3 main.py --profile DOWNLOAD_CAT_LABEL="Konzerte · Musik,Theater" --preprocess --postprocess
    ```

---

## 5. Das Ergebnis ansehen 📂

Egal welches Profil du genutzt hast, deine Dateien landen im Ordner `output`.

```bash
ls -l output/
```

Die Dateinamen sind technisch aufgebaut und enthalten einen Zeitstempel (z.B. `20260219_...`).
Du wirst meistens zwei Arten von Dateien sehen:

*   `loadData_..._csv_... .csv`: Die klassische Datenansicht. **Das ist meistens die Datei, die du suchst.**
*   `jsonld_..._csv_... .csv`: Eine alternative Datenstruktur (technischer).

Öffne die Datei einfach in **Excel**, **LibreOffice** oder **Numbers**.

*Tipp: Sortiere im Explorer nach "Änderungsdatum", um die neueste Datei oben zu sehen.*

---

## 6. Ausgabe anpassen (Konfiguration) ⚙️

Du möchtest das Trennzeichen der CSV ändern (z. B. Komma statt Semikolon) oder andere Spalten exportieren?

1.  Öffne die Datei `config/processing_config.json` in einem Texteditor.
2.  Suche den Abschnitt `"export"` -> `"csv"`.

**Beispiel: Trennzeichen ändern**
```json
"csv": {
    "delimiter": ",",   <-- Ändere dies z.B. zu "," oder ";"
    "quotechar": """,
    ...
}
```

3.  Suche den Abschnitt `"export"` -> `"filename_template"`, um die Dateinamen der Ausgabedateien zu ändern.

**Beispiel: Orte per Suchen/Ersetzen korrigieren**
Wenn in den Quelldaten `Ort siehe Beschreibung` steht, kannst du das automatisch ersetzen:
```json
"replacements": {
  "enabled": true,
  "rules": [
    {
      "field": "location_name",
      "search": "Ort siehe Beschreibung",
      "replace": "Kommunales Kino",
      "mode": "exact",
      "case_sensitive": false
    }
  ]
}
```

**Beispiel: Nur bestimmte Events verarbeiten (ID/Titel/Link)**
```json
"selection": {
  "enabled": true,
  "ids": ["523253141860", "523253151003"],
  "titles": ["Iftar für Frauen"],
  "urls": ["https://www.esslingen.de/frauenwochen"],
  "case_sensitive": false
}
```
Wenn mehrere Listen gesetzt sind, gilt eine ODER-Logik (ID oder Titel oder URL).
Bei URL-Filtern werden Detailseiten mit gleicher `nodeID` als derselbe Termin erkannt
(z. B. `.../zmdetail/index.html?nodeID=...` und `.../zmdetail_<id>/index.html?nodeID=...`).
Du kannst alternativ auch per CLI filtern:
`python3 main.py --postprocess --event-id 523253141860,523253151003`

Änderungen werden beim nächsten Aufruf mit `--postprocess` sofort wirksam.

---

## 7. Verstehen: Wie werden die Daten gemappt? 🗺️

Vielleicht wunderst du dich, warum in der CSV "Titel" steht, obwohl im JSON `name` oder `titel` steht.

Das Tool nutzt ein **Standard-Schema** (genannt `canonical_event_v1`) als versionierte Source of Truth.
Die Definition liegt in: `config/schema/canonical_event_v1.json`.

Hier sind alle verfügbaren Standard-Felder:

| Interner Name (ID) | Standard-Label (CSV-Kopf) | Inhalt |
| :--- | :--- | :--- |
| `id` | ID | Eindeutige Kennung |
| `title` | Titel | Name der Veranstaltung |
| `start_date` | Startdatum | Beginn (YYYY-MM-DD) |
| `end_date` | Enddatum | Ende (YYYY-MM-DD) |
| `time` | Uhrzeit | Uhrzeit (HH:MM) |
| `start_time` | Startzeit | Startzeit (HH:MM), z. B. aus `18:00-20:00` |
| `end_time` | Endzeit | Endzeit (HH:MM), z. B. aus `18:00-20:00` |
| `description` | Beschreibung | Details zum Event |
| `location_name` | Ort | Veranstaltungsort |
| `location_postal_code` | PLZ | Postleitzahl |
| `location_city` | Stadt | Stadt |
| `category` | Kategorie | Art (z.B. Konzert) |
| `series` | Sammelbegriff | Serie (z.B. Meisterkonzerte) |
| `url` | URL | Link zur Webseite |
| `source_type` | QuelleTyp | Herkunft (jsonld/loadData) |
| `source_file` | QuelleDatei | Dateiname der Quelle |

**Du willst Spalten umbenennen?**
Überschreibe das Mapping einfach in deiner Konfiguration `config/processing_config.json`:

```json
"export": {
    "field_mappings": {
        "title": "Veranstaltungsname",
        "start_date": "Datum",
        "location_name": "Wo"
    },
    ...
}
```
Beim nächsten Lauf wird "Titel" durch "Veranstaltungsname" ersetzt.

**Du willst nur bestimmte Spalten?**
Definiere die Liste unter `"export"` -> `"fields"`. Die Reihenfolge bestimmt auch die Spaltenreihenfolge in der CSV:
```json
"export": {
    "fields": ["title", "start_date", "location_name"],
    ...
}
```

**Alternative (für Profis):**
Du kannst das Mapping auch per Umgebungsvariable setzen:
`export PROCESS_EXPORT_FIELD_MAPPINGS="title:Name,start_date:Wann"`

---

## 8. Hilfe & Tipps 💡

*   **Verbindungsprobleme?**
    Wenn der Download fehlschlägt oder blockiert wird ("Access Denied"), kannst du ein Tarnkappen-Modul nutzen:
    1.  Installiere es: `pip install stealth_requests`
    2.  Nutze den Parameter: `python3 main.py --backend stealth ...`
*   **Große Datenmengen:**
    Das Profil `every_date` lädt **alle** Termine. Das dauert länger!
*   **Hilfe anzeigen:**
    `python3 main.py --help` zeigt dir alle verfügbaren Befehle.

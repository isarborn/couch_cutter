# Couch Cutter

Ein intelligentes Video-Schnitt-Tool zum automatischen Entfernen von Werbung, Intros und Pre-Rolls aus Videos (z.B. von Zattoo-Aufzeichnungen).

## Features

- 🎬 **Automatische Werbungserkennung** - Entfernt definierte Werbeblöcke nahtlos
- ⏳ **Pre-Roll Entfernung** - Schneidet Intros und Vorspänne ab
- 🎯 **Flexible Zeitangaben** - Unterstützt MM:SS und HH:MM:SS Formate
- 🌐 **Web-Interface** - Einfache Bedienung über Browser
- 🚀 **Schnelle Verarbeitung** - Stream Copy für platzsparende Schnitte ohne Re-Encoding
- 💾 **Automatisches Backup** - Originaldateien werden gesichert
- 🐧 **Plattformübergreifend** - Läuft auf Windows, macOS und Linux (inkl. Raspberry Pi)
- 🔧 **Automatische FFmpeg-Installation** - Lädt FFmpeg bei Bedarf automatisch herunter

## Anforderungen

- Python 3.7+
- FFmpeg (wird automatisch installiert, falls nicht vorhanden)

## Installation

1. Repository klonen:
```bash
git clone https://github.com/isarborn/couch_cutter.git
cd couch_cutter
```

2. Dependencies installieren:
```bash
pip install -r requirements.txt
```

## Verwendung

### Web-Server starten

```bash
python video_server.py
```

Der Server läuft dann auf `http://localhost:5000`

### API-Endpunkte

#### `/browse`
Durchsucht das Video-Verzeichnis

Query-Parameter:
- `path` (optional): Relativer Pfad zum Durchsuchen

Beispiel:
```
GET /browse?path=Babylon%20Berlin
```

#### `/cut`
Startet einen Video-Schnitt-Job

Query-Parameter:
- `data`: Schneid-Konfiguration im Format
```
Pfad/Video.mp4[pre_roll_end, [[ad_start1,ad_end1],[ad_start2,ad_end2]], movie_end]
```

Beispiel:
```
GET /cut?data=Babylon%20Berlin/Episode1.mp4[0:05,[17:03,19:29],[22:15,24:44],40:00]
```

**Erklärung:**
- `0:05` - Alles vor 5 Sekunden entfernen (Pre-Roll)
- `[[17:03,19:29],[22:15,24:44]]` - Werbeblöcke entfernen
- `40:00` - Filmende bei 40:00 Minuten

### Command-Line Verwendung

```bash
python cut_smart.py '{"video": "/path/to/video.mp4", "pre_roll_end": "0:05", "ads": [["17:03","19:29"]], "movie_end": "40:00"}'
```

## Konfiguration

Die Basis-Verzeichnis wird in `video_server.py` konfiguriert:

```python
BASE_DIR = '/mnt/video/ZattooDownloads'
```

Passe diesen Pfad an dein Video-Verzeichnis an.

## Output

Nach dem Schneiden wird eine neue Datei erstellt:
- `{original}_clean.{ext}` - Die geschnittene Version
- `{original}.bak` - Backup der Originaldatei

Das Original wird durch die bereinigte Version ersetzt.

## Plattform-Spezifika

### Raspberry Pi
Die FFmpeg-Installation wird automatisch über `apt-get` durchgeführt.

### macOS
FFmpeg wird über Homebrew oder MacPorts installiert.

### Windows
FFmpeg wird über `winget` oder `chocolatey` installiert.

## Fehlerbehandlung

Falls FFmpeg nicht automatisch installiert werden kann, folge diesen Anweisungen:

```bash
# Linux/Raspberry Pi
sudo apt-get update && sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Windows
winget install ffmpeg
# oder
choco install ffmpeg
```

## Lizenz

MIT

## Author

isarborn

---

**Hinweis:** Stelle sicher, dass du die Rechte hast, Videos zu schneiden und zu speichern.
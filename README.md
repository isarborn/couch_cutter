# Couch Cutter

Ein Video-Schnitt-Tool zum Entfernen von Werbung, Intros und Pre-Rolls aus Videos (z.B. von Zattoo-Aufzeichnungen).

# Szenario

Du zeichnest Videos aus dem klassischen TV auf und speicherst diese auf deinem NAS oder sonstigem Gerät das deinem Fernseher eine Freigabe bietet. Ich schaue diese Videos meist mit VLC am Fernseher an. 
Naturgemäss sind diese Aufnahmen geflutet mit Werbung, aber auch mit einem Vorlauf vor dem eigentlichen Film und einem Nachlauf nach dem Film. 
Bei einer Folge einer Serie mit einer Netto-Laufzeit von 20 Minuten sieht das dann meistens so aus: 5 min. Vorlauf, 12 min. Film, 10 Minunten Werbung, 8 Minunten Film, 15 min Nachlauf.
Für 20 Minuten einer Folge hat man meistens 50 Minuten auf der Platte. Dies ungefähr 66% Datenmüll aus. 

Das schneiden am Rechner nervt. Die Daten müssen vom Speicher auf dem Rechner und wieder zurück. Weil NAS ältere Raspberrys nicht so schnell sind, dauert das und ist wenig komfortabel.

Couch_cutter installierst Du direkt auf dem Raspberry oder irgendeiner anderen Kiste, die Python unterstützt. 
Das Tool zeigt alle Videodatein in eines Ordners auf einer kleinen simplen Website als Liste an. 
<img width="647" height="599" alt="image" src="https://github.com/user-attachments/assets/3394d6e3-faeb-4b44-8a5d-9d523b786446" />

Wähle die Datei die geschnitten werden soll und gib die Schnittmarken (Anfang, Werbeblöcke, Ende) an. Es ist egal ob Du MM:SS oder HH:MM:SS verwendest. Geht beides.
<img width="821" height="244" alt="image" src="https://github.com/user-attachments/assets/f9577118-4197-44fe-8229-a273291a580f" />

Danach "Schnitt starten" klicken. 

Das Tool schneidet dann mit ffmpeg die Datei zurecht. Die Originaldatei erhält die Endung .bak und dienst als Backup, für den Fall, dass was schief gegangen ist. Wenn man sicher ist nichts 
verloren zu haben, kann man sie löschen.
Die geschnitte Datei erhält genau den Namen der ursprünglichen Datei.


## Features

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
3. Basisverzeichnis einstellen:
```bash
nano video_server.py
```
Dort dann in zeile 7 das Verzeichnis einstellen, in dem der Server starten soll. z.B. /mnt/video/downloads

## Verwendung

### Web-Server starten

```bash
python video_server.py
```

Der Server läuft dann auf `http://ip-deines-raspberries:5000`

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

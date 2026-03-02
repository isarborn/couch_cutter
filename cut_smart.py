#!/usr/bin/env python3
import subprocess
import os
import math
import shutil
import sys
import platform
from tempfile import NamedTemporaryFile

def ensure_ffmpeg():
    """Prüft, ob ffmpeg installiert ist. Falls nicht, versucht es zu installieren."""
    if shutil.which("ffmpeg") is not None:
        print("✓ ffmpeg ist installiert")
        return True
    
    print("⚠ ffmpeg nicht gefunden. Versuche zu installieren...")
    
    system = platform.system()
    installers = []
    
    if system == "Windows":
        installers = [
            (["winget", "install", "ffmpeg"], "winget"),
            (["choco", "install", "ffmpeg", "-y"], "chocolatey"),
        ]
    elif system == "Linux":
        # Erkennung der Linux-Distribution
        installers = [
            (["sudo", "apt-get", "update"], None),  # nur Update
            (["sudo", "apt-get", "install", "-y", "ffmpeg"], "apt-get"),
            (["sudo", "pacman", "-S", "ffmpeg", "--noconfirm"], "pacman"),
            (["sudo", "yum", "install", "-y", "ffmpeg"], "yum"),
            (["sudo", "dnf", "install", "-y", "ffmpeg"], "dnf"),
        ]
    elif system == "Darwin":  # macOS
        installers = [
            (["brew", "install", "ffmpeg"], "homebrew"),
            (["sudo", "port", "install", "ffmpeg"], "macports"),
        ]
    
    # Update für Linux durchführen
    if system == "Linux":
        try:
            subprocess.run(["sudo", "apt-get", "update"], check=False, capture_output=True, timeout=60)
        except Exception:
            pass
    
    for cmd, name in installers:
        if name is None:  # Skip nur-Update Befehle
            continue
        try:
            print(f"  Versuche {name}...")
            subprocess.run(cmd, check=True, capture_output=True, timeout=300)
            if shutil.which("ffmpeg") is not None:
                print(f"✓ ffmpeg erfolgreich mit {name} installiert")
                return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            continue
    
    print("✗ ffmpeg konnte nicht automatisch installiert werden.")
    print("  Bitte installieren Sie ffmpeg manuell:")
    if system == "Windows":
        print("  - Mit winget: winget install ffmpeg")
        print("  - Mit chocolatey: choco install ffmpeg")
        print("  - Manuell: https://ffmpeg.org/download.html")
    elif system == "Linux":
        print("  - Debian/Ubuntu: sudo apt-get install ffmpeg")
        print("  - Arch: sudo pacman -S ffmpeg")
        print("  - RedHat/CentOS: sudo yum install ffmpeg")
        print("  - Fedora: sudo dnf install ffmpeg")
    elif system == "Darwin":
        print("  - Mit Homebrew: brew install ffmpeg")
        print("  - Mit MacPorts: sudo port install ffmpeg")
    return False

def parse_time(t: str) -> float:
    """Wandelt 'MM:SS' oder 'HH:MM:SS' in Sekunden um."""
    parts = t.strip().split(':')
    parts = [int(p) for p in parts]
    if len(parts) == 2:
        m, s = parts
        return m * 60 + s
    elif len(parts) == 3:
        h, m, s = parts
        return h * 3600 + m * 60 + s
    else:
        raise ValueError(f'Ungültiges Zeitformat: {t}')

def build_keep_segments(pre_roll_end_s, ads_s, movie_end_s):
    """
    pre_roll_end_s: Sekunden, alles davor wird entfernt
    ads_s: Liste von [start_s, end_s] (Werbeblöcke, werden entfernt)
    movie_end_s: Filmende in Sekunden – alles danach weg
    """

    keep = []
    current = pre_roll_end_s

    ads_s = sorted(ads_s, key=lambda x: x[0])

    for ad_start, ad_end in ads_s:
        if ad_start > movie_end_s:
            break
        if ad_start > current:
            keep.append((current, min(ad_start, movie_end_s)))
        current = max(current, ad_end)

    if current < movie_end_s:
        keep.append((current, movie_end_s))

    return keep

def cut_smart(cfg):
    """
    cfg = {
        'video': '/mnt/video/.../Datei.mp4',
        'pre_roll_end': 'MM:SS oder HH:MM:SS',
        'ads': [['17:03','19:29'], ...],
        'movie_end': 'MM:SS oder HH:MM:SS'
    }
    """
    if not ensure_ffmpeg():
        raise RuntimeError("ffmpeg ist erforderlich, konnte aber nicht installiert werden")
    
    print("DEBUG cfg:", cfg)

    input_file = cfg['video']
    pre_roll_end = parse_time(cfg['pre_roll_end'])
    ads = cfg.get('ads', [])
    movie_end = parse_time(cfg['movie_end'])

    print("DEBUG parsed:",
          "pre_roll_end_s =", pre_roll_end,
          "ads_s =", [[parse_time(a[0]), parse_time(a[1])] for a in ads],
          "movie_end_s =", movie_end)
    

    input_file = cfg['video']
    pre_roll_end = parse_time(cfg['pre_roll_end'])
    ads = cfg.get('ads', [])
    movie_end = parse_time(cfg['movie_end'])

    ads_s = []
    for a in ads:
        if len(a) != 2:
            continue
        ads_s.append([parse_time(a[0]), parse_time(a[1])])

    keep_segments = build_keep_segments(pre_roll_end, ads_s, movie_end)
    if not keep_segments:
        print("Keine Segmente zum Behalten berechnet.")
        return

    print("Keep-Segmente:", keep_segments)

    base, ext = os.path.splitext(input_file)
    clips = []

    for idx, (start, end) in enumerate(keep_segments):
        dur = max(0, end - start)
        if dur <= 0:
            continue
        clip_file = f"{base}_keep_{idx}{ext}"

        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(math.floor(start)),
            "-i", input_file,
            "-t", str(math.ceil(dur)),
            "-map", "0",
            "-c", "copy",
            "-movflags", "+faststart",
            clip_file,
        ]
        print("FFmpeg-Clip:", " ".join(cmd))
        subprocess.run(cmd, check=True)
        clips.append(clip_file)

    if not clips:
        print("Keine Clips erzeugt.")
        return

    with NamedTemporaryFile("w", delete=False, suffix=".txt") as tf:
        list_path = tf.name
        for c in clips:
            tf.write(f"file '{c}'\n")

    output_file = f"{base}_clean{ext}"
    cmd_concat = [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_path,
        "-c", "copy",
        "-movflags", "+faststart",
        output_file,
    ]
    print("FFmpeg-Concat:", " ".join(cmd_concat))
    subprocess.run(cmd_concat, check=True)

    # Aufräumen
    try:
        for c in clips:
            if os.path.exists(c):
                os.remove(c)
        if os.path.exists(list_path):
            os.remove(list_path)
    except Exception as e:
        print("Warnung: Konnte temporäre Dateien nicht löschen:", e)

    # Original durch Clean ersetzen (mit Backup)
    try:
        backup = input_file + '.bak'
        if os.path.exists(backup):
            os.remove(backup)
        os.rename(input_file, backup)
        os.rename(output_file, input_file)
        print(f"Original ersetzt. Backup: {backup}")
    except Exception as e:
        print("Warnung: Konnte Original nicht ersetzen:", e)
        print("Clean-Datei bleibt als:", output_file)

    print("Fertig.")

if __name__ == '__main__':
    import sys, json
    if len(sys.argv) > 1:
        cfg = json.loads(sys.argv[1])
        cut_smart(cfg)

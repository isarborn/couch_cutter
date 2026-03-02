#!/usr/bin/env python3
from flask import Flask, request, jsonify
import os
import threading
import re

from cut_smart import cut_smart

BASE_DIR = '/mnt/video/ZattooDownloads'

app = Flask(__name__, static_folder='.', static_url_path='')

@app.route('/browse')
def browse():
    rel = request.args.get('path', '')  # leer = Basis
    full_path = os.path.join(BASE_DIR, rel.lstrip('/'))

    if not os.path.isdir(full_path):
        return jsonify({'error': f'Verzeichnis nicht gefunden: {full_path}'}), 404

    dirs = []
    files = []
    for entry in os.scandir(full_path):
        if entry.is_dir():
            dirs.append(entry.name)
        elif entry.is_file() and entry.name.lower().endswith(('.mp4', '.mkv')):
            files.append(entry.name)

    dirs.sort(key=str.casefold)
    files.sort(key=str.casefold)

    return jsonify({
        'path': rel,
        'dirs': dirs,
        'files': files,
    })

def parse_cut_param(param: str):
    """
    Erwartet:
      Pfad/Datei.mp4[pre, [[s1,e1],[s2,e2]], movie_end]
      oder
      Pfad/Datei.mp4[pre, [], movie_end]
    """
    print("DEBUG parse_cut_param param:", repr(param))

    # 1. Aufteilen in 'Pfad' und 'inneren Teil'
    try:
        file_part, inner = param.split('[', 1)
    except ValueError:
        raise ValueError("Fehlende '[' in data")

    inner = inner.rstrip(']')  # letztes ']' entfernen

    # 2. pre, ads_str, movie_end trennen
    # Wir suchen das erste Komma (nach pre) und das letzte Komma (vor movie_end)
    first_comma = inner.find(',')
    last_comma = inner.rfind(',')

    if first_comma == -1 or last_comma == -1 or first_comma == last_comma:
        raise ValueError("Konnte pre/ads/movie_end nicht trennen")

    pre_roll = inner[:first_comma].strip()
    ads_str = inner[first_comma + 1:last_comma].strip()
    movie_end = inner[last_comma + 1:].strip()

    print("DEBUG split:", "pre_roll=", pre_roll, "ads_str=", ads_str, "movie_end=", movie_end)

    # 3. ads_str parsen
    ads = []
    if ads_str != '[]':
        # Inhalt ohne die äußeren Klammern [[...]]
        if ads_str.startswith('[') and ads_str.endswith(']'):
            inner_ads = ads_str[1:-1].strip()
        else:
            inner_ads = ads_str

        # jetzt Paare [s,e] suchen
        import re
        pairs = re.findall(r'\[([^,]+),\s*([^]]+)\]', inner_ads)
        ads = [[s.strip(), e.strip()] for s, e in pairs]

    rel_path = file_part.strip()
    video_path = os.path.join(BASE_DIR, rel_path)
    print("DEBUG rel_path:", repr(rel_path))
    print("DEBUG video_path:", video_path)
    print("DEBUG ads parsed:", ads)

    cfg = {
        'video': video_path,
        'pre_roll_end': pre_roll,
        'ads': ads,
        'movie_end': movie_end,
    }
    return cfg


def run_cut_async(cfg):
    try:
        cut_smart(cfg)
    except Exception as e:
        print("Fehler in cut_smart:", e)

@app.route('/cut')
def cut():
    data = request.args.get('data')
    print("DEBUG data:", repr(data))

    if not data:
        return jsonify({'error': 'Parameter data fehlt'}), 400

    try:
        cfg = parse_cut_param(data)
    except Exception as e:
        return jsonify({'error': str(e), 'raw': data}), 400

    threading.Thread(target=run_cut_async, args=(cfg,)).start()

    return jsonify({'status': 'OK', 'cfg': cfg})

@app.route('/')
def root():
    return app.send_static_file('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

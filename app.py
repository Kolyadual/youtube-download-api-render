import os
import tempfile
import uuid
import time
import requests
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
CORS(app)

# Хранилище прямых ссылок (uid -> {url, expires})
video_map = {}

def get_direct_url(url):
    """Извлекает прямую ссылку на видео (аудио+видео в одном потоке)"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'format': 'bestvideo[height<=1080]+bestaudio/best[ext=m4a]/best[height<=1080]/best',
        'merge_output_format': 'mp4',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        formats = info.get('formats', [])
        
        # Приоритет – 720p со звуком
        for f in formats:
            if f.get('format_id') == '22':
                return f.get('url'), info.get('title')
        
        # Если нет 22, берём последний (обычно лучший)
        target_format = formats[-1]
        return target_format.get('url'), info.get('title')

@app.route('/api/download', methods=['POST'])
def download():
    # ... (без изменений, код загрузчика) ...

@app.route('/api/stream', methods=['POST'])
def stream():
    data = request.get_json()
    url = data.get('url')
    if not url:
        return jsonify({'error': 'URL is required'}), 400

    try:
        direct_url, title = get_direct_url(url)
        if not direct_url:
            return jsonify({'error': 'Could not extract direct URL'}), 500

        # Генерируем уникальный ID и сохраняем ссылку с таймаутом 5 часов
        uid = str(uuid.uuid4())
        video_map[uid] = {
            'url': direct_url,
            'expires': time.time() + 5 * 3600
        }

        return jsonify({
            'stream_id': uid,
            'title': title,
            'thumbnail': f'https://img.youtube.com/vi/{url.split("v=")[-1]}/hqdefault.jpg'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/video/<uid>')
def stream_video(uid):
    """Проксирует видеофайл с googlevideo"""
    entry = video_map.get(uid)
    if not entry or time.time() > entry['expires']:
        return "Video not found or expired", 404

    # Делаем запрос к прямому URL с потоковой передачей
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
    }
    resp = requests.get(entry['url'], stream=True, headers=headers)
    
    # Проксируем ответ обратно клиенту
    def generate():
        for chunk in resp.iter_content(chunk_size=8192):
            yield chunk

    return Response(
        generate(),
        status=resp.status_code,
        headers={
            'Content-Type': resp.headers.get('Content-Type', 'video/mp4'),
            'Accept-Ranges': 'bytes',
            'Access-Control-Allow-Origin': '*'
        }
    )

@app.route('/ping')
def ping():
    return 'pong'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

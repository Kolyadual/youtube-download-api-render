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

video_map = {}

def get_cookiefile():
    """Возвращает путь к файлу с куками.
    Сначала проверяет переменную окружения YOUTUBE_COOKIES,
    потом локальный файл cookies.txt (если он есть)."""
    data = os.environ.get('YOUTUBE_COOKIES')
    if data:
        path = '/tmp/cookies.txt'
        with open(path, 'w') as f:
            f.write(data)
        return path
    if os.path.exists('cookies.txt'):
        return 'cookies.txt'
    return None

def get_direct_url(url):
    """Извлекает прямую ссылку на видео со звуком"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'extractor_args': {'youtube': {'player_client': ['android']}},
        'format': 'best[height<=1080]',  # Упрощённый универсальный формат
        'merge_output_format': 'mp4',
    }
    cookiefile = get_cookiefile()
    if cookiefile:
        ydl_opts['cookiefile'] = cookiefile

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        formats = info.get('formats', [])
        
        # Ищем формат с видео и аудио в одном потоке
        for f in formats:
            if f.get('acodec') != 'none' and f.get('vcodec') != 'none':
                return f.get('url'), info.get('title')
        
        # Запасной вариант — берём последний доступный
        if formats:
            target = formats[-1]
            return target.get('url'), info.get('title')
        
        return None, info.get('title')


@app.route('/api/download', methods=['POST'])
def download():
    data = request.get_json()
    url = data.get('url')
    mode = data.get('mode', 'video')
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'extractor_args': {'youtube': {'player_client': ['android']}},
        'outtmpl': os.path.join(tempfile.gettempdir(), '%(title)s.%(ext)s'),
    }
    
    cookiefile = get_cookiefile()
    if cookiefile:
        ydl_opts['cookiefile'] = cookiefile

    if mode == 'audio':
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        ydl_opts['format'] = 'best[height<=1080]/best'  # Упрощённый
        ydl_opts['merge_output_format'] = 'mp4'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filepath = ydl.prepare_filename(info)
            if mode == 'audio':
                filepath = os.path.splitext(filepath)[0] + '.mp3'
            filename = os.path.basename(filepath)
            return jsonify({'download_url': f'/download/{filename}', 'filename': filename})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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

        uid = str(uuid.uuid4())
        video_map[uid] = {
            'url': direct_url,
            'expires': time.time() + 5 * 3600  # 5 часов
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
    entry = video_map.get(uid)
    if not entry or time.time() > entry['expires']:
        return "Video not found or expired", 404

    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
    }
    resp = requests.get(entry['url'], stream=True, headers=headers)

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


@app.route('/download/<filename>')
def serve_file(filename):
    return send_from_directory(tempfile.gettempdir(), filename, as_attachment=True)


@app.route('/ping')
def ping():
    return 'pong'


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

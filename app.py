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
    """Ищет куки в переменной окружения или файле"""
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
    """Получает прямую ссылку на видео"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'format': 'best',
        'extractor_args': {'youtube': {'player_client': ['android']}},
    }
    
    cookiefile = get_cookiefile()
    if cookiefile:
        ydl_opts['cookiefile'] = cookiefile

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info.get('url'), info.get('title', 'Без названия')


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
        ydl_opts['format'] = 'best'
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
            return jsonify({'error': 'Не удалось получить ссылку'}), 500

        uid = str(uuid.uuid4())
        video_map[uid] = {
            'url': direct_url,
            'expires': time.time() + 5 * 3600
        }

        video_id = url.split('v=')[-1].split('&')[0] if 'v=' in url else ''

        return jsonify({
            'stream_id': uid,
            'title': title,
            'thumbnail': f'https://img.youtube.com/vi/{video_id}/hqdefault.jpg' if video_id else ''
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/video/<uid>')
def stream_video(uid):
    entry = video_map.get(uid)
    if not entry or time.time() > entry['expires']:
        return "Видео не найдено или срок истёк", 404

    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36'
    }
    
    resp = requests.get(entry['url'], stream=True, headers=headers)

    def generate():
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                yield chunk

    return Response(
        generate(),
        status=resp.status_code,
        headers={
            'Content-Type': 'video/mp4',
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

import os
import tempfile
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import yt_dlp
import subprocess # Для проверки ffmpeg, но он здесь не критичен

app = Flask(__name__)
CORS(app)

@app.route('/api/download', methods=['POST']) # Оставляем для совместимости
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
        'outtmpl': os.path.join(tempfile.gettempdir(), '%(title)s.%(ext)s'),
    }
    if mode == 'audio':
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        ydl_opts['format'] = 'bestvideo[height<=1080]+bestaudio/best'
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
    """
    Новый эндпоинт для получения прямой ссылки на видео
    """
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'format': 'bestvideo[height<=1080]+bestaudio/best[ext=m4a]/best[height<=1080]/best', # Лучшее видео + аудио
        'merge_output_format': 'mp4',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False) # Мы не скачиваем!
            formats = info.get('formats', [])

            # Ищем самый подходящий формат (в идеале с видео и аудио)
            target_format = None
            for f in formats:
                if f.get('format_id') == '22': # 720p с аудио — хороший компромисс
                    target_format = f
                    break

            if not target_format:
                # Если '22' нет, берём лучшее видео и надеемся на лучшее
                target_format = formats[-1] 

            direct_url = target_format.get('url')
            if not direct_url:
                return jsonify({'error': 'Could not extract direct URL'}), 500

            return jsonify({
                'direct_url': direct_url,
                'title': info.get('title', ''),
                'thumbnail': info.get('thumbnail', ''),
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Простейшая проверка жизни
@app.route('/ping')
def ping():
    return 'pong'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

import os
import tempfile
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
CORS(app)

# ⚠️ ВСТАВЬ СЮДА URL СВОЕГО POT-СЕРВЕРА
POT_PROVIDER_URL = 'https://bgutil-ytdlp-pot-provider.onrender.com'

def get_cookiefile():
    """Возвращает путь к файлу с куками (из переменной окружения или локального файла)."""
    data = os.environ.get('YOUTUBE_COOKIES')
    if data:
        path = '/tmp/cookies.txt'
        with open(path, 'w') as f:
            f.write(data)
        return path
    if os.path.exists('cookies.txt'):
        return 'cookies.txt'
    return None

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
        'format': 'best',  # с PoToken будет работать
        'outtmpl': os.path.join(tempfile.gettempdir(), '%(title)s.%(ext)s'),
        'extractor_args': {
            'youtube': {
                # Важно: указываем плагин для получения PoToken
                'pot': {
                    'provider': 'bgutil',
                    'bgutil_url': POT_PROVIDER_URL,
                    'client_variant': 'web',  # или 'android', если web не сработает
                },
                # Дополнительно можно указать player_client (необязательно)
                'player_client': ['web'],
            }
        },
    }

    cookiefile = get_cookiefile()
    if cookiefile:
        ydl_opts['cookiefile'] = cookiefile

    if mode == 'audio':
        ydl_opts['format'] = 'bestaudio/best'
        # Конвертация в mp3 не используется, чтобы не требовать ffmpeg
        # При желании можно раскомментировать строки ниже и установить ffmpeg на Render
        # ydl_opts['postprocessors'] = [{
        #     'key': 'FFmpegExtractAudio',
        #     'preferredcodec': 'mp3',
        #     'preferredquality': '192',
        # }]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filepath = ydl.prepare_filename(info)
            filename = os.path.basename(filepath)
            return jsonify({'download_url': f'/download/{filename}', 'filename': filename})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def serve_file(filename):
    return send_from_directory(tempfile.gettempdir(), filename, as_attachment=True)

@app.route('/ping')
def ping():
    return 'pong'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

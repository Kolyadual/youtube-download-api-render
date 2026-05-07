import os
import tempfile
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
CORS(app)

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
        'format': 'best',  # ПРОСТО BEST, БЕЗ ВСЯКИХ СЛОЖНОСТЕЙ
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


@app.route('/download/<filename>')
def serve_file(filename):
    return send_from_directory(tempfile.gettempdir(), filename, as_attachment=True)


@app.route('/ping')
def ping():
    return 'pong'


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

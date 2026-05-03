import os
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
CORS(app)  # Разрешаем запросы отовсюду

@app.route('/api/download', methods=['POST'])
def download():
    data = request.get_json()
    url = data.get('url')
    mode = data.get('mode', 'video')  # 'video' или 'audio'

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
    }

    if mode == 'audio':
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
        ydl_opts['outtmpl'] = os.path.join(tempfile.gettempdir(), '%(title)s.%(ext)s')
    else:
        # Видео: лучшее качество до 1080p, чтобы не ломать однопоточный сервер
        ydl_opts['format'] = 'bestvideo[height<=1080]+bestaudio/best'
        ydl_opts['merge_output_format'] = 'mp4'
        ydl_opts['outtmpl'] = os.path.join(tempfile.gettempdir(), '%(title)s.%(ext)s')

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # После скачивания берём путь к готовому файлу
            filepath = ydl.prepare_filename(info)
            if mode == 'audio':
                # После извлечения аудио расширение меняется
                filepath = os.path.splitext(filepath)[0] + '.mp3'
            # Генерируем прямую ссылку для скачивания через наше же приложение
            download_url = f"/download/{os.path.basename(filepath)}"
            return jsonify({'download_url': download_url, 'filename': os.path.basename(filepath)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def serve_file(filename):
    # Отдаём файл из временной папки
    from flask import send_from_directory
    return send_from_directory(tempfile.gettempdir(), filename, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

import os
import yt_dlp
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import tempfile
import uuid

app = Flask(__name__)
CORS(app) # Разрешаем запросы с GitHub Pages

DOWNLOAD_FOLDER = tempfile.gettempdir() # Временная папка на сервере Render

@app.route('/download', methods=['POST'])
def download_video():
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({'error': 'URL не указан'}), 400

    # Генерируем уникальное имя, чтобы файлы не перезаписывались
    unique_id = str(uuid.uuid4())
    output_path = os.path.join(DOWNLOAD_FOLDER, f'{unique_id}.mp4')

    ydl_opts = {
        'format': 'best[height<=720]', # Ограничим качество для скорости и размера
        'outtmpl': output_path,
        'noplaylist': True, # Не скачиваем плейлисты, только одно видео
        'quiet': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            # yt-dlp может добавить расширение сам, проверяем финальное имя
            final_filepath = output_path
            if not os.path.exists(final_filepath):
                 # Иногда расширение может быть mkv/webm
                 for ext in ['mp4', 'mkv', 'webm']:
                     potential = f'{output_path[:-4]}.{ext}'
                     if os.path.exists(potential):
                         final_filepath = potential
                         break

            # Получаем безопасное оригинальное название
            safe_title = "video.mp4"
            try:
                safe_title = f"{info.get('title', 'video')}.mp4"
                safe_title = "".join(c for c in safe_title if c.isalnum() or c in (' ', '.', '_', '-')).rstrip()
            except:
                pass

            return send_file(
                final_filepath,
                as_attachment=True,
                download_name=safe_title,
                mimetype='video/mp4'
            )

    except Exception as e:
        return jsonify({'error': f'Ошибка при скачивании: {str(e)}'}), 500

if __name__ == '__main__':
    # Render сам установит PORT в переменные окружения
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

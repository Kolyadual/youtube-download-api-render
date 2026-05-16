import os
import sys
import subprocess
import uuid
import tempfile
import shutil
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/download', methods=['POST'])
def download_video():
    data = request.get_json()
    url = data.get('url') if data else None

    if not url:
        return jsonify({'error': 'URL не указан'}), 400

    # Уникальная временная папка
    temp_dir = tempfile.mkdtemp(prefix='ytdl_')
    output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')

    # Команда с User-Agent и другими заголовками
    command = [
        sys.executable, '-m', 'yt_dlp',
        '-f', 'best[height<=720]',
        '-o', output_template,
        '--no-playlist',
        '--merge-output-format', 'mp4',
        '--add-header', 'User-Agent:Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        '--add-header', 'Accept-Language:en-US,en;q=0.9',
        url
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip() or 'Неизвестная ошибка'
            print(f"yt-dlp error: {error_msg}")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return jsonify({'error': f'Ошибка при скачивании: {error_msg[-300:]}'}), 500

        # Ищем скачанный файл
        files = os.listdir(temp_dir)
        video_files = [f for f in files if f.endswith(('.mp4', '.mkv', '.webm'))]

        if not video_files:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return jsonify({'error': 'Файл не найден после скачивания'}), 500

        filepath = os.path.join(temp_dir, video_files[0])

        response = send_file(
            filepath,
            as_attachment=True,
            download_name=video_files[0],
            mimetype='video/mp4'
        )

        # Автоматическая очистка после отправки
        @response.call_on_close
        def cleanup():
            shutil.rmtree(temp_dir, ignore_errors=True)

        return response

    except subprocess.TimeoutExpired:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({'error': 'Таймаут (5 минут). Видео слишком большое.'}), 504
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({'error': f'Внутренняя ошибка: {str(e)}'}), 500

@app.route('/')
def index():
    return jsonify({'status': 'ok', 'message': 'YouTube Downloader API'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

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

    unique_id = str(uuid.uuid4())
    temp_dir = tempfile.mkdtemp(prefix='ytdl_')

    output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')

    command = [
        sys.executable, '-m', 'yt_dlp',
        '-f', 'best[height<=720]',
        '-o', output_template,
        '--no-playlist',
        '--merge-output-format', 'mp4',
        '--no-warnings',
        url
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip() or 'Неизвестная ошибка'
            print(f"yt-dlp error: {error_msg}")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return jsonify({'error': f'Ошибка: {error_msg[-300:]}'}), 500

        # Ищем любой скачанный файл
        files = os.listdir(temp_dir)
        video_files = [f for f in files if f.endswith(('.mp4', '.mkv', '.webm', '.avi'))]

        if not video_files:
            audio_files = [f for f in files if f.endswith(('.mp3', '.m4a', '.opus', '.aac'))]
            shutil.rmtree(temp_dir, ignore_errors=True)
            if audio_files:
                return jsonify({'error': 'Найдено только аудио. Видео недоступно.'}), 404
            return jsonify({'error': 'Файл не найден после скачивания'}), 500

        filepath = os.path.join(temp_dir, video_files[0])

        response = send_file(
            filepath,
            as_attachment=True,
            download_name=video_files[0],
            mimetype='video/mp4'
        )

        # Чистим после отправки — без call_on_close которого нет в новых Flask
        response.headers['X-Cleanup-Path'] = temp_dir  # метка на всякий

        return response

    except subprocess.TimeoutExpired:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({'error': 'Таймаут (5 минут). Видео слишком большое для бесплатного тарифа.'}), 504

    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({'error': f'Сбой сервера: {str(e)}'}), 500

    finally:
        # Дополнительная страховка — чистим если response не отправился
        if 'response' not in locals() and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

@app.route('/')
def index():
    return jsonify({
        'status': 'ok',
        'yt-dlp_version': 'latest',
        'python_version': sys.version.split()[0]
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

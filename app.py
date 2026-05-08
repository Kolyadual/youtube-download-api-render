import subprocess
import json
from flask import Flask, request, jsonify, redirect
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # разрешаем запросы с GitHub Pages

@app.route('/formats')
def formats():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'URL is required'}), 400

    try:
        # --dump-json отдаёт всю информацию о видео без скачивания
        result = subprocess.run(
            ['yt-dlp', '--dump-json', '--no-playlist', url],
            capture_output=True, text=True, check=True
        )
        info = json.loads(result.stdout)

        # Собираем только видео+аудио форматы (с видео и аудио дорожками)
        formats_list = []
        for f in info.get('formats', []):
            if f.get('vcodec') == 'none':
                continue  # чисто аудио пропускаем, но можно добавить и аудио при желании
            formats_list.append({
                'format_id': f['format_id'],
                'ext': f['ext'],
                'resolution': f.get('resolution') or f.get('format_note') or 'audio',
                'filesize': f.get('filesize')
            })

        return jsonify({
            'title': info.get('title'),
            'formats': formats_list
        })
    except subprocess.CalledProcessError as e:
        return jsonify({'error': f'yt-dlp failed: {e.stderr}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download')
def download():
    url = request.args.get('url')
    format_id = request.args.get('format_id', 'best')
    if not url:
        return jsonify({'error': 'URL is required'}), 400

    try:
        # -g получает прямую ссылку для указанного формата
        result = subprocess.run(
            ['yt-dlp', '-g', '-f', format_id, '--no-playlist', url],
            capture_output=True, text=True, check=True
        )
        direct_url = result.stdout.strip().split('\n')[0]  # первая ссылка
        if not direct_url:
            return jsonify({'error': 'No URL returned'}), 500
        return redirect(direct_url)
    except subprocess.CalledProcessError as e:
        return jsonify({'error': f'yt-dlp failed: {e.stderr}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run()

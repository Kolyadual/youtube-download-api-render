import os
import io
import shutil
import subprocess
import uuid
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp

app = FastAPI(title="Open Video Downloader API")

# Разрешаем доступ нашему фронтенду на GitHub Pages
origins = os.getenv("ALLOWED_ORIGIN", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origins],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "API is running"}

@app.get("/download")
async def download_video(url: str = Query(..., description="YouTube video URL")):
    """
    Скачивает видео по ссылке и отдаёт готовый MP4-файл.
    """
    # Проверка корректности URL (базовая)
    if "youtube.com/watch" not in url and "youtu.be/" not in url:
        raise HTTPException(status_code=400, detail="Некорректная ссылка на YouTube")

    # Уникальный идентификатор для временных файлов (если бы мы их сохраняли)
    unique_id = str(uuid.uuid4())[:8]

    # Настройки yt-dlp: скачиваем видео и аудио по отдельности, но не сливаем,
    # потому что слияние будем делать сами через ffmpeg в потоке
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': f'/tmp/{unique_id}_%(format_id)s.%(ext)s',  # сохраняем во временную папку Render
        'quiet': True,
        'no_warnings': True,
        # Не склеиваем автоматически — нам нужны отдельные файлы для потоковой передачи
        'merge_output_format': None,
    }

    # Загружаем с помощью yt-dlp
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get('title', 'video')
        # Ищем пути к скачанным файлам видео и аудио
        video_path = None
        audio_path = None
        for fmt in info.get('requested_formats', []):
            if fmt.get('vcodec') != 'none':
                video_path = ydl.prepare_filename(fmt)
            if fmt.get('acodec') != 'none':
                audio_path = ydl.prepare_filename(fmt)

        # Если формат одиночный (уже со звуком), просто читаем файл и отдаём
        if video_path and audio_path is None:
            # Одиночный файл, отдаём как есть
            with open(video_path, 'rb') as f:
                single_file_data = f.read()
            # Удаляем временный файл
            os.remove(video_path)
            return StreamingResponse(
                io.BytesIO(single_file_data),
                media_type='video/mp4',
                headers={'Content-Disposition': f'attachment; filename="{title}.mp4"'}
            )

        # Если не нашлись пути (что редко, но может быть)
        if not video_path or not audio_path:
            raise HTTPException(status_code=500, detail="Не удалось извлечь видео и аудио потоки")

        # Запускаем ffmpeg для склейки и отправки результата в реальном времени
        def generate():
            # Команда: ffmpeg -i video -i audio -c:v copy -c:a aac -f mp4 pipe:1
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-i', audio_path,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-f', 'mp4',
                '-movflags', 'frag_keyframe+empty_moov',  # для стриминга
                'pipe:1'
            ]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                for chunk in iter(lambda: proc.stdout.read(8192), b''):
                    yield chunk
                proc.wait()
                if proc.returncode != 0:
                    raise Exception("ffmpeg error")
            finally:
                # Очистка временных файлов
                os.remove(video_path)
                os.remove(audio_path)

        return StreamingResponse(
            generate(),
            media_type='video/mp4',
            headers={'Content-Disposition': f'attachment; filename="{title}.mp4"'}
        )

# Точка входа для Render: uvicorn запускает app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

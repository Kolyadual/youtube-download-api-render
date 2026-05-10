import os
import tempfile
import uuid
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp

app = FastAPI(title="Open Video Downloader API")

# Разрешаем твоему фронтенду на GitHub Pages обращаться к API
origins = os.getenv("ALLOWED_ORIGIN", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origins],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "API is running. Use /download?url=..."}

@app.get("/download")
async def download_video(url: str = Query(..., description="YouTube video URL")):
    # Базовая проверка ссылки
    if not any(domain in url for domain in ("youtube.com/watch", "youtu.be/")):
        raise HTTPException(status_code=400, detail="Некорректная ссылка на YouTube")

    # Создаём временную папку для загрузки
    with tempfile.TemporaryDirectory() as tmpdir:
        unique_id = str(uuid.uuid4())[:8]
        outtmpl = os.path.join(tmpdir, f"{unique_id}_%(title)s.%(ext)s")

        ydl_opts = {
            # Выбираем лучший MP4, где видео и аудио уже объединены (до 720p/1080p)
            'format': 'best[ext=mp4]/best',
            'outtmpl': outtmpl,
            'quiet': True,
            'no_warnings': True,
            # На случай возрастных ограничений можно добавить cookies, но пока без них
            # 'cookiefile': 'cookies.txt'
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get('title', 'video')

                # Найдём скачанный файл (один, без аудио-разрывов)
                downloaded_file = ydl.prepare_filename(info)
                # Если такого файла нет, значит расширение было изменено
                if not os.path.exists(downloaded_file):
                    # Попробуем найти любой mp4 в папке
                    for f in os.listdir(tmpdir):
                        if f.endswith('.mp4'):
                            downloaded_file = os.path.join(tmpdir, f)
                            break
                    else:
                        raise Exception("Скачанный файл не найден")

                # Отдаём файл и автоматически удаляем после ответа
                return FileResponse(
                    downloaded_file,
                    media_type='video/mp4',
                    headers={'Content-Disposition': f'attachment; filename="{title}.mp4"'}
                )

        except yt_dlp.utils.DownloadError as e:
            raise HTTPException(status_code=500, detail=f"Ошибка загрузки: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")

# Команда запуска остаётся: uvicorn app:app --host 0.0.0.0 --port $PORT
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

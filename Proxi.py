from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import httpx
import Db as db
import os
import logging
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

app = FastAPI()
@app.get("/download/{song_token}")

async def download_song(song_token):
    path = db.get_song_path(song_token)
    if path is None:
        log.error("Song url not found")
        raise HTTPException(status_code=404)
    headers = {
        'Referer': os.getenv("REFERER"),
        'User-Agent': os.getenv('USER_AGENT')
    }
    return StreamingResponse(generator(path, headers), media_type='audio/mpeg')


async def generator(path, headers):
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", path, headers=headers) as response:
                async for chunk in response.aiter_bytes():
                    yield chunk
    except httpx.HTTPError as e:
        log.error(f"HTTP error: {e}")
        raise e

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
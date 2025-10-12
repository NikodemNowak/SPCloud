import os

import aiofiles
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse

app = FastAPI()


@app.get("/")
async def root():
    return {"status": "ok", "message": "Hello World"}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...), logical_name: str = Form(None)):
    file_path = os.path.join('/app/files', logical_name or file.filename)
    async with aiofiles.open(file_path, 'wb') as out_file:
        while content := await file.read(1024 * 1024):  # czytamy w kawałkach 1MB
            await out_file.write(content)
    response = {"filename": file.filename, "content_type": file.content_type, "file_path": file_path}
    return response

@app.get("/download/{file_name}")
async def download_file(file_name: str):
    file_path = os.path.join('/app/files', file_name)
    if not os.path.exists(file_path):
        responseError = {'error': 'File not found'}
        return responseError

    return FileResponse(file_path, media_type="application/octet-stream", filename=file_name)

@app.get("/files")
async def list_files():
    files = os.listdir('/app/files')
    return {"files": files}

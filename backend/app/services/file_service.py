import os
from typing import List, Optional

import aiofiles
from fastapi import UploadFile


class FileService:
    """Service to handle file operations like saving and retrieving files."""

    def __init__(self, storage_path: str = '/app/files'):
        self.storage_path = storage_path
        os.makedirs(storage_path, exist_ok=True)

    async def save_file(self, file: UploadFile, logical_name: Optional[str] = None) -> dict:
        """
        Saves a file to disk

        Args:
            file: File to save
            logical_name: Optional logical name for the file

        Returns:
            Dictionary with information about the saved file
        """
        filename = logical_name or file.filename
        file_path = os.path.join(self.storage_path, filename)

        async with aiofiles.open(file_path, 'wb') as out_file:
            while content := await file.read(1024 * 1024):
                await out_file.write(content)

        return {
            "filename": file.filename,
            "logical_name": filename,
            "content_type": file.content_type,
            "file_path": file_path,
            "size": os.path.getsize(file_path)
        }

    def get_file_path(self, file_name: str) -> str:
        return os.path.join(self.storage_path, file_name)

    def file_exists(self, file_name: str) -> bool:
        return os.path.exists(self.get_file_path(file_name))

    def list_files(self) -> List[str]:
        return os.listdir(self.storage_path)

    def get_file_info(self, file_name: str) -> Optional[dict]:
        file_path = self.get_file_path(file_name)
        if not os.path.exists(file_path):
            return None

        return {
            "filename": file_name,
            "size": os.path.getsize(file_path),
            "path": file_path
        }

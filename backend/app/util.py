from uuid import UUID

from fastapi import HTTPException, status


def _str_to_uuid(id_str: str) -> UUID:
    try:
        return UUID(id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid UUID format"
        )

from pydantic import BaseModel


class TOTPVerifyRequest(BaseModel):
    code: str


class TOTPSetupToken(BaseModel):
    setup_token: str
    token_type: str
    expires_in: int

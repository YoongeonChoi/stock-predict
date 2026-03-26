from pydantic import BaseModel


class AccountProfile(BaseModel):
    user_id: str
    email: str | None = None
    username: str | None = None
    full_name: str | None = None
    phone_number: str | None = None
    phone_masked: str | None = None
    birth_date: str | None = None


class UsernameAvailabilityResponse(BaseModel):
    username: str
    normalized_username: str
    valid: bool
    available: bool
    message: str

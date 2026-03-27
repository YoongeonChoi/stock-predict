from pydantic import BaseModel


class AccountProfile(BaseModel):
    user_id: str
    email: str | None = None
    email_verified: bool = False
    email_confirmed_at: str | None = None
    username: str | None = None
    full_name: str | None = None
    phone_number: str | None = None
    phone_masked: str | None = None
    birth_date: str | None = None


class AccountProfileUpdateRequest(BaseModel):
    username: str
    full_name: str
    phone_number: str
    birth_date: str


class SignUpValidationRequest(BaseModel):
    username: str
    email: str
    full_name: str
    phone_number: str
    birth_date: str
    password: str
    password_confirm: str


class SignUpValidationResponse(BaseModel):
    email: str
    normalized_username: str
    normalized_full_name: str
    normalized_phone_number: str
    birth_date: str
    ready: bool = True
    message: str = "회원가입 조건이 확인되었습니다."


class UsernameAvailabilityResponse(BaseModel):
    username: str
    normalized_username: str
    valid: bool
    available: bool
    message: str

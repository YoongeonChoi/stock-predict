from pydantic import BaseModel


class ContactSubmissionRequest(BaseModel):
    name: str = ""
    email: str = ""
    subject: str = ""
    message: str = ""
    company: str = ""


class ContactSubmissionResponse(BaseModel):
    ok: bool = True
    message: str = "문의가 정상적으로 접수되었습니다."

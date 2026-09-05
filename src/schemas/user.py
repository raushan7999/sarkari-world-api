from pydantic import BaseModel, EmailStr


class UserRead(BaseModel):
    id: int
    email: EmailStr
    is_admin: bool = False

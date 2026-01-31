from enum import Enum
from pydantic import BaseModel


class AuthType(str, Enum):
    NONE = "none"
    API_KEY = "api_key"
    BEARER = "bearer"


class ToolDefinition(BaseModel):
    id: str
    name: str
    description: str = ""
    base_url: str
    method: str = "GET"
    path: str = ""
    auth_type: AuthType = AuthType.NONE
    auth_header: str = ""
    parameters: list[str] = []

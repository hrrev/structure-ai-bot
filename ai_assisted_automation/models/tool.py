from enum import Enum
from typing import Any

from pydantic import BaseModel


class AuthType(str, Enum):
    NONE = "none"
    API_KEY = "api_key"
    BEARER = "bearer"
    BASIC = "basic"


class AuthConfig(BaseModel):
    type: AuthType = AuthType.NONE
    header: str | None = None  # custom header name for api_key
    username_key: str | None = None  # tool_config key for basic auth username


class RequestConfig(BaseModel):
    path_params: list[str] = []
    query_params: list[str] = []
    headers: dict[str, str] = {}
    body: dict[str, Any] | None = None
    content_type: str = "application/json"


class ResponseExtractConfig(BaseModel):
    fields: dict[str, str] = {}  # output_key -> dot-path into response
    strict: bool = True


class ToolDefinition(BaseModel):
    id: str
    name: str
    description: str = ""
    base_url: str
    method: str = "GET"
    path: str = ""
    # Legacy auth fields (kept for backward compat)
    auth_type: AuthType = AuthType.NONE
    auth_header: str = ""
    parameters: list[str] = []
    # New optional configs
    auth: AuthConfig | None = None
    request: RequestConfig | None = None
    response_extract: ResponseExtractConfig | None = None

    def get_auth_config(self) -> AuthConfig:
        """Return auth config, falling back to legacy fields."""
        if self.auth is not None:
            return self.auth
        return AuthConfig(type=self.auth_type, header=self.auth_header or None)

from pydantic import BaseModel


class QueryRequest(BaseModel):
    query: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"query": "What is the P&L for Building A in 2024?"},
                {"query": "Compare all properties by NOI"},
                {"query": "Which property had the highest OER in 2025?"},
            ]
        }
    }


class QueryResponse(BaseModel):
    answer: str
    blocked: bool = False
    block_reason: str | None = None


class ErrorResponse(BaseModel):
    detail: str
    error_type: str

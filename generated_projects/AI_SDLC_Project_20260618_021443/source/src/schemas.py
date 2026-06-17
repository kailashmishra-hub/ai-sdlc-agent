from pydantic import BaseModel

class Record(BaseModel):
    name: str
    description: str | None = None

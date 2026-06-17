from fastapi import FastAPI
from src.schemas import Record
from src.service import RecordService

app = FastAPI(title="Generated AI SDLC API")
service = RecordService()

@app.get("/api/records")
def list_records():
    return service.list_records()

@app.post("/api/records")
def create_record(record: Record):
    return service.create_record(record)

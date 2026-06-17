from src.repository import RecordRepository
from src.schemas import Record

class RecordService:
    def __init__(self):
        self.repository = RecordRepository()

    def list_records(self):
        return self.repository.list_records()

    def create_record(self, record: Record):
        return self.repository.create_record(record)

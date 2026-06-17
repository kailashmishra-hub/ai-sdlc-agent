class RecordRepository:
    def __init__(self):
        self.records = []

    def list_records(self):
        return self.records

    def create_record(self, record):
        payload = record.model_dump()
        self.records.append(payload)
        return {"status": "created", "record": payload}

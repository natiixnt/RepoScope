class DBClient:
    def query(self, sql: str) -> list[dict[str, str]]:
        return [{"sql": sql}]

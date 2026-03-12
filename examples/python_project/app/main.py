from fastapi import FastAPI

from app.auth.service import AuthService
from infra.logging import get_logger

app = FastAPI()
auth = AuthService()
logger = get_logger()


@app.get("/health")
def healthcheck() -> dict[str, str]:
    logger.info("healthcheck")
    return {"status": "ok"}


if __name__ == "__main__":
    print("run via uvicorn")

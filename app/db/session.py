from sqlmodel import create_engine, Session
from dotenv import load_dotenv
import os
from typing import Generator

load_dotenv(dotenv_path='.env')

DATABASE_URL = f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

engine = create_engine(DATABASE_URL)

def session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session













from sqlmodel import SQLModel, create_engine, Session

# SQLite database URL (file-based)
DATABASE_URL = "sqlite:///./app.db"

# Create engine
engine = create_engine(DATABASE_URL, echo=True, connect_args={"check_same_thread": False})

def get_db():
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()

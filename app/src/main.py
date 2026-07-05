import logging
import os

import sys
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator

from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_env_variable(var_name):
    try:
        return os.environ[var_name]
    except KeyError:
        logging.error(f"La variable de entorno '{var_name}' no está definida.")
        sys.exit(1)


DATABASE_URL = get_env_variable('DATABASE_URL')

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

class UserDB(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), index=True)
    email = Column(String(100), unique=True, index=True)
    age = Column(Integer, nullable=True)

Base.metadata.create_all(bind=engine)

# --- Pydantic model ---
class User(BaseModel):
    username: str = Field(..., min_length=3, description="Nombre de usuario (mínimo 3 caracteres)")
    email: str = Field(..., description="Email del usuario")
    age: Optional[int] = Field(None, ge=0, description="Edad no negativa (opcional)")

    @field_validator("username")
    def username_with_values(cls, value):
        if not any(vowel in value for vowel in ["a", "e", "i", "o", "u"]):
            raise ValueError("You need vowels in your username!")
        return value

    @model_validator(mode="after")
    def long_username_if_age_ge_50(cls, instance):
        if instance.age is not None and instance.age >= 50:
            if len(instance.username) < 20:
                raise ValueError("You must provide a username longer than 20 chars")
        return instance

# --- FastAPI setup ---
app = FastAPI(
    title="Mi primera API con FastAPI",
    description="Una API de ejemplo con base de datos SQLite.",
    version="1.0.0"
)

@app.get("/hello")
def initial_greeting():
    logger.info("Recibida petición al saludo genérico")
    return {"msg": "Hola mundo!!!"}

@app.get("/hello/{name}")
def custom_greeting(name: str):
    logger.info(f"Recibida petición al saludo personalizado para {name}")
    processed_name = name.capitalize()
    if processed_name == "Pepe":
        logger.warning("Pepe ha entrado a la web!!")
    return {"msg": f"Hello, {processed_name}!!!"}

@app.post("/users")
def create_user(user: User):
    logger.info(f"📥 Registro de usuario recibido: {user}")
    
    db = SessionLocal()
    existing = db.query(UserDB).filter(UserDB.email == user.email).first()
    if existing:
        db.close()
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    user_db = UserDB(username=user.username, email=user.email, age=user.age)
    db.add(user_db)
    db.commit()
    db.refresh(user_db)
    db.close()

    logger.info(f"✅ Usuario guardado en DB: {user_db.username}")
    return {
        "msg": "Usuario registrado correctamente",
        "usuario": {
            "id": user_db.id,
            "username": user_db.username,
            "email": user_db.email,
            "age": user_db.age
        }
    }

@app.get("/users/{user_id}")
def get_user_by_id(user_id: int):
    db = SessionLocal()
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    db.close()

    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "age": user.age
    }

@app.delete("/users/{user_id}")
def delete_user_by_id(user_id: int):
    db = SessionLocal()
    user = db.query(UserDB).filter(UserDB.id == user_id).first()

    if not user:
        db.close()
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    db.delete(user)
    db.commit()
    db.close()

    logger.info(f"🗑️ Usuario con ID {user_id} eliminado.")
    return {"msg": f"Usuario con ID {user_id} eliminado correctamente"}
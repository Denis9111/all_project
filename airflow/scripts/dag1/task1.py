from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import create_engine, Column, String, Integer, TIMESTAMP, VARCHAR
from sqlalchemy.orm import declarative_base, sessionmaker

import sys
sys.path.append("..")

SQLALCHEMY_DATABASE_URI = f'postgresql://den:0000@45.82.153.168/mydb'

engine = create_engine(SQLALCHEMY_DATABASE_URI)

Base = declarative_base()

# Создаем класс для сессий(фабрика). это нужно для взаимодействия с бд
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
session = Session()

class User(Base):
    __tablename__ = 'users'  # Имя таблицы в БД
    id = Column(Integer, primary_key=True, autoincrement=True,unique=True)
    name = Column(VARCHAR(50),nullable=False)
    current_dt = Column(TIMESTAMP, nullable=False)

Base.metadata.create_all(engine)

alice = User(
    name="Alice",
    current_dt=datetime.now()
)
den = User(
    name="den",
    current_dt=datetime.now()
)

session.add(alice)
session.add(den)
session.commit()

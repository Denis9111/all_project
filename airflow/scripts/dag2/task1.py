import datetime as datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, VARCHAR, Date, Boolean, Float, TIMESTAMP
from sqlalchemy.orm import declarative_base
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--date", dest="date")
parser.add_argument("--host", dest="host")
parser.add_argument("--dbname", dest="dbname")
parser.add_argument("--user", dest="user")
parser.add_argument("--jdbc_password", dest="jdbc_password")
parser.add_argument("--port", dest="port")
args = parser.parse_args()

print('date = ' + str(args.date))
print('host = ' + str(args.host))
print('dbname = ' + str(args.dbname))
print('user = ' + str(args.user))
print('jdbc_password = ' + str(args.jdbc_password))
print('port = ' + str(args.port))

v_host = str(args.host)
v_dbname = str(args.dbname)
v_user = str(args.user)
v_password = str(args.jdbc_password)
v_port = str(args.port)

SQLALCHEMY_DATABASE_URI = f'postgresql://{str(v_user)}:{str(v_password)}@{str(v_host)}:{str(v_port)}/{str(v_dbname)}'

print(SQLALCHEMY_DATABASE_URI)

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

alice2 = User(
    name="Alice2",
    current_dt=datetime.datetime.now()
)
den2 = User(
    name="den2",
    current_dt=datetime.datetime.now()
)

session.add(alice2)
session.add(den2)
session.commit()

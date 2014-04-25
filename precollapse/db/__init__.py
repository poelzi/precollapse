from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from sqlalchemy import create_engine


Engine = create_engine('sqlite:///precollapse.db', echo=True)

Base = declarative_base()

def create_session():
    return sessionmaker(bind=Engine)

Session = create_session()

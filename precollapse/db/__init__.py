from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session


Engine = None
xSession, Session, ScopeSession = None, None, None

def configure_engine(url='sqlite:///precollapse.db'):
    global Engine, Base, Session, ScopeSession
    Engine = create_engine(url, echo=False)
    Base.metadata.bind = Engine

Base = declarative_base()

def create_session(expire_on_commit=True):
    global ScopeSession, Session, Engine
    if ScopeSession:
        return ScopeSession()
    ScopeSession = Session = scoped_session(sessionmaker(bind=Engine))
    return ScopeSession(expire_on_commit=expire_on_commit)




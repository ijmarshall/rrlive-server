from sqlalchemy import Column, Integer, String, TIMESTAMP

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    login = Column(String, unique=True, index=True, nullable=False)
    name = Column(String)
    email = Column(String)
    # picture = Column(String)

    def get_display_name(self) -> str:
        return self.name if self.name is not None else self.login

class RevMeta(Base):
    __tablename__ = "revmeta"

    revid = Column(String, primary_key=True, index=True)
    title = Column(String)
    last_updated = Column(String)
    keyword_filter = Column(String)

class LiveSummarySection(Base):
    __tablename__ = "live_abstracts"

    id = Column(Integer, primary_key=True, index=True)
    section = Column(String)
    text = Column(String)
    revid = Column(String)
    last_updated = Column(TIMESTAMP)

class InitScreenRecord(Base):
    __tablename__ = "init_screen"

    id = Column(Integer, primary_key=True, index=True)
    revid = Column(String)
    pmid = Column(String)
    ti = Column(String)
    ab = Column(String)
    decision = Column(String)

class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    login = Column(String(128))
    revid = Column(String(16))
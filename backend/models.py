from sqlalchemy import JSON, ForeignKey, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

class Base(DeclarativeBase):
    pass

class Campaign(Base):
    __tablename__ = "campaigns"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)

class Stream(Base):
    __tablename__ = "streams"
    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"))
    name: Mapped[str]
    # Снимки содержат только связи офферов, включая архив и локальные закрепления.
    published: Mapped[list] = mapped_column(JSON)
    draft: Mapped[list] = mapped_column(JSON)

Session = sessionmaker(create_engine("sqlite:///adrobot.db"), expire_on_commit=False)

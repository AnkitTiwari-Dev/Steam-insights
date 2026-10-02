from sqlalchemy import Column, Integer, String, Float, DateTime, UniqueConstraint
from database import Base
from datetime import datetime, UTC
class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    current_price = Column(Float)
    last_sale_date = Column(DateTime)
    average_gap_days = Column(Float)
    app_id = Column(Integer,unique=True)
    itad_id = Column(String,unique=True,nullable=True)
    last_checked = Column(DateTime)

class SaleEvent(Base):
    __tablename__ = "sale_events"
    id = Column(Integer, primary_key=True)
    regular_price = Column(Float)
    timestamp = Column(DateTime)
    cut = Column(Integer)
    shop_id = Column(Integer)
    app_id = Column(Integer)
    
class Rating(Base):
    __tablename__ = "ratings"
    id = Column(Integer,primary_key=True)
    app_id = Column(Integer,index=True)
    steam_id = Column(String,index=True)
    status = Column(String)
    score = Column(Integer, nullable=True)
    updated_at = Column(DateTime,default=lambda: datetime.now(UTC),onupdate=lambda: datetime.now(UTC))
    __table_args__ = (
        UniqueConstraint("app_id", "steam_id", name="uq_app_steam"),
    )
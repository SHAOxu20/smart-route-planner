from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


class UserHistory(Base):
    __tablename__ = "user_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), index=True)
    query_text = Column(Text)          # 原始输入
    parsed_intent = Column(JSON)       # 解析后的意图结构
    generated_route = Column(JSON)     # 生成的路线方案
    selected_plan = Column(String(8))  # 用户选择的方案 A/B/C
    feedback = Column(Text, default="")# 用户反馈
    created_at = Column(DateTime, default=datetime.utcnow)


class POIRecord(Base):
    __tablename__ = "poi_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    poi_id = Column(String(64), unique=True, index=True)
    name = Column(String(128))
    category = Column(String(64))       # 餐饮/景点/购物/休闲
    address = Column(String(256))
    lng = Column(Float)
    lat = Column(Float)
    avg_price = Column(Float, default=0)
    rating = Column(Float, default=4.0)
    open_time = Column(String(64))      # "10:00-22:00"
    tags = Column(JSON, default=list)   # ["氛围感","适合约会","拍照出片"]
    ugc_summary = Column(Text, default="")
    source = Column(String(32), default="amap")  # amap / xiaohongshu / dianping
    cluster_id = Column(Integer, nullable=True)
    weather_sensitive = Column(String(8), default="")  # indoor/outdoor/both
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

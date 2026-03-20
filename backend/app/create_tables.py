from app.db.database import engine
from models.db_models import Base

Base.metadata.drop_all(bind=engine)

# 创建所有表
Base.metadata.create_all(bind=engine)

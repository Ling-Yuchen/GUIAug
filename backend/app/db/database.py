from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


# database connection url
DATABASE_URL = "mysql+pymysql://root:root@localhost:3306/ui2"

# create database engine
engine = create_engine(DATABASE_URL)

# create database session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# base model, for the creation of ORM model
Base = declarative_base()

def get_db():
    db = SessionLocal()  # 创建一个数据库会话
    try:
        yield db          # 将会话对象提供给调用者（例如 API 的路由处理函数）
    finally:
        db.close()        # 在操作完成后关闭数据库会话，释放资源

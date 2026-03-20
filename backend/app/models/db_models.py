from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from app.db.database import Base


class Script(Base):
    __tablename__ = "scripts"

    script_id = Column(String(255), primary_key=True, index=True)
    script_name = Column(String(255))
    device_id = Column(String(255), index=True)
    app_id = Column(String(255))
    script_folder = Column(String(255))
    timestamp = Column(DateTime, default=datetime.now())
    description = Column(String(2047))
    mutate_ready = Column(Boolean)
    mutate_master = Column(String(255))
    mutating = Column(Boolean)

    operations = relationship("Operation", back_populates="script")


class Operation(Base):
    __tablename__ = "operations"

    op_id = Column(String(255), primary_key=True, index=True)
    script_id = Column(String(255), ForeignKey("scripts.script_id"))
    op_type = Column(String(255))
    op_params = Column(String(2047))
    widget_bbox = Column(String(255))
    widget_desc = Column(String(255))
    op_folder = Column(String(255))
    timestamp = Column(DateTime, default=datetime.now())
    package = Column(String(255))
    activity = Column(String(255))
    intent = Column(String(255))
    mutate_type = Column(String(255))
    mutate_reason = Column(String(255))

    script = relationship("Script", back_populates="operations")
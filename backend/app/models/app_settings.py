"""Application Settings Model"""

from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime, timezone
from app.db import Base


class AppSettings(Base):
    """Table to store application-level settings and counters."""
    
    __tablename__ = "app_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f"<AppSettings(key='{self.key}', value='{self.value}')>"

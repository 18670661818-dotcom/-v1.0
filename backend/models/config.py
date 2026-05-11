"""配置模型"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float
from sqlalchemy.orm import relationship

from core.database import Base


class Config(Base):
    __tablename__ = "configs"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, index=True, nullable=False)
    value = Column(Text, nullable=False)
    value_type = Column(String(20), default="string")  # string, integer, float, boolean, json
    description = Column(String(500))
    category = Column(String(50), index=True)  # 例如：system, alert, camera, inference
    is_public = Column(Boolean, default=False)  # 是否允许普通用户查看
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )

    def get_typed_value(self):
        """根据value_type返回类型化的值"""
        if self.value_type == "integer":
            return int(self.value)
        elif self.value_type == "float":
            return float(self.value)
        elif self.value_type == "boolean":
            return self.value.lower() in ("true", "1", "yes")
        elif self.value_type == "json":
            import json
            return json.loads(self.value)
        else:
            return self.value

    def set_typed_value(self, value):
        """设置类型化的值"""
        if self.value_type == "json":
            import json
            self.value = json.dumps(value)
        else:
            self.value = str(value)
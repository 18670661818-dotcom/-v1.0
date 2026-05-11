"""配置模型测试"""
import pytest
from models.config import Config


def test_create_config(db_session):
    """测试创建配置"""
    config = Config(
        key="test_key",
        value="test_value",
        value_type="string",
        description="测试配置",
        category="test",
        is_public=True,
    )
    db_session.add(config)
    db_session.commit()
    db_session.refresh(config)
    
    assert config.id is not None
    assert config.key == "test_key"
    assert config.value == "test_value"
    assert config.value_type == "string"


def test_config_value_types(db_session):
    """测试配置值类型"""
    # 字符串类型
    string_config = Config(
        key="string_key",
        value="string_value",
        value_type="string",
    )
    db_session.add(string_config)
    db_session.commit()
    db_session.refresh(string_config)
    
    assert string_config.get_typed_value() == "string_value"
    
    # 整数类型
    int_config = Config(
        key="int_key",
        value="123",
        value_type="integer",
    )
    db_session.add(int_config)
    db_session.commit()
    db_session.refresh(int_config)
    
    assert int_config.get_typed_value() == 123
    
    # 浮点数类型
    float_config = Config(
        key="float_key",
        value="3.14",
        value_type="float",
    )
    db_session.add(float_config)
    db_session.commit()
    db_session.refresh(float_config)
    
    assert float_config.get_typed_value() == pytest.approx(3.14)
    
    # 布尔类型
    bool_config = Config(
        key="bool_key",
        value="true",
        value_type="boolean",
    )
    db_session.add(bool_config)
    db_session.commit()
    db_session.refresh(bool_config)
    
    assert bool_config.get_typed_value() is True
    
    # JSON类型
    json_config = Config(
        key="json_key",
        value='{"key": "value"}',
        value_type="json",
    )
    db_session.add(json_config)
    db_session.commit()
    db_session.refresh(json_config)
    
    assert json_config.get_typed_value() == {"key": "value"}


def test_config_set_typed_value(db_session):
    """测试设置类型化值"""
    config = Config(
        key="set_key",
        value="old_value",
        value_type="string",
    )
    db_session.add(config)
    db_session.commit()
    db_session.refresh(config)
    
    # 设置新值
    config.set_typed_value("new_value")
    db_session.commit()
    db_session.refresh(config)
    
    assert config.value == "new_value"
    assert config.get_typed_value() == "new_value"


def test_config_unique_key(db_session):
    """测试配置键唯一性"""
    config1 = Config(
        key="unique_key",
        value="value1",
        value_type="string",
    )
    db_session.add(config1)
    db_session.commit()
    
    config2 = Config(
        key="unique_key",  # 相同的key
        value="value2",
        value_type="string",
    )
    db_session.add(config2)
    
    with pytest.raises(Exception):  # 应该抛出唯一性约束异常
        db_session.commit()


def test_config_default_values(db_session):
    """测试配置默认值"""
    config = Config(
        key="default_key",
        value="default_value",
    )
    db_session.add(config)
    db_session.commit()
    db_session.refresh(config)
    
    assert config.value_type == "string"  # 默认类型
    assert config.is_public is False  # 默认不公开
    assert config.created_at is not None  # 自动设置创建时间
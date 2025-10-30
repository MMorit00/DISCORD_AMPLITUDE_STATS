"""
配置模块
提供应用配置和常量
"""
from .settings import Settings, load_settings
from .constants import *

__all__ = [
    "Settings",
    "load_settings",
]


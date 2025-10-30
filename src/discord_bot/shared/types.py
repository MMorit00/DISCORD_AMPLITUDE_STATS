"""
Bot 层共享类型（避免与 portfolio-report 的 shared/types 冲突）
"""
from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any]

    def to_openai_format(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class ToolCall:
    function_name: str
    arguments: Dict[str, Any]


@dataclass
class TextReply:
    content: str



"""
需求卡片生成器
根据对话历史生成结构化需求卡片
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
import json


class CardGenerator:
    """需求卡片生成器"""
    
    def __init__(self):
        self.card_template = {
            "requirement_id": "",
            "requirement_type": "",
            "style": "",
            "dimensions": "",
            "layering_requirements": "",
            "spine_reserved": "",
            "delivery_time": "",
            "reference_images": [],
            "description": ""
        }
    
    def generate_card(self, conversation_state) -> Dict[str, Any]:
        card = conversation_state.card
        state = conversation_state

        result_card = {
            "requirement_id": card.requirement_id or self._generate_id(),
            "requirement_type": card.requirement_type or "待确认",
            "style": card.style or "待确认",
            "dimensions": card.dimensions or "待确认",
            "layering_requirements": self._format_layering(card.layering_requirements),
            "spine_reserved": self._format_spine(card.spine_reserved),
            "delivery_time": card.delivery_time or "待确认",
            "reference_images": card.reference_images or [],
            "description": card.description or self._generate_description(state),
            "created_at": state.created_at,
            "status": "已完成" if card.is_complete() else "待完善"
        }
        return result_card

    def _generate_id(self) -> str:
        return f"REQ_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def _format_layering(self, layering: str) -> str:
        if not layering:
            return "无特殊要求（使用默认分层规范）"
        return layering

    def _format_spine(self, spine: str) -> str:
        if not spine:
            return "不需要"
        return spine

    def _generate_description(self, state) -> str:
        user_messages = [m["content"] for m in state.messages if m["role"] == "user"]
        if user_messages:
            return user_messages[0][:500] if len(user_messages[0]) > 500 else user_messages[0]
        return "通过多轮对话收集的需求"

    def generate_summary(self, card: Dict[str, Any]) -> str:
        lines = [
            "=" * 40,
            f"📋 需求卡片 #{card['requirement_id']}",
            "=" * 40,
            f"🎨 类型：{card['requirement_type']}",
            f"✨ 风格：{card['style']}",
            f"📐 尺寸：{card['dimensions']}",
            f"📚 分层：{card['layering_requirements']}",
            f"🦴 Spine：{card['spine_reserved']}",
            f"⏰ 交付：{card['delivery_time']}",
            f"📝 描述：{card['description'][:100]}..." if len(card['description']) > 100 else f"📝 描述：{card['description']}",
        ]
        if card.get('reference_images'):
            lines.append(f"🖼️ 参考图：{len(card['reference_images'])}张")
        lines.append("=" * 40)
        lines.append(f"状态：{card['status']}")
        return "\n".join(lines)

    def export_card_json(self, card: Dict[str, Any]) -> str:
        return json.dumps(card, ensure_ascii=False, indent=2)

    def export_card_markdown(self, card: Dict[str, Any]) -> str:
        md = f"""# 美术需求卡片

## 基本信息

| 字段 | 内容 |
|------|------|
| 需求ID | {card['requirement_id']} |
| 类型 | {card['requirement_type']} |
| 风格 | {card['style']} |
| 尺寸 | {card['dimensions']} |
| 创建时间 | {card['created_at']} |
| 状态 | {card['status']} |

## 技术要求

| 字段 | 内容 |
|------|------|
| 分层要求 | {card['layering_requirements']} |
| Spine预留 | {card['spine_reserved']} |
| 交付时间 | {card['delivery_time']} |

## 参考资料

**参考图链接：**
"""
        if card.get('reference_images'):
            for idx, img in enumerate(card['reference_images'], 1):
                md += f"- [{idx}] {img}\n"
        else:
            md += "- 无\n"

        md += f"""
## 需求描述

{card['description']}
"""
        return md

    # 新增：生成纯文本格式的卡片（用于嵌入对话回复）
    def generate_card_text(self, state) -> str:
        """生成纯文本格式的需求卡片，适合直接输出在对话中"""
        card = self.generate_card(state)
        lines = [
            "=" * 40,
            f"📋 需求卡片 #{card['requirement_id']}",
            "=" * 40,
            f"🎨 类型：{card['requirement_type']}",
            f"✨ 风格：{card['style']}",
            f"📐 尺寸：{card['dimensions']}",
            f"📚 分层：{card['layering_requirements']}",
            f"🦴 Spine：{card['spine_reserved']}",
            f"⏰ 交付：{card['delivery_time']}",
            f"📝 描述：{card['description'][:100]}{'...' if len(card['description']) > 100 else ''}",
        ]
        if card.get('reference_images'):
            lines.append(f"🖼️ 参考图：{len(card['reference_images'])}张")
        lines.append("=" * 40)
        lines.append(f"状态：{card['status']}")
        return "\n".join(lines)
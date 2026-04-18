"""
多轮对话管理器
管理对话状态、收集需求字段、生成追问
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import re


@dataclass
class RequirementCard:
    requirement_id: str = ""
    requirement_type: str = ""
    style: str = ""
    dimensions: str = ""
    layering_requirements: str = ""
    spine_reserved: str = ""
    delivery_time: str = ""
    reference_images: List[str] = field(default_factory=list)
    description: str = ""

    def __post_init__(self):
        if self.reference_images is None:
            self.reference_images = []
        elif isinstance(self.reference_images, list):
            self.reference_images = [img for img in self.reference_images if img is not self]
        else:
            self.reference_images = [self.reference_images] if self.reference_images is not self else []
        if self.description is self:
            self.description = ""

    def is_complete(self) -> bool:
        return all([self.requirement_type, self.style, self.dimensions])

    def get_missing_fields(self) -> List[str]:
        missing = []
        if not self.requirement_type:
            missing.append("类型")
        if not self.style:
            missing.append("风格")
        if not self.dimensions:
            missing.append("尺寸")
        return missing

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "requirement_type": self.requirement_type,
            "style": self.style,
            "dimensions": self.dimensions,
            "layering_requirements": self.layering_requirements,
            "spine_reserved": self.spine_reserved,
            "delivery_time": self.delivery_time,
            "reference_images": self.reference_images[:] if isinstance(self.reference_images, list) else [],
            "description": self.description,
        }


@dataclass
class ConversationState:
    session_id: str
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updated_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    card: RequirementCard = field(default_factory=RequirementCard)
    messages: List[Dict[str, str]] = field(default_factory=list)
    stage: str = "start"
    collected_fields: List[str] = field(default_factory=list)
    pending_question: Optional[str] = None
    pending_candidate: Optional[Dict[str, str]] = None
    pending_completion: bool = False

    def add_message(self, role: str, content: str):
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        self.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def mark_field_collected(self, field_name: str):
        if field_name not in self.collected_fields:
            self.collected_fields.append(field_name)


class ConversationManager:
    def __init__(self):
        self.sessions: Dict[str, ConversationState] = {}
        self._id_counter = 0

    def create_session(self, session_id: Optional[str] = None) -> ConversationState:
        if session_id is None:
            self._id_counter += 1
            session_id = f"req_{datetime.now().strftime('%Y%m%d%H%M%S')}_{self._id_counter}"
        state = ConversationState(
            session_id=session_id,
            card=RequirementCard(requirement_id=session_id)
        )
        self.sessions[session_id] = state
        return state

    def get_session(self, session_id: str) -> Optional[ConversationState]:
        return self.sessions.get(session_id)

    def delete_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]

    def update_card_field(self, session_id: str, field: str, value: Any) -> bool:
        state = self.get_session(session_id)
        if not state:
            return False

        field_mapping = {
            "类型": "requirement_type", "类型选择": "requirement_type",
            "风格": "style", "风格选择": "style",
            "尺寸": "dimensions", "尺寸规格": "dimensions",
            "分层要求": "layering_requirements", "分层": "layering_requirements",
            "Spine预留": "spine_reserved", "spine": "spine_reserved",
            "交付时间": "delivery_time", "交付日期": "delivery_time", "时间": "delivery_time",
            "参考图": "reference_images", "参考图链接": "reference_images",
            "描述": "description", "需求描述": "description"
        }

        attr_name = field_mapping.get(field, field)

        if hasattr(state.card, attr_name):
            if value is state.card or value is state:
                print(f"⚠️ 阻止自引用赋值: {field}")
                return False
            if isinstance(value, list):
                value = [v for v in value if v is not state.card and v is not state]

            current = getattr(state.card, attr_name)
            if isinstance(current, list) and isinstance(value, list):
                current.extend(value)
                setattr(state.card, attr_name, list(set(current)))
            else:
                setattr(state.card, attr_name, value)

            state.mark_field_collected(attr_name)
            return True
        return False

    def generate_next_question(self, state: ConversationState) -> str:
        missing = state.card.get_missing_fields()
        if not missing:
            if not state.card.layering_requirements:
                return "请问对分层有特殊要求吗？比如需要PSD分层、特定图层命名规则等？"
            if not state.card.spine_reserved:
                return "是否需要预留Spine动画接口？（如骨骼点、动画帧等）"
            if not state.card.delivery_time:
                return "请确认一下期望的交付时间是什么时候？"
            if not state.card.reference_images:
                return "有参考图可以提供吗？（可以上传图片或提供链接）"
            return "__COMPLETE__"
        priority = ["类型", "风格", "尺寸"]
        for f in priority:
            if f in missing:
                return self._get_question_for_field(f, state)
        return self._get_question_for_field(missing[0], state)

    def _get_question_for_field(self, field: str, state: ConversationState) -> str:
        questions = {
            "类型": "请问这是一个什么类型的美术需求？（角色皮肤/UI图标/关卡元素/推广素材）",
            "风格": "请描述一下期望的风格？（如：甜美、暗黑、赛博、国风、科幻等）",
            "尺寸": "请问需要的尺寸规格是多少？（如：1024x1024、1920x1080等）"
        }
        if field == "类型" and state.card.description:
            return f"根据您的描述'{state.card.description[:50]}...'，这是一个什么类型的美术需求呢？"
        return questions.get(field, f"请提供{field}信息")

    def extract_and_update_fields(self, user_input: str, state: ConversationState) -> Dict[str, Any]:
        updates = {}

        # 类型关键词
        type_keywords = {
            "角色皮肤": ["角色", "皮肤", "立绘", "角色设计", "人设"],
            "UI图标": ["UI", "图标", "icon", "按钮", "界面元素"],
            "关卡元素": ["关卡", "场景", "地图", "背景", "元素"],
            "推广素材": ["推广", "宣传", "海报", "广告", "营销"]
        }
        for tname, keywords in type_keywords.items():
            if any(kw in user_input for kw in keywords):
                updates["类型"] = tname
                break

        # 风格关键词
        style_keywords = {
            "甜美": ["甜美", "可爱", "Q版", "萌系", "清新"],
            "暗黑": ["暗黑", "哥特", "压抑", "阴郁", "dark"],
            "赛博": ["赛博", "cyber", "科技", "机械", "未来"],
            "国风": ["国风", "古风", "武侠", "水墨", "传统"],
            "科幻": ["科幻", "太空", "星际", "飞船", "外星"],
            "写实": ["写实", "写实风格", "真实", "拟真", "逼真", "写实类"]
        }
        for sname, keywords in style_keywords.items():
            if any(kw in user_input for kw in keywords):
                updates["风格"] = sname
                break

        # 尺寸
        size_match = re.search(r'(\d+)\s*[xX×]\s*(\d+)', user_input)
        if size_match:
            updates["尺寸"] = f"{size_match.group(1)}x{size_match.group(2)}"

        # 分层
        if any(kw in user_input for kw in ["分层", "PSD", "图层"]):
            updates["分层要求"] = "需要PSD分层"

        # Spine
        if any(kw in user_input for kw in ["spine", "Spine", "动画", "骨骼"]):
            updates["Spine预留"] = "需要预留Spine动画接口"

        # 时间
        for pat in [r'(\d+)\s*(天|日)', r'(\d+)\s*小时', r'下周', r'月底', r'本周']:
            if re.search(pat, user_input):
                updates["交付时间"] = user_input
                break

        # 描述
        if not state.card.description and len(user_input) > 5:
            updates["描述"] = user_input

        for field, value in updates.items():
            self.update_card_field(state.session_id, field, value)
        return updates
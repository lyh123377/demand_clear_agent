"""
美术需求澄清Agent - Flask主应用
通过多轮对话收集美术需求，生成结构化需求卡片
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import os
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
import json
import re
import uuid
from flask import Flask, render_template, request, jsonify, session
from datetime import datetime

from agent import LLMClient, ConversationManager, RAGEngine, CardGenerator

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'art-requirement-agent-secret-key-2024')

# 初始化组件
conversation_manager = ConversationManager()
card_generator = CardGenerator()
rag_engine = None
llm_client = None


def init_llm():
    global llm_client
    api_key = os.getenv("ZHIPUAI_API_KEY")
    if not api_key:
        print("⚠️ 未设置 ZHIPUAI_API_KEY，LLM 功能将不可用，将降级到规则引擎")
        llm_client = None
    else:
        llm_client = LLMClient(api_key=api_key, model="glm-4-flash")
        print("✅ LLM 客户端初始化成功")


def init_rag():
    global rag_engine
    db_path = os.path.join(os.path.dirname(__file__), "chroma_db")
    rag_engine = RAGEngine(persist_directory=db_path)
    if not rag_engine.load_existing_db():
        print("⚠️ 未找到向量数据库，请先运行 init_kb.py 初始化知识库")
        rag_engine.vectorstore = None


# 系统提示词（优化版）
SYSTEM_PROMPT = """你是一位专业的游戏美术需求澄清助手。你的职责是通过多轮对话，帮助用户明确和结构化他们的美术需求。

【必填字段】类型、风格、尺寸
【选填字段】分层要求、Spine预留、交付时间、参考图

【重要规则】
1. 类型必须是以下之一：角色皮肤、UI图标、关卡元素、推广素材。不要将用户原话作为类型。
2. 每次只问1个最关键的问题，优先问缺失的必填字段。
3. **回复末尾必须附加JSON：{"updates": {"字段名": "值"}}，字段名为中文。**
4. **当用户一次性提供多个属性时（例如“男骑士，暗黑，1024x1024,不分层，预留spine，下周五交付”），你必须将每个属性拆分并填入对应的字段中，而不是将整句话填入一个字段。**
5. 字段映射：
   - “类型”：从“角色/皮肤/UI/图标/关卡/推广/海报”等推断
   - “风格”：从“甜美/暗黑/赛博/国风/科幻/写实/男骑士/女战士”等推断（“男骑士”可能属于角色描述，如果用户没说具体风格风格，可暂时留空或推断为“写实/奇幻”）
   - “尺寸”：匹配数字x数字模式，如1024x1024
   - “分层要求”：包含“分层/PSD/图层”则填“需要PSD分层”，包含“不分层”则填“不需要分层”
   - “Spine预留”：包含“spine/骨骼/动画/预留spine”则填“需要预留Spine动画接口”，包含“不预留”则填“不需要”
   - “交付时间”：提取时间词，如“下周五/3天后/月底”
6. 如果用户提供了描述但没有明确类型，请推断类型并放入updates。

【对话风格】专业、友好、使用中文和emoji，不要输出JSON外的代码块。

示例1：
用户：“男骑士，暗黑，1024x1024,不分层，预留spine，下周五交付”
回复：好的，已记录您的需求。{"updates": {"类型": "角色皮肤", "风格": "暗黑", "尺寸": "1024x1024", "分层要求": "不需要分层", "Spine预留": "需要预留Spine动画接口", "交付时间": "下周五"}}

示例2：
用户：“月卡标识的太阳月亮图标”
回复：好的，已记录类型为UI图标。请问您希望这个图标采用什么风格？{"updates": {"类型": "UI图标", "描述": "月卡标识的太阳月亮图标"}}
"""


def format_candidate_card(candidate: dict, completed_fields: set) -> str:
    """将候选卡片格式化为表格，标注【补全获得】"""
    lines = [
        "### 📋 根据历史案例为您生成的候选需求卡片",
        "",
        "| 字段 | 建议值 |",
        "|------|--------|"
    ]
    for field, value in candidate.items():
        if field in completed_fields:
            marker = "（您已提供）"
        else:
            marker = "**【补全获得】**"
        lines.append(f"| {field} | {value} {marker} |")
    lines.append("")
    lines.append("您可以直接回复“确认”采纳全部，或说出需要修改的字段（例如“风格改成国风”）。")
    return "\n".join(lines)


def auto_complete_missing_fields(state, user_input, rag):
    """智能补全：生成完整候选卡片"""
    user_msg_count = len([m for m in state.messages if m['role'] == 'user'])
    if user_msg_count > 2:
        return None, False

    if not rag or not rag.vectorstore:
        return None, False

    query = user_input
    if state.card.description:
        query = state.card.description + " " + user_input

    cases = rag.search_cases(query, top_k=1, threshold=0.3)
    if not cases:
        return None, False

    extracted = rag.extract_fields_from_case(cases[0]['content'])
    if not extracted:
        return None, False

    # 构建候选卡片
    candidate = {}
    completed_fields = set()

    # 用户已提供的字段优先
    if state.card.requirement_type:
        candidate["类型"] = state.card.requirement_type
        completed_fields.add("类型")
    elif "类型" in extracted:
        candidate["类型"] = extracted["类型"]

    if state.card.style:
        candidate["风格"] = state.card.style
        completed_fields.add("风格")
    elif "风格" in extracted:
        candidate["风格"] = extracted["风格"]

    if state.card.dimensions:
        candidate["尺寸"] = state.card.dimensions
        completed_fields.add("尺寸")
    elif "尺寸" in extracted:
        candidate["尺寸"] = extracted["尺寸"]

    if state.card.layering_requirements:
        candidate["分层要求"] = state.card.layering_requirements
        completed_fields.add("分层要求")
    elif "分层要求" in extracted:
        candidate["分层要求"] = extracted["分层要求"]

    if state.card.spine_reserved:
        candidate["Spine预留"] = state.card.spine_reserved
        completed_fields.add("Spine预留")
    elif "Spine预留" in extracted:
        candidate["Spine预留"] = extracted["Spine预留"]

    if state.card.delivery_time:
        candidate["交付时间"] = state.card.delivery_time
        completed_fields.add("交付时间")
    elif "交付时间" in extracted:
        candidate["交付时间"] = extracted["交付时间"]

    candidate["需求描述"] = user_input
    completed_fields.add("需求描述")

    state.pending_candidate = candidate
    state.pending_completion = True
    return format_candidate_card(candidate, completed_fields), True


def handle_candidate_confirmation(user_input, state, rag):
    """处理用户对候选卡片的确认/修改（使用大模型）"""
    if not state.pending_candidate:
        return None, False

    # 快速确认
    if user_input.strip() in ["确认", "是的", "好的", "采纳", "ok", "就这样", "对"]:
        field_map = {
            "类型": "requirement_type",
            "风格": "style",
            "尺寸": "dimensions",
            "分层要求": "layering_requirements",
            "Spine预留": "spine_reserved",
            "交付时间": "delivery_time",
            "需求描述": "description"
        }
        for field, value in state.pending_candidate.items():
            internal = field_map.get(field)
            if internal:
                conversation_manager.update_card_field(state.session_id, internal, value)
        state.pending_candidate = None
        state.pending_completion = False
        missing = state.card.get_missing_fields()
        if missing:
            next_q = conversation_manager.generate_next_question(state)
            return f"✅ 已采纳所有建议。{next_q}", True
        else:
            return "✅ 已采纳所有建议。所有必填信息已齐全！请点击“生成卡片”按钮。", True

    # 使用 LLM 解析修改指令
    if not llm_client:
        # 降级：清空 pending，让正常对话处理
        state.pending_candidate = None
        state.pending_completion = False
        return None, False

    try:
        from langchain_core.messages import SystemMessage, HumanMessage
        prompt = f"""你是一个解析用户修改指令的助手。用户收到了一个候选需求卡片，现在回复了修改指令。

        候选卡片：{state.pending_candidate}
        用户回复：{user_input}

        **重要**：用户可能在一个回复中包含多个字段的修改，例如“类型改成角色皮肤，风格暗黑，尺寸1024x1024”。你必须将每个修改拆分开，输出对应的字段和新值。

        请输出 JSON 格式：{{"updates": {{"字段名": "新值"}}}}
        字段名必须是：类型、风格、尺寸、分层要求、Spine预留、交付时间、需求描述。

        示例：
        用户回复：“风格改成国风，尺寸改成2048x2048”
        输出：{{"updates": {{"风格": "国风", "尺寸": "2048x2048"}}}}

        如果用户没有明确修改，输出 {{"updates": {{}}}}。

        只输出 JSON，不要有其他文字。"""
        lc_messages = [SystemMessage(content=prompt), HumanMessage(content=user_input)]
        llm_response = llm_client.chat(lc_messages)
        json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            updates = data.get("updates", {})
            if updates:
                field_map = {
                    "类型": "requirement_type",
                    "风格": "style",
                    "尺寸": "dimensions",
                    "分层要求": "layering_requirements",
                    "Spine预留": "spine_reserved",
                    "交付时间": "delivery_time",
                    "需求描述": "description"
                }
                for field, value in updates.items():
                    internal = field_map.get(field)
                    if internal:
                        conversation_manager.update_card_field(state.session_id, internal, value)
                state.pending_candidate = None
                state.pending_completion = False
                missing = state.card.get_missing_fields()
                if missing:
                    next_q = conversation_manager.generate_next_question(state)
                    return f"✅ 已根据您的修改更新。{next_q}", True
                else:
                    return "✅ 已根据您的修改更新。所有必填信息已齐全！请点击“生成卡片”按钮。", True
            else:
                # 没有修改，视为确认
                state.pending_candidate = None
                state.pending_completion = False
                return "好的，已清除补全建议，请继续提供需求。", True
    except Exception as e:
        print(f"解析修改指令失败: {e}")
        state.pending_candidate = None
        state.pending_completion = False
        return None, False


def process_user_input(user_input, state, rag=None):
    """处理用户输入：先补全，再LLM"""
    # 规则提取（基础）
    conversation_manager.extract_and_update_fields(user_input, state)

    # 智能补全：仅在早期且缺失较多时触发
    if not (hasattr(state, 'pending_completion') and state.pending_completion):
        missing_count = len(state.card.get_missing_fields())
        user_msg_count = len([m for m in state.messages if m['role'] == 'user'])
        if missing_count >= 2 or (len(user_input.strip()) < 15 and user_msg_count <= 2):
            completion_msg, has_completion = auto_complete_missing_fields(state, user_input, rag)
            if has_completion:
                return completion_msg, state

    # 正常LLM对话
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    collected_info = f"当前已确认：类型={state.card.requirement_type or '无'}，风格={state.card.style or '无'}，尺寸={state.card.dimensions or '无'}，分层={state.card.layering_requirements or '无'}，Spine={state.card.spine_reserved or '无'}，交付={state.card.delivery_time or '无'}。"
    messages.append({"role": "system", "content": collected_info})

    # RAG上下文
    if rag and rag.vectorstore:
        cases = rag.search_cases(user_input, top_k=2)
        specs = rag.search_specs(user_input, top_k=1)
        rag_text = ""
        if cases:
            rag_text += "相似案例：\n" + "\n".join([c['content'][:200] for c in cases]) + "\n"
        if specs:
            rag_text += "规范参考：\n" + specs[0]['content'][:200] + "\n"
        if rag_text:
            messages.append({"role": "system", "content": f"知识库参考：\n{rag_text}"})

    for msg in state.messages[-8:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_input})

    response = None
    if llm_client:
        try:
            from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
            lc_messages = []
            for m in messages:
                if m["role"] == "system":
                    lc_messages.append(SystemMessage(content=m["content"]))
                elif m["role"] == "user":
                    lc_messages.append(HumanMessage(content=m["content"]))
                elif m["role"] == "assistant":
                    lc_messages.append(AIMessage(content=m["content"]))
            llm_raw = llm_client.chat(lc_messages)

            # 解析JSON更新
            json_match = re.search(r'\{[^{}]*"updates"[^{}]*\{[^{}]*\}\s*\}', llm_raw, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    if "updates" in data:
                        for field, value in data["updates"].items():
                            conversation_manager.update_card_field(state.session_id, field, value)
                    response = llm_raw.replace(json_match.group(), "").strip()
                except json.JSONDecodeError:
                    response = llm_raw
            else:
                response = llm_raw
        except Exception as e:
            print(f"LLM调用失败: {e}")
            response = None

    if not response:
        missing = state.card.get_missing_fields()
        if missing:
            next_q = conversation_manager.generate_next_question(state)
            response = f"📋 已确认：{state.card.requirement_type or '待定'} | {state.card.style or '待定'} | {state.card.dimensions or '待定'}\n\n{next_q}"
        else:
            response = "所有必填信息已收集完毕！请点击“生成卡片”按钮获取结构化需求。"

    # 完成提示
    if not state.card.get_missing_fields() and state.card.layering_requirements and state.card.delivery_time:
        if "生成卡片" not in response:
            response += "\n\n✨ 所有信息已收集完毕！请点击“生成卡片”按钮获取结构化需求。"

    return response, state


@app.route('/')
def index():
    session['session_id'] = str(uuid.uuid4())
    session['initialized'] = False
    return render_template('index.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    user_input = data.get('message', '').strip()
    action = data.get('action', 'continue')

    session_id = session.get('session_id')
    if not session_id:
        session_id = str(uuid.uuid4())
        session['session_id'] = session_id

    state = conversation_manager.get_session(session_id)
    if not state:
        state = conversation_manager.create_session(session_id)

    state.add_message('user', user_input)

    if not session.get('initialized'):
        init_rag()
        session['initialized'] = True

    # 处理生成卡片动作
    if action == 'generate_card' or (state.card.is_complete() and state.card.layering_requirements and state.card.delivery_time):
        card = card_generator.generate_card(state)
        state.stage = 'complete'
        state.add_message('assistant', '好的，已为您生成结构化需求卡片！')
        return jsonify({'success': True, 'type': 'card', 'card': card, 'message': '需求卡片已生成'})

    # 处理待确认的候选卡片
    if hasattr(state, 'pending_completion') and state.pending_completion:
        response, handled = handle_candidate_confirmation(user_input, state, rag_engine)
        if handled:
            state.add_message('assistant', response)
            return jsonify({
                'success': True,
                'type': 'conversation',
                'message': response,
                'state': {
                    'session_id': session_id,
                    'stage': state.stage,
                    'collected_fields': state.collected_fields,
                    'card': state.card.to_dict() if state.card else {}
                }
            })
        else:
            # 处理失败，清除pending
            state.pending_completion = False
            state.pending_candidate = None

    # 正常对话
    if user_input:
        response, state = process_user_input(user_input, state, rag_engine)
        state.add_message('assistant', response)
    else:
        response = """👋 欢迎使用美术需求澄清助手！

我可以帮助您结构化美术需求，减少沟通成本和返工率。

请告诉我您的大致需求，比如：
- "我需要一个角色皮肤"
- "做一套UI图标"
- "设计一个关卡背景"

我会通过几个问题帮您明确关键信息。🎨"""
        state.add_message('assistant', response)

    return jsonify({
        'success': True,
        'type': 'conversation',
        'message': response,
        'state': {
            'session_id': session_id,
            'stage': state.stage,
            'collected_fields': state.collected_fields,
            'card': state.card.to_dict() if state.card else {}
        }
    })


@app.route('/api/card', methods=['GET'])
def get_card():
    session_id = session.get('session_id')
    if not session_id:
        return jsonify({'success': False, 'error': 'No active session'})
    state = conversation_manager.get_session(session_id)
    if not state:
        return jsonify({'success': False, 'error': 'Session not found'})
    card = card_generator.generate_card(state)
    return jsonify({'success': True, 'card': card})


@app.route('/api/reset', methods=['POST'])
def reset():
    session_id = session.get('session_id')
    if session_id:
        conversation_manager.delete_session(session_id)
    session['session_id'] = str(uuid.uuid4())
    return jsonify({'success': True, 'message': '会话已重置', 'session_id': session['session_id']})


@app.route('/api/history', methods=['GET'])
def get_history():
    session_id = session.get('session_id')
    if not session_id:
        return jsonify({'success': False, 'messages': []})
    state = conversation_manager.get_session(session_id)
    if not state:
        return jsonify({'success': False, 'messages': []})
    return jsonify({'success': True, 'messages': state.messages})


# 在 app.py 末尾添加以下路由（位于 if __name__ == '__main__' 之前）

@app.route('/api/update_card', methods=['POST'])
def update_card():
    """前端保存卡片编辑内容"""
    session_id = session.get('session_id')
    if not session_id:
        return jsonify({'success': False, 'error': 'No active session'})

    state = conversation_manager.get_session(session_id)
    if not state:
        return jsonify({'success': False, 'error': 'Session not found'})

    data = request.json
    updates = data.get('updates', {})

    # 字段映射（前端字段名 -> 后端字段名）
    field_mapping = {
        'requirement_type': 'requirement_type',
        'style': 'style',
        'dimensions': 'dimensions',
        'layering_requirements': 'layering_requirements',
        'spine_reserved': 'spine_reserved',
        'delivery_time': 'delivery_time',
        'description': 'description',
        'reference_images': 'reference_images'
    }

    for front_field, value in updates.items():
        backend_field = field_mapping.get(front_field)
        if backend_field and value is not None:
            # 特殊处理参考图：可能是逗号分隔的字符串转成列表
            if backend_field == 'reference_images' and isinstance(value, str):
                # 支持中文逗号、英文逗号、空格分割
                import re
                urls = re.split(r'[，,;\s]+', value)
                value = [url.strip() for url in urls if url.strip()]
            conversation_manager.update_card_field(session_id, backend_field, value)

    # 生成最新的卡片返回
    card = card_generator.generate_card(state)
    return jsonify({'success': True, 'card': card})

if __name__ == '__main__':
    print("=" * 50)
    print("🎨 美术需求澄清Agent 启动中...")
    print("=" * 50)
    print("📍 访问地址: http://127.0.0.1:5000")
    init_llm()
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=True)
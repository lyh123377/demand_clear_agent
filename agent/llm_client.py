"""智谱AI GLM-4-Flash 客户端封装"""
import os
from typing import Optional, List
from langchain_community.chat_models import ChatZhipuAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate

# 默认配置
DEFAULT_MODEL = "glm-4-flash"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_TOP_P = 0.9


class LLMClient:
    """智谱AI大模型客户端"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL):
        """
        初始化LLM客户端
        
        Args:
            api_key: 智谱AI API密钥，默认从环境变量读取
            model: 模型名称，默认glm-4-flash
        """
        self.api_key = api_key or os.getenv("ZHIPUAI_API_KEY")
        if not self.api_key:
            raise ValueError("智谱AI API Key未设置，请设置环境变量 ZHIPUAI_API_KEY")
        
        self.model = model
        self.llm = ChatZhipuAI(
            zhipuai_api_key=self.api_key,
            model=self.model,
            temperature=DEFAULT_TEMPERATURE,
            top_p=DEFAULT_TOP_P
        )
    
    def chat(self, messages: List[BaseMessage]) -> str:
        """
        发送对话请求
        
        Args:
            messages: 消息列表
            
        Returns:
            AI回复内容
        """
        response = self.llm(messages)
        return response.content
    
    def chat_with_prompt(self, system_prompt: str, user_input: str, 
                        conversation_history: Optional[List[BaseMessage]] = None) -> str:
        """
        快捷对话方法
        
        Args:
            system_prompt: 系统提示词
            user_input: 用户输入
            conversation_history: 对话历史
            
        Returns:
            AI回复内容
        """
        messages = [SystemMessage(content=system_prompt)]
        
        if conversation_history:
            messages.extend(conversation_history)
        
        messages.append(HumanMessage(content=user_input))
        
        return self.chat(messages)
    
    def generate_streaming(self, messages: List[BaseMessage]):
        """
        流式生成回复
        
        Args:
            messages: 消息列表
            
        Yields:
            生成的文本片段
        """
        for chunk in self.llm.stream(messages):
            yield chunk.content

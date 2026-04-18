"""
初始化向量知识库
运行此脚本构建RAG所需的向量数据库
"""
import os
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.rag_engine import RAGEngine

def main():
    """初始化向量数据库"""
    print("=" * 50)
    print("🎨 美术需求澄清Agent - 知识库初始化")
    print("=" * 50)
    
    # 获取知识库文件路径
    base_dir = os.path.dirname(os.path.abspath(__file__))
    specs_path = os.path.join(base_dir, "knowledge_base", "specs.json")
    cases_path = os.path.join(base_dir, "knowledge_base", "cases.json")
    issues_path = os.path.join(base_dir, "knowledge_base", "issues.json")
    db_path = os.path.join(base_dir, "chroma_db")
    
    # 检查文件是否存在
    for path, name in [(specs_path, "规范"), (cases_path, "案例"), (issues_path, "问题")]:
        if os.path.exists(path):
            print(f"✅ 找到{name}文件: {path}")
        else:
            print(f"❌ 缺少{name}文件: {path}")
            return
    
    print("\n📦 正在初始化向量数据库...")
    
    # 初始化RAG引擎
    rag = RAGEngine(persist_directory=db_path)
    
    # 加载知识库
    rag.load_knowledge_base(specs_path, cases_path, issues_path)
    
    print("\n✅ 知识库初始化完成!")
    print(f"📁 向量数据库路径: {db_path}")
    
    # 测试检索
    print("\n🧪 测试检索功能...")
    test_results = rag.similarity_search("甜美风格的角色皮肤", top_k=2,threshold=0.3)
    print(f"   测试结果: 找到 {len(test_results)} 条相关内容")

if __name__ == "__main__":
    main()

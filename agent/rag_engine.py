############################################################
# 文件名: rag_engine.py
# 路径: .\agent\rag_engine.py
############################################################

"""
RAG检索引擎 - 支持混合检索（向量+BM25）和重排序
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import os
import json
import re
from typing import List, Dict, Optional, Any
import numpy as np

from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

# BM25
from rank_bm25 import BM25Okapi

# 重排序
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import torch


class RAGEngine:
    """RAG检索引擎（混合检索 + 重排序）"""

    def __init__(self, persist_directory: str = "./chroma_db",
                 embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
                 reranker_model: str = "BAAI/bge-reranker-base"):
        self.persist_directory = persist_directory
        self.embedding_model = embedding_model
        self.reranker_model_name = reranker_model
        self.embeddings = None
        self.vectorstore = None
        self.documents_text = []      # 存储原始文档文本（用于BM25）
        self.documents_metadata = []  # 存储文档元数据
        self.bm25 = None              # BM25索引
        self.reranker_model = None    # 重排序模型
        self.reranker_tokenizer = None

        self._init_embeddings()
        self._init_reranker()

    def extract_fields_from_case(self, case_content: str) -> Dict[str, str]:
        """从案例内容中提取类型、风格、尺寸等字段"""
        import re
        fields = {}
        patterns = {
            "类型": r'类型[：:]\s*([^\n]+)',
            "风格": r'风格[：:]\s*([^\n]+)',
            "尺寸": r'尺寸[：:]\s*([^\n]+)',
            "分层要求": r'分层[：:]\s*([^\n]+)',
            "Spine预留": r'Spine[：:]\s*([^\n]+)',
            "交付时间": r'交付[：:]\s*([^\n]+)',
        }
        for field, pattern in patterns.items():
            match = re.search(pattern, case_content)
            if match:
                value = match.group(1).strip()
                if value and value not in ["无", "未知", "待确认", ""]:
                    fields[field] = value
        return fields

    def _init_embeddings(self):
        """初始化Embedding模型"""
        self.embeddings = HuggingFaceBgeEmbeddings(
            model_name=self.embedding_model,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )

    def _init_reranker(self):
        """初始化重排序模型（Cross-Encoder）"""
        try:
            model_name = self.reranker_model_name
            self.reranker_tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.reranker_model = AutoModelForSequenceClassification.from_pretrained(model_name)
            self.reranker_model.eval()
            print(f"重排序模型加载成功: {model_name}")
        except Exception as e:
            print(f"重排序模型加载失败: {e}，将不使用重排序")
            self.reranker_model = None

    def _tokenize_chinese(self, text: str) -> List[str]:
        """简单中文分词（用于BM25）"""
        # 按单字切分（对于中文，简单按字切分效果尚可）
        return list(text.lower())

    def _build_bm25_index(self):
        """构建BM25索引"""
        if not self.documents_text:
            return
        tokenized_docs = [self._tokenize_chinese(doc) for doc in self.documents_text]
        self.bm25 = BM25Okapi(tokenized_docs)
        print(f"✅ BM25索引构建完成，共 {len(self.documents_text)} 篇文档")

    def add_document(self, content: str, metadata: Dict[str, Any]):
        """添加单个文档到内存（用于BM25）"""
        self.documents_text.append(content)
        self.documents_metadata.append(metadata)

    def load_knowledge_base(self, specs_path: str, cases_path: str, issues_path: str):
        """加载知识库数据"""
        def _load_json_robust(filepath: str):
            if not os.path.exists(filepath):
                return []
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                content = f.read().strip()
                if not content:
                    return []
                try:
                    data = json.loads(content)
                    if isinstance(data, list):
                        return data
                    else:
                        return [data]
                except json.JSONDecodeError:
                    objects = []
                    for line in content.splitlines():
                        line = line.strip()
                        if line:
                            try:
                                obj = json.loads(line)
                                objects.append(obj)
                            except:
                                continue
                    return objects

        documents = []

        # 加载规范
        specs_list = _load_json_robust(specs_path)
        for spec in specs_list:
            doc_content = f"【美术交付规范】{spec.get('title', '')}\n\n类别：{spec.get('category', '')}\n\n内容：{spec.get('content', '')}\n\n示例：{spec.get('examples', '')}"
            metadata = {"type": "spec", "title": spec.get('title', ''), "category": spec.get('category', '')}
            doc = Document(page_content=doc_content, metadata=metadata)
            documents.append(doc)
            self.add_document(doc_content, metadata)

        # 加载案例
        cases_list = _load_json_robust(cases_path)
        for case in cases_list:
            doc_content = f"【历史案例】{case.get('case_id', '')}\n\n需求描述：{case.get('description', '')}\n\n类型：{case.get('type', '')}\n\n风格：{case.get('style', '')}\n\n尺寸：{case.get('dimensions', '')}\n\n是否分层：{case.get('layered', '')}\n\n验收结果：{case.get('result', '')}"
            metadata = {"type": "case", "case_id": case.get('case_id', ''), "style": case.get('style', ''), "category": case.get('type', '')}
            doc = Document(page_content=doc_content, metadata=metadata)
            documents.append(doc)
            self.add_document(doc_content, metadata)

        # 加载返工问题
        issues_list = _load_json_robust(issues_path)
        for issue in issues_list:
            doc_content = f"【常见返工原因】{issue.get('issue', '')}\n\n原因：{issue.get('cause', '')}\n\n解决方案：{issue.get('solution', '')}"
            metadata = {"type": "issue", "issue": issue.get('issue', '')}
            doc = Document(page_content=doc_content, metadata=metadata)
            documents.append(doc)
            self.add_document(doc_content, metadata)

        # 创建向量存储
        if documents:
            self.vectorstore = Chroma.from_documents(
                documents=documents,
                embedding=self.embeddings,
                persist_directory=self.persist_directory
            )
            self.vectorstore.persist()
            print(f"知识库加载完成，共 {len(documents)} 个文档")
            # 构建BM25索引
            self._build_bm25_index()
        else:
            print("警告：知识库为空")

    def _vector_search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """向量检索"""
        if not self.vectorstore:
            return []
        results = self.vectorstore.similarity_search_with_score(query, k=top_k)
        docs = []
        for doc, score in results:
            similarity = 1 - score / 2  # 距离转相似度
            docs.append({
                "content": doc.page_content,
                "metadata": doc.metadata,
                "similarity": similarity,
                "score": similarity
            })
        return docs

    def _bm25_search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """BM25检索"""
        if not self.bm25:
            return []
        tokenized_query = self._tokenize_chinese(query)
        scores = self.bm25.get_scores(tokenized_query)
        # 获取top_k索引
        top_indices = np.argsort(scores)[-top_k:][::-1]
        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append({
                    "content": self.documents_text[idx],
                    "metadata": self.documents_metadata[idx],
                    "bm25_score": float(scores[idx]),
                    "score": float(scores[idx])
                })
        return results

    def _rrf_fusion(self, results_list: List[List[Dict]], k: int = 60) -> List[Dict]:
        """
        RRF (Reciprocal Rank Fusion) 融合多个检索结果列表
        results_list: [vector_results, bm25_results]
        """
        if not results_list or not results_list[0]:
            return []

        # 收集所有文档的唯一标识（用content的前200字符+metadata作为key）
        doc_scores = {}
        for list_idx, results in enumerate(results_list):
            for rank, doc in enumerate(results, start=1):
                # 简单key: content前200字符 + metadata字符串
                key = doc['content'][:200] + str(doc.get('metadata', {}))
                rrf_score = 1 / (k + rank)
                if key not in doc_scores:
                    doc_scores[key] = {'doc': doc, 'score': 0}
                doc_scores[key]['score'] += rrf_score

        # 按融合分数排序
        sorted_items = sorted(doc_scores.values(), key=lambda x: x['score'], reverse=True)
        return [item['doc'] for item in sorted_items]

    def _rerank(self, query: str, docs: List[Dict], top_k: int = 5) -> List[Dict]:
        """使用Cross-Encoder重排序"""
        if not self.reranker_model or not docs:
            return docs[:top_k]

        try:
            pairs = [[query, doc['content']] for doc in docs]
            with torch.no_grad():
                inputs = self.reranker_tokenizer(pairs, padding=True, truncation=True, return_tensors='pt', max_length=512)
                scores = self.reranker_model(**inputs).logits.view(-1,).float()
                scores = torch.sigmoid(scores).numpy()

            # 添加重排序分数
            for i, doc in enumerate(docs):
                doc['rerank_score'] = float(scores[i])

            # 按重排序分数排序
            docs_sorted = sorted(docs, key=lambda x: x.get('rerank_score', 0), reverse=True)
            return docs_sorted[:top_k]
        except Exception as e:
            print(f"重排序失败: {e}")
            return docs[:top_k]

    def hybrid_search(self, query: str, top_k: int = 5, threshold: float = 0.2, use_rerank: bool = True) -> List[Dict[str, Any]]:
        """混合检索，增加调试日志"""
        print(f"[DEBUG] hybrid_search query='{query}', top_k={top_k}, threshold={threshold}")

        # 1. 向量检索
        vector_results = self._vector_search(query, top_k=top_k * 3)
        print(f"[DEBUG] vector_results count: {len(vector_results)}")

        # 2. BM25检索
        bm25_results = self._bm25_search(query, top_k=top_k * 3)
        print(f"[DEBUG] bm25_results count: {len(bm25_results)}")

        # 3. 融合（RRF）
        fused = self._rrf_fusion([vector_results, bm25_results])
        print(f"[DEBUG] fused results count: {len(fused)}")

        # 4. 阈值过滤
        filtered = [doc for doc in fused if doc.get('similarity', 0) >= threshold or doc.get('bm25_score', 0) > 0]
        print(f"[DEBUG] after threshold filter: {len(filtered)}")

        # 5. 重排序（可选）
        if use_rerank and self.reranker_model:
            filtered = self._rerank(query, filtered, top_k=top_k)
            print(f"[DEBUG] after rerank: {len(filtered)}")
        else:
            filtered = filtered[:top_k]

        return filtered

    # 保留原有接口以兼容现有代码
    def similarity_search(self, query: str, top_k: int = 3, threshold: float = 0.2) -> List[Dict[str, Any]]:
        """兼容原有接口：调用混合检索（默认不启用重排序，速度更快）"""
        return self.hybrid_search(query, top_k=top_k, threshold=threshold, use_rerank=False)

    def search_cases(self, query: str, top_k: int = 3, threshold: float = 0.3) -> List[Dict[str, Any]]:
        """搜索相似历史案例，增加调试日志"""
        print(f"[DEBUG] search_cases called with query='{query}', top_k={top_k}, threshold={threshold}")
        results = self.hybrid_search(query, top_k=top_k, threshold=threshold, use_rerank=True)
        print(f"[DEBUG] hybrid_search returned {len(results)} results")
        cases = []
        for doc in results:
            print(f"DEBUG: type={doc['metadata'].get('type')}, content={doc['content'][:50]}")
            cases.append({
                "content": doc['content'],
                "metadata": doc['metadata'],
                "similarity": doc.get('rerank_score', doc.get('similarity', 0))
            })
        print(f"[DEBUG] filtered cases (type=case): {len(cases)}")
        if cases:
            print(f"[DEBUG] best case similarity: {cases[0]['similarity']}")
            print(f"[DEBUG] best case content preview: {cases[0]['content'][:200]}...")
        return cases

    def search_specs(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """搜索相关规范"""
        results = self.hybrid_search(query, top_k=top_k, use_rerank=False)
        specs = []
        for doc in results:
            if doc.get('metadata', {}).get("type") == "spec":
                specs.append({
                    "content": doc['content'],
                    "metadata": doc['metadata']
                })
        return specs

    def search_issues(self, query: str) -> List[Dict[str, Any]]:
        """搜索相关返工问题"""
        results = self.hybrid_search(query, top_k=2, use_rerank=False)
        issues = []
        for doc in results:
            if doc.get('metadata', {}).get("type") == "issue":
                issues.append({
                    "content": doc['content'],
                    "metadata": doc['metadata']
                })
        return issues

    def recommend_cases(self, style: Optional[str] = None, requirement_type: Optional[str] = None, top_k: int = 3) -> List[Dict[str, Any]]:
        """根据风格和类型推荐相似案例"""
        query_parts = []
        if style:
            query_parts.append(style)
        if requirement_type:
            query_parts.append(requirement_type)
        if not query_parts:
            return []
        query = " ".join(query_parts)
        return self.search_cases(query, top_k=top_k)

    def load_existing_db(self):
        """加载已存在的向量数据库"""
        if os.path.exists(self.persist_directory):
            self.vectorstore = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embeddings
            )
            # 重建BM25索引（需要重新加载文档）
            # 由于Chroma不直接提供文档列表，这里先简单处理，后续可优化
            print("✅ 加载现有向量数据库成功")
            return True
        return False
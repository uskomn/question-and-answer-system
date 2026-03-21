from RAG.search_kb import KnowledgeBase


# kb = KnowledgeBase(kb_dir="E:\PycharmProjects\question and answer system\RAG\kb_data")
kb = KnowledgeBase(kb_dir="/home/ubuntu/question-and-answer-system/RAG/kb_data")


print("知识库加载完成")


def search_from_kg(question: str, top_k=5):
    results, _ = kb.search_diverse(question, top_k=top_k)
    return [r["text"] for r in results]
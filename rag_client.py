from rag_system import RAGSearchSystem

def ask_rag(question: str) -> str:
    rag = RAGSearchSystem()
    return rag.search_and_answer(question)
                                                                                                  

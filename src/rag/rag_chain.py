from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from langchain_core.runnables import RunnablePassthrough

from src.config.bedrock import create_llm
from src.models.policy import PolicyAnswer
from src.rag.vectorstore import load_vectorstore


def format_docs(docs) -> str:
    """Format retrieved documents into a context string.

    Each document includes its source metadata for citation.
    This is what gets injected into the prompt.
    """
    formatted = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "unknown")
        page = doc.metadata.get("page", "?")
        section = doc.metadata.get("section", "")
        
        formatted.append(
            f"[Document {i}]\n"
            f"Source: {source}, Page {page}\n"
            f"Section: {section}\n"
            f"Content: {doc.page_content}\n"
        )
    return "\n---\n".join(formatted) if formatted else "No matching policy documents found."


def _build_retriever_runnable(metadata_filter=None, retriever=None):
    if retriever is not None:
        return retriever

    vectorstore = load_vectorstore()
    search_kwargs = {"k": 3}
    if metadata_filter:
        search_kwargs["filter"] = metadata_filter

    return vectorstore.as_retriever(search_kwargs=search_kwargs)


def create_rag_chain(metadata_filter: dict | None = None, retriever=None):
    """
    Create a RAG chain that retrieves docs and reasons over them.
    
    Args:
        metadata_filter: Optional filter for vector search
                        e.g., {"jurisdiction": "state_texas"}
    """
    llm = create_llm(temperature=0)
    retriever_runnable = _build_retriever_runnable(metadata_filter=metadata_filter, retriever=retriever)
    
    # RAG prompt — instructs LLM to use ONLY retrieved context
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a compliance officer reviewing 
mortgage lending regulations.

RULES:
- Answer ONLY based on the provided context documents
- If the context does not contain the answer, say 
  "Insufficient documentation to answer this question"
- ALWAYS cite the source document and page number
- NEVER make up or assume information not in the context
- Be precise and quote specific requirements"""),
        ("human", """CONTEXT DOCUMENTS:
{context}

---

QUESTION: {question}

Provide your answer with source citations."""),
    ])
    
    # The LCEL chain:
    # 1. Retrieve docs (in parallel with passing the question through)
    # 2. Format docs into context string
    # 3. Fill prompt template
    # 4. Send to LLM
    # 5. Parse response
    
    return (
        {
            "context": retriever_runnable | RunnableLambda(format_docs),
            "question": RunnablePassthrough(),
        }
        | prompt
        | llm
        | StrOutputParser()
    )


def create_structured_rag_chain(metadata_filter: dict | None = None, retriever=None):
    """Create a RAG chain that returns a structured PolicyAnswer object.

    Args:
        metadata_filter: Optional FAISS metadata filter for retrieval.
    """
    llm = create_llm(temperature=0)
    retriever_runnable = _build_retriever_runnable(metadata_filter=metadata_filter, retriever=retriever)
    structured_llm = llm.with_structured_output(PolicyAnswer)

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            """You are a mortgage compliance analyst.
Answer ONLY from the provided context documents.
If context is insufficient, set sufficient_context to false.
Always provide citations in sources and include relevant quotes when available.""",
        ),
        (
            "human",
            """CONTEXT DOCUMENTS:
{context}

QUESTION: {question}

Return a structured response.""",
        ),
    ])

    return (
        {
            "context": retriever_runnable | RunnableLambda(format_docs),
            "question": RunnablePassthrough(),
        }
        | prompt
        | structured_llm
    )
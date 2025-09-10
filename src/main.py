import os
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# LangChain components
from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaEmbeddings, ChatOllama # Use modern Ollama classes
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI # Use the standard OpenAI client

# Load environment variables
load_dotenv()

# --- Configuration ---
# Allow overriding index path per service instance (Option A multi-API)
INDEX_DIR = os.getenv("INDEX_DIR")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
LITELLM_API_BASE = os.getenv("LITELLM_API_BASE", "http://litellm:4000")


def _slug_from_embedding(model_name: str) -> str:
    import re as _re
    return _re.sub(r"[^A-Za-z0-9]+", "_", model_name.lower())

# --- Data Models ---
class QueryRequest(BaseModel):
    question: str
    model_name: str = Field(default="ollama/phi3:mini")

class Document(BaseModel):
    page_content: str
    metadata: dict

class QueryResponse(BaseModel):
    answer: str
    source_documents: List[Document]

# --- Global Resources ---
rag_resources = {}

# --- Lifespan Management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("--- RAG API is starting up ---")

    # Derive INDEX_DIR from EMBEDDING_MODEL when not explicitly set
    index_dir = INDEX_DIR
    if not index_dir:
        slug = _slug_from_embedding(EMBEDDING_MODEL_NAME)
        index_dir = f".rag_cache/{slug}/faiss_index"

    print(f"Loading FAISS index from '{index_dir}'...")
    if not os.path.exists(index_dir):
        raise RuntimeError(f"FAISS index not found. Run the index builder first.")

    embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL_NAME, base_url=OLLAMA_BASE_URL)

    vectorstore = FAISS.load_local(
        index_dir,
        embeddings,
        allow_dangerous_deserialization=True
    )
    rag_resources["vectorstore"] = vectorstore
    print("FAISS index loaded successfully.")

    yield

    print("--- RAG API is shutting down ---")
    rag_resources.clear()

# --- FastAPI Application ---
app = FastAPI(title="RAG API", lifespan=lifespan)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/info")
def info():
    return {
        "index_dir": INDEX_DIR,
        "embedding_model": EMBEDDING_MODEL_NAME,
        "ollama_base_url": OLLAMA_BASE_URL,
        "litellm_api_base": LITELLM_API_BASE,
    }

@app.post("/query", response_model=QueryResponse)
async def query_rag_pipeline(request: QueryRequest) -> QueryResponse:
    vectorstore = rag_resources.get("vectorstore")
    if not vectorstore:
        raise HTTPException(status_code=503, detail="Vector store not available.")

    # Choose local vs cloud path
    if request.model_name.startswith("ollama/"):
        local_model = request.model_name.split("/", 1)[-1]
        llm = ChatOllama(
            model=local_model,
            base_url=OLLAMA_BASE_URL,
            temperature=0,
            timeout=600,
        )
    else:
        # Cloud via LiteLLM (OpenAI-compatible)
        llm = ChatOpenAI(
            model=request.model_name,
            openai_api_base=LITELLM_API_BASE,
            openai_api_key="anything", # LiteLLM doesn't require a key for local models
            request_timeout=600 # 10 minute timeout for large models
        )

    retriever = vectorstore.as_retriever()

    # ---- Problem-solver prompt tailored for handbook-style queries ----
    rag_prompt_template = """You are a helpful UCL Computer Science handbook assistant.
Answer using ONLY the context. If the answer is not in the context, say "I don't know based on the handbook excerpts provided."

Write concise, actionable guidance:
- Start with the direct answer in one short sentence.
- Then list 2–5 clear steps (what to do / who to contact / forms to submit / deadlines).
- If relevant, include warnings/caveats (e.g., evidence required, timing rules).
- End with a one-line source label: "Source: <section or heading>".

STRICT RULES:
- Do not invent emails, links, or policies not shown in context.
- Prefer official terms from the context (e.g., Extenuating Circumstances, SORA).
- Keep total length under ~8 lines.

Context:
{context}

Question: {question}

Helpful, grounded answer:"""

    RAG_PROMPT = PromptTemplate(
        template=rag_prompt_template,
        input_variables=["context", "question"]
    )

    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True,
        chain_type_kwargs={"prompt": RAG_PROMPT}
    )

    result = await qa_chain.ainvoke({"query": request.question})

    return QueryResponse(
        answer=result["result"],
        source_documents=[
            Document(page_content=doc.page_content, metadata=doc.metadata)
            for doc in result["source_documents"]
        ]
    )

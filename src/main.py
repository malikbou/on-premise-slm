import os
import time
import uuid
import json
import httpx
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
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
            model_kwargs={"num_ctx": 8192},
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

# --- OpenAI-compatible API Surface ---

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    stream: Optional[bool] = False


@app.get("/v1/models")
def list_models():
    data = []
    # 1) Discover local Ollama chat models
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5.0)
        if resp.status_code == 200:
            payload = resp.json()
            for m in payload.get("models", []):
                name = m.get("name") or ""
                lowered = name.lower()
                # Heuristic: exclude embedding models to avoid offering non-chat models
                if any(x in lowered for x in ["embedding", "embed", "bge", "e5"]):
                    continue
                data.append({"id": f"ollama/{name}", "object": "model"})
    except Exception:
        # If Ollama is unreachable, ignore silently; cloud models still listed
        pass

    # 2) Add cloud aliases configured in LiteLLM (mirrors config.yaml)
    cloud_models = [
        "gpt-4o-mini",
        "gpt-4o",
        "azure-gpt5",
        "azure-gpt4-1-mini",
        "gemini-2.5-pro",
        "claude-opus-4-1-20250805",
    ]
    data.extend({"id": mid, "object": "model"} for mid in cloud_models)

    return {"object": "list", "data": data}


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest):
    # Extract last user message as the question
    question = next((m.content for m in reversed(req.messages) if m.role == "user"), "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="No user message provided")

    vectorstore = rag_resources.get("vectorstore")
    if not vectorstore:
        raise HTTPException(status_code=503, detail="Vector store not available.")

    retriever = vectorstore.as_retriever()
    docs = await retriever.aget_relevant_documents(question)
    context_text = "\n\n".join(doc.page_content for doc in docs)

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

    prompt = PromptTemplate(template=rag_prompt_template, input_variables=["context", "question"]).format(
        context=context_text,
        question=question,
    )

    # Select LLM
    if req.model.startswith("ollama/"):
        local_model = req.model.split("/", 1)[-1]
        llm = ChatOllama(
            model=local_model,
            base_url=OLLAMA_BASE_URL,
            temperature=0,
            timeout=600,
            model_kwargs={"num_ctx": 8192},
        )
    else:
        llm = ChatOpenAI(
            model=req.model,
            openai_api_base=LITELLM_API_BASE,
            openai_api_key="anything",
            request_timeout=600,
        )

    # Prepare a sources block for non-streaming or finalization
    source_labels: List[str] = []
    for d in docs:
        label = d.metadata.get("section") or d.metadata.get("source") or d.metadata.get("file_path") or "Document"
        if label not in source_labels:
            source_labels.append(label)

    if req.stream:
        async def event_stream():
            created = int(time.time())
            cid = f"chatcmpl-{uuid.uuid4()}"
            # Stream token/content chunks
            async for part in llm.astream(prompt):
                delta = getattr(part, "content", None)
                if delta is None:
                    delta = str(part)
                if not delta:
                    continue
                chunk = {
                    "id": cid,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": req.model,
                    "choices": [
                        {"index": 0, "delta": {"content": delta}, "finish_reason": None}
                    ],
                }
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

            # Append sources before final stop (optional)
            if source_labels:
                sources_text = "\n\nSources:\n" + "\n".join(f"- {s}" for s in source_labels)
                src_chunk = {
                    "id": cid,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": req.model,
                    "choices": [
                        {"index": 0, "delta": {"content": sources_text}, "finish_reason": None}
                    ],
                }
                yield f"data: {json.dumps(src_chunk, ensure_ascii=False)}\n\n"

            # Final stop
            final = {
                "id": cid,
                "object": "chat.completion.chunk",
                "created": created,
                "model": req.model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
            yield f"data: {json.dumps(final, ensure_ascii=False)}\n\n"

            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    # Non-streaming
    result = await llm.ainvoke(prompt)
    content = getattr(result, "content", None) or str(result)
    if source_labels:
        content = f"{content}\n\nSources:\n" + "\n".join(f"- {s}" for s in source_labels)

    return {
        "id": f"chatcmpl-{uuid.uuid4()}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": req.model,
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }

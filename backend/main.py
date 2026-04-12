"""
Arknights RAG Backend - FastAPI Server
Provides REST API for the frontend
"""
import asyncio
import sys
import os
import json
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, Request, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator
import uvicorn

from backend.db import get_db, init_db
from backend.auth import (
    validate_account, validate_username, validate_password,
    hash_password, verify_password, create_jwt, decode_jwt
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("arknights_rag")

# Import RAG components
from backend.rag.orchestrator import RAGOrchestrator, get_orchestrator
from backend.config import (
    BASE_DIR, CHUNKS_DIR, FAISS_INDEX_DIR, DATA_DIR,
    ENTITY_RELATIONS_FILE, SILICONFLOW_API_KEY,
    EMBEDDING_MODEL, RERANKER_MODEL, DEEPSEEK_LLM_MODEL, DEEPSEEK_API_KEY, LLM_MODEL,
)
import backend.config as config

# Import AgenticRAG components
from backend.agent.sessions import SessionManager
from backend.agent.core import agent_loop
from backend.api.llm_factory import get_available_models, DEFAULT_MODEL

# ============== FastAPI App ==============
app = FastAPI(
    title="Arknights RAG API",
    description="Backend API for Arknights RAG System",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await init_db()


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    req_id = id(request)
    
    # Log request
    body_info = ""
    if request.method in ("POST", "PUT", "PATCH"):
        # Read body for logging, but we need to store it for the endpoint
        body = await request.body()
        try:
            body_json = json.loads(body)
            # Truncate long fields for readability
            log_body = {k: (v if len(str(v)) < 200 else str(v)[:200] + "...") for k, v in body_json.items()}
            body_info = f" body={json.dumps(log_body, ensure_ascii=False)}"
        except Exception:
            body_info = f" body_length={len(body)}"
    
    logger.info(f"[REQ #{req_id}] {request.method} {request.url.path}{body_info}")
    
    response = await call_next(request)
    
    elapsed = (time.time() - start) * 1000
    logger.info(f"[RES #{req_id}] {request.method} {request.url.path} -> {response.status_code} ({elapsed:.0f}ms)")
    
    return response

def get_orch() -> RAGOrchestrator:
    return get_orchestrator(
        api_key=str(SILICONFLOW_API_KEY),
        faiss_index_dir=str(FAISS_INDEX_DIR),
        deepseek_api_key=str(DEEPSEEK_API_KEY)
    )


# AgenticRAG Session Manager (singleton)
_session_manager = SessionManager(max_sessions=1000, ttl_seconds=3600)


# ============== Request/Response Models ==============
class QueryRequest(BaseModel):
    question: str
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    use_parent_doc: bool = True
    use_graphrag: bool = True
    use_crag: bool = True
    top_k_per_channel: int = 8
    rerank_top_k: int = 5

    @field_validator('question')
    @classmethod
    def question_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('question cannot be empty')
        return v.strip()

    @field_validator('top_k_per_channel', 'rerank_top_k')
    @classmethod
    def top_k_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f'top_k values must be positive, got {v}')
        if v > 100:
            raise ValueError(f'top_k values must not exceed 100, got {v}')
        return v


# ===== AgenticRAG Request Models =====

class AgentChatRequest(BaseModel):
    """Request for agent chat endpoint."""
    session_id: str
    message: str
    model: Optional[str] = None

    @field_validator('message')
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('message cannot be empty')
        return v.strip()


class QueryResponse(BaseModel):
    answer: str
    crag_level: str
    avg_score: float
    num_docs_used: int
    used_web_search: bool
    retrieved_documents: Optional[List[Dict]] = None
    retrieved_doc_ids: Optional[List[str]] = None  # 用于评估
    graph_results: Optional[Dict] = None
    pipeline_steps: List[Dict] = Field(default_factory=list)
    total_time_ms: float = 0.0


class ChunkInfo(BaseModel):
    filename: str
    name: str
    char_count: int
    lines: int
    tokens: int


class EntityRelationData(BaseModel):
    entities: Dict
    relations: List[Dict]


class StatsResponse(BaseModel):
    operators: int
    stories: int
    knowledge: int
    relations: int


# ============== API Endpoints ==============

@app.get("/api")
async def root():
    return {"message": "Arknights RAG API", "version": "1.0.0"}


@app.get("/health")
async def health():
    """Health check endpoint for Docker."""
    return {"status": "healthy"}


@app.get("/status")
async def status():
    """Get service health status."""
    return {
        "status": "healthy",
        "api_key_configured": bool(SILICONFLOW_API_KEY),
        "embedding_model": config.EMBEDDING_MODEL,
        "reranker_model": config.RERANKER_MODEL,
        "llm_model": LLM_MODEL or "not configured"
    }


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    """Execute RAG query and return answer with metadata"""
    try:
        orch = get_orch()
        result = orch.query(
            question=req.question,
            conversation_history=req.conversation_history,
            use_parent_doc=req.use_parent_doc,
            use_graphrag=req.use_graphrag,
            use_crag=req.use_crag,
            top_k_per_channel=req.top_k_per_channel,
            rerank_top_k=req.rerank_top_k
        )

        return QueryResponse(
            answer=result.answer,
            crag_level=result.crag_level,
            avg_score=result.avg_score,
            num_docs_used=result.num_docs_used,
            used_web_search=result.used_web_search,
            retrieved_documents=result.retrieved_documents,
            retrieved_doc_ids=result.retrieved_doc_ids,
            graph_results=result.graph_results,
            pipeline_steps=result.pipeline_steps,
            total_time_ms=result.total_time_ms
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chunks/{collection}", response_model=List[ChunkInfo])
async def list_chunks(collection: str):
    """List all chunks in a collection"""
    valid_collections = ["operators", "stories", "knowledge"]
    if collection not in valid_collections:
        raise HTTPException(status_code=400, detail=f"Invalid collection. Must be one of: {valid_collections}")

    collection_dir = CHUNKS_DIR / collection
    if not collection_dir.exists():
        raise HTTPException(status_code=404, detail=f"Collection '{collection}' not found")

    chunks = []
    for f in sorted(collection_dir.glob("*.md")) + sorted(collection_dir.glob("*.txt")):
        content = f.read_text(encoding="utf-8")
        char_count = len(content)
        line_count = len(content.split("\n"))
        tokens = int(char_count / 1.5)

        chunks.append(ChunkInfo(
            filename=f.name,
            name=f.stem,
            char_count=char_count,
            lines=line_count,
            tokens=tokens
        ))

    return chunks


@app.get("/chunks/{collection}/{filename}")
async def get_chunk(collection: str, filename: str):
    """Get content of a specific chunk"""
    valid_collections = ["operators", "stories", "knowledge"]
    if collection not in valid_collections:
        raise HTTPException(status_code=400, detail=f"Invalid collection")

    filepath = CHUNKS_DIR / collection / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"File not found")

    content = filepath.read_text(encoding="utf-8")
    return {"filename": filename, "content": content}


@app.get("/knowledge-graph", response_model=EntityRelationData)
async def get_graph():
    """Get entity relations for knowledge graph"""
    if not ENTITY_RELATIONS_FILE.exists():
        return EntityRelationData(entities=[], relations=[])

    with open(ENTITY_RELATIONS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    return EntityRelationData(
        entities=data.get("entities", []),
        relations=data.get("relations", [])
    )


@app.get("/stats", response_model=StatsResponse)
async def get_stats():
    """Get system statistics"""
    stats = {
        "operators": 0,
        "stories": 0,
        "knowledge": 0,
        "relations": 0
    }

    # Count chunks
    for coll in ["operators", "stories", "knowledge"]:
        collection_dir = CHUNKS_DIR / coll
        if collection_dir.exists():
            stats[coll] = len(list(collection_dir.glob("*.md"))) + len(list(collection_dir.glob("*.txt")))

    # Count relations
    if ENTITY_RELATIONS_FILE.exists():
        with open(ENTITY_RELATIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            stats["relations"] = len(data.get("relations", []))

    return StatsResponse(**stats)


# ============== Auth & Conversation Endpoints ==============

class RegisterRequest(BaseModel):
    account: str
    username: str
    password: str

class LoginRequest(BaseModel):
    account: str
    password: str

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class SyncConversationsRequest(BaseModel):
    conversations: list


def get_current_user(authorization: str = Header(None)):
    """Extract current user from JWT token in Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    payload = decode_jwt(token)
    if not payload:
        return None
    return payload


@app.post("/auth/register")
async def register(req: RegisterRequest):
    """Register a new user."""
    err = validate_account(req.account)
    if err:
        raise HTTPException(status_code=400, detail=err)
    err = validate_username(req.username)
    if err:
        raise HTTPException(status_code=400, detail=err)
    err = validate_password(req.password)
    if err:
        raise HTTPException(status_code=400, detail=err)

    db = await get_db()
    try:
        cursor = await db.execute("SELECT id FROM users WHERE account = ?", (req.account,))
        if await cursor.fetchone():
            raise HTTPException(status_code=400, detail="该账号已被注册")

        pw_hash = hash_password(req.password)
        cursor = await db.execute(
            "INSERT INTO users (account, username, password_hash) VALUES (?, ?, ?)",
            (req.account, req.username.strip(), pw_hash)
        )
        await db.commit()
        user_id = cursor.lastrowid

        token = create_jwt(user_id, req.account, req.username.strip(), datetime.now(timezone.utc).isoformat())
        return {"token": token, "user": {"id": user_id, "account": req.account, "username": req.username.strip()}}
    finally:
        await db.close()


@app.post("/auth/login")
async def login(req: LoginRequest):
    """Login with account + password."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT id, account, username, password_hash, password_changed_at FROM users WHERE account = ?", (req.account,))
        row = await cursor.fetchone()
        if not row or not verify_password(req.password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="账号或密码错误")

        token = create_jwt(row["id"], row["account"], row["username"], row["password_changed_at"])
        return {"token": token, "user": {"id": row["id"], "account": row["account"], "username": row["username"]}}
    finally:
        await db.close()


@app.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Get current user info."""
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    return {"user": {"id": user["user_id"], "account": user["account"], "username": user["username"]}}


@app.post("/auth/change-password")
async def change_password(req: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    """Change password. Invalidates JWT after change."""
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    db = await get_db()
    try:
        cursor = await db.execute("SELECT password_hash FROM users WHERE id = ?", (user["user_id"],))
        row = await cursor.fetchone()
        if not row or not verify_password(req.old_password, row["password_hash"]):
            raise HTTPException(status_code=400, detail="旧密码错误")

        err = validate_password(req.new_password)
        if err:
            raise HTTPException(status_code=400, detail=err)

        new_hash = hash_password(req.new_password)
        now = datetime.now(timezone.utc).isoformat()
        await db.execute("UPDATE users SET password_hash = ?, password_changed_at = ? WHERE id = ?", (new_hash, now, user["user_id"]))
        await db.commit()

        token = create_jwt(user["user_id"], user["account"], user["username"], now)
        return {"token": token}
    finally:
        await db.close()


@app.get("/conversations")
async def list_conversations(user: dict = Depends(get_current_user)):
    """List all conversations for the current user."""
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT session_id, name, created_at, updated_at FROM conversations WHERE user_id = ? ORDER BY updated_at DESC",
            (user["user_id"],)
        )
        rows = await cursor.fetchall()
        return {"conversations": [dict(r) for r in rows]}
    finally:
        await db.close()


@app.get("/conversations/{session_id}/messages")
async def get_conversation_messages(session_id: str, user: dict = Depends(get_current_user)):
    """Get all messages for a conversation."""
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    db = await get_db()
    try:
        cursor = await db.execute("SELECT user_id FROM conversations WHERE session_id = ?", (session_id,))
        row = await cursor.fetchone()
        if not row or row["user_id"] != user["user_id"]:
            raise HTTPException(status_code=404, detail="会话不存在")
        cursor = await db.execute(
            "SELECT role, content, metadata, created_at FROM messages WHERE session_id = ? ORDER BY created_at",
            (session_id,)
        )
        messages = [dict(r) for r in await cursor.fetchall()]
        for m in messages:
            try:
                m["metadata"] = json.loads(m["metadata"]) if m["metadata"] else {}
            except Exception:
                m["metadata"] = {}
        return {"messages": messages}
    finally:
        await db.close()


@app.post("/conversations/sync")
async def sync_conversations(req: SyncConversationsRequest, user: dict = Depends(get_current_user)):
    """Sync (upsert) conversations from frontend. Incremental: skip existing messages."""
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    db = await get_db()
    try:
        for conv in req.conversations:
            sid = conv.get("session_id")
            if not sid:
                continue
            cursor = await db.execute("SELECT session_id FROM conversations WHERE session_id = ?", (sid,))
            exists = await cursor.fetchone()
            if not exists:
                await db.execute(
                    "INSERT INTO conversations (session_id, user_id, name, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (sid, user["user_id"], conv.get("name", ""), conv.get("created_at", ""), conv.get("updated_at", ""))
                )
            else:
                await db.execute(
                    "UPDATE conversations SET name = ?, updated_at = ? WHERE session_id = ?",
                    (conv.get("name", ""), conv.get("updated_at", ""), sid)
                )

            for msg in conv.get("messages", []):
                metadata_str = json.dumps(msg.get("metadata", {}), ensure_ascii=False)
                cursor = await db.execute(
                    "SELECT id FROM messages WHERE session_id = ? AND role = ? AND content = ? AND created_at = ?",
                    (sid, msg.get("role", ""), msg.get("content", ""), msg.get("created_at", ""))
                )
                if not await cursor.fetchone():
                    await db.execute(
                        "INSERT INTO messages (session_id, role, content, metadata, created_at) VALUES (?, ?, ?, ?, ?)",
                        (sid, msg.get("role", ""), msg.get("content", ""), metadata_str, msg.get("created_at", ""))
                    )
        await db.commit()
        return {"status": "ok"}
    finally:
        await db.close()


@app.delete("/conversations/{session_id}")
async def delete_conversation(session_id: str, user: dict = Depends(get_current_user)):
    """Delete a conversation and its messages."""
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    db = await get_db()
    try:
        cursor = await db.execute("SELECT user_id FROM conversations WHERE session_id = ?", (session_id,))
        row = await cursor.fetchone()
        if not row or row["user_id"] != user["user_id"]:
            raise HTTPException(status_code=404, detail="会话不存在")
        await db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        await db.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
        await db.commit()
        return {"status": "ok"}
    finally:
        await db.close()


@app.put("/conversations/{session_id}/rename")
async def rename_conversation(session_id: str, name: str = "", user: dict = Depends(get_current_user)):
    """Rename a conversation."""
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    db = await get_db()
    try:
        cursor = await db.execute("SELECT user_id FROM conversations WHERE session_id = ?", (session_id,))
        row = await cursor.fetchone()
        if not row or row["user_id"] != user["user_id"]:
            raise HTTPException(status_code=404, detail="会话不存在")
        await db.execute("UPDATE conversations SET name = ? WHERE session_id = ?", (name, session_id))
        await db.commit()
        return {"status": "ok"}
    finally:
        await db.close()


# ============== AgenticRAG Endpoints ==============

@app.post("/agent/session")
async def create_agent_session():
    """Create a new agent session."""
    session_id = _session_manager.create_session()
    return {"session_id": session_id}


@app.post("/agent/chat")
async def agent_chat(req: AgentChatRequest):
    """Agent chat endpoint with SSE streaming.
    
    If the session_id is invalid or expired, a new session is auto-created.
    """
    session = _session_manager.get_session(req.session_id)
    actual_session_id = req.session_id
    
    if session is None:
        # Session expired or invalid — auto-create a new one
        actual_session_id = _session_manager.create_session()
        logger.warning(f"Session '{req.session_id}' not found/expired, auto-created new session: {actual_session_id}")
    
    model_id = req.model or DEFAULT_MODEL
    logger.info(f"[AGENT CHAT] session={actual_session_id} model={model_id} message={req.message[:100]}")

    return StreamingResponse(
        agent_loop(
            session_id=actual_session_id,
            user_message=req.message,
            session_manager=_session_manager,
            model_id=model_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-New-Session-Id": actual_session_id if actual_session_id != req.session_id else "",
        }
    )


@app.get("/agent/session/{session_id}/messages")
async def get_session_messages(session_id: str):
    """Get session message history."""
    session = _session_manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    return {"messages": session.messages}


@app.delete("/agent/session/{session_id}")
async def delete_agent_session(session_id: str):
    """Delete a session."""
    _session_manager.delete_session(session_id)
    return {"status": "ok"}


@app.get("/agent/debug/trace")
async def get_agent_debug_trace(session_id: str):
    """Get Agent's complete tool call trace for debugging."""
    session = _session_manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    traces = []
    for msg in session.messages:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                fn = tc.get("function", {})
                traces.append({
                    "type": "tool_call",
                    "id": tc.get("id", ""),
                    "name": fn.get("name", ""),
                    "arguments": fn.get("arguments", ""),
                })
        elif msg.get("role") == "tool":
            traces.append({
                "type": "tool_result",
                "tool_call_id": msg.get("tool_call_id", ""),
                "content": msg.get("content", "")[:500],
            })

    return {"traces": traces}


@app.get("/agent/stats")
async def get_agent_stats():
    """Get agent session statistics."""
    return {
        "active_sessions": _session_manager.get_active_count(),
        "max_sessions": _session_manager._max_sessions,
        "ttl_seconds": _session_manager._ttl,
    }


@app.get("/agent/models")
async def get_agent_models():
    """Get available LLM models."""
    return {
        "models": get_available_models(),
        "default": DEFAULT_MODEL,
    }


# ============== Data Endpoints ==============

def extract_names_from_markdown_table(content: str) -> List[str]:
    """从Markdown表格中提取名字"""
    names = set()
    lines = content.split('\n')

    for line in lines:
        # 匹配表格行，排除分隔行和空行
        line = line.strip()
        if line.startswith('|') and line.endswith('|') and '---' not in line:
            # 移除首尾的|并分割单元格
            cells = line[1:-1].split('|')
            for cell in cells:
                cell = cell.strip()
                # 过滤空单元格和特殊标记
                if cell and cell != '<br />' and cell != '--' and not cell.startswith('...'):
                    # 移除可能的多余空格
                    name = cell.replace('\u3000', ' ').replace('\t', ' ').strip()
                    if name:
                        names.add(name)

    return sorted(list(names))


@app.get("/quick-questions")
async def get_quick_questions():
    """生成5个快速问题，基于GraphRAG图数据和别名信息。"""
    import random
    from backend.rag.query_rewriter import ALIAS_MAP

    questions = []

    # ===== 1. 关系问题：基于 GraphRAG 图中有连线的干员对 =====
    try:
        from backend.rag.graphrag.query import get_graph_builder
        graph_builder = get_graph_builder()
        graph = graph_builder.graph

        if graph and graph.number_of_nodes() > 0:
            # 获取所有"干员"类型的节点
            operator_nodes = [
                n for n in graph.nodes()
                if graph.nodes[n].get("type") == "干员" or n in (graph.nodes[n] for n in graph.nodes())
            ]

            # 尝试多次找到有连线的干员对
            relation_pair = None
            for _ in range(50):
                if not operator_nodes:
                    break
                node_a = random.choice(operator_nodes)
                # 获取所有与 node_a 在同一连通分量中的节点（无向图）
                # 使用 BFS 找可达节点，记录距离
                visited = {node_a: 0}
                queue = [node_a]
                while queue:
                    current = queue.pop(0)
                    for neighbor in graph.successors(current):
                        if neighbor not in visited:
                            visited[neighbor] = visited[current] + 1
                            queue.append(neighbor)
                    for neighbor in graph.predecessors(current):
                        if neighbor not in visited:
                            visited[neighbor] = visited[current] + 1
                            queue.append(neighbor)

                # 在可达的干员节点中选择（排除自身），距离越近概率越高
                reachable_operators = [
                    (n, dist) for n, dist in visited.items()
                    if n != node_a and n in operator_nodes
                ]

                if not reachable_operators:
                    continue

                # 加权随机：距离越近概率越高 (权重 = 1/distance^2)
                weights = [1.0 / (d * d) for _, d in reachable_operators]
                total_w = sum(weights)
                weights = [w / total_w for w in weights]

                idx = random.choices(range(len(reachable_operators)), weights=weights, k=1)[0]
                node_b, dist = reachable_operators[idx]
                relation_pair = (node_a, node_b, dist)
                break

            if relation_pair:
                a, b, dist = relation_pair
                questions.append({
                    "label": f"{a}/{b}关系",
                    "question": f"{a}和{b}的关系",
                    "type": "relation",
                })
            else:
                # fallback: 随机两个干员
                op_names = operator_nodes[:100] if operator_nodes else []
                if len(op_names) >= 2:
                    a, b = random.sample(op_names, 2)
                    questions.append({
                        "label": f"{a}/{b}关系",
                        "question": f"{a}和{b}的关系",
                        "type": "relation",
                    })
        else:
            # no graph, use fallback
            questions.append({
                "label": "银灰/初雪关系",
                "question": "银灰和初雪的关系",
                "type": "relation",
            })
    except Exception as e:
        logger.error(f"Failed to generate relation question: {e}")
        questions.append({
            "label": "银灰/初雪关系",
            "question": "银灰和初雪的关系",
            "type": "relation",
        })

    # ===== 2. 技能问题：随机干员 =====
    try:
        operators_file = DATA_DIR / "all_operators.json"
        if operators_file.exists():
            with open(operators_file, 'r', encoding='utf-8') as f:
                operators_data = json.load(f)
            op_names = [op['干员名'] for op in operators_data if '干员名' in op]
            if op_names:
                chosen = random.choice(op_names)
                questions.append({
                    "label": f"{chosen}技能",
                    "question": f"{chosen}的技能是什么",
                    "type": "skill",
                })
    except Exception:
        questions.append({
            "label": "银灰技能",
            "question": "银灰的技能是什么",
            "type": "skill",
        })

    # ===== 3. 故事问题：随机故事 =====
    try:
        story_file = DATA_DIR / "story_summary.md"
        if story_file.exists():
            with open(story_file, 'r', encoding='utf-8') as f:
                content = f.read()
            story_names = extract_names_from_markdown_table(content)
            if story_names:
                chosen = random.choice(story_names)
                questions.append({
                    "label": f"{chosen}故事",
                    "question": f"{chosen}故事内容",
                    "type": "story",
                })
    except Exception:
        questions.append({
            "label": "骑士故事",
            "question": "骑士故事内容",
            "type": "story",
        })

    # ===== 4. 背景故事：随机干员（优先选在图中的干员） =====
    try:
        # 从 char_summary 中获取角色名
        char_file = DATA_DIR / "char_summary.md"
        if char_file.exists():
            with open(char_file, 'r', encoding='utf-8') as f:
                content = f.read()
            char_names = extract_names_from_markdown_table(content)
            if char_names:
                chosen = random.choice(char_names)
                questions.append({
                    "label": f"{chosen}背景",
                    "question": f"{chosen}背景故事",
                    "type": "background",
                })
    except Exception:
        questions.append({
            "label": "银灰背景",
            "question": "银灰背景故事",
            "type": "background",
        })

    # ===== 5. 别名问题：从有别名的干员中抽取 =====
    # 收集每个干员的所有别名
    alias_groups = {}
    for alias, real_name in ALIAS_MAP.items():
        if alias == real_name:
            continue
        if real_name not in alias_groups:
            alias_groups[real_name] = []
        alias_groups[real_name].append(alias)

    if alias_groups:
        operator_name = random.choice(list(alias_groups.keys()))
        aliases = alias_groups[operator_name]
        questions.append({
            "label": f"{operator_name}别名",
            "question": f"{operator_name}别名有什么",
            "type": "alias",
        })
    else:
        # fallback
        questions.append({
            "label": "银灰别名",
            "question": "银灰别名有什么",
            "type": "alias",
        })

    return {"questions": questions}


@app.get("/operators")
async def get_operators():
    """获取所有干员名列表（从all_operators.json）"""
    operators_file = DATA_DIR / "all_operators.json"
    if not operators_file.exists():
        raise HTTPException(status_code=404, detail="Operators file not found")

    try:
        with open(operators_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 提取干员名字段
        operator_names = []
        for operator in data:
            if '干员名' in operator:
                operator_names.append(operator['干员名'])

        return {"operators": operator_names}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading operators data: {str(e)}")


@app.get("/characters")
async def get_characters():
    """获取角色名列表（从char_summary.md）"""
    char_file = DATA_DIR / "char_summary.md"
    if not char_file.exists():
        raise HTTPException(status_code=404, detail="Characters file not found")

    try:
        with open(char_file, 'r', encoding='utf-8') as f:
            content = f.read()

        names = extract_names_from_markdown_table(content)
        return {"characters": names}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading characters data: {str(e)}")


@app.get("/stories")
async def get_stories():
    """获取故事名列表（从story_summary.md）"""
    story_file = DATA_DIR / "story_summary.md"
    if not story_file.exists():
        raise HTTPException(status_code=404, detail="Stories file not found")

    try:
        with open(story_file, 'r', encoding='utf-8') as f:
            content = f.read()

        names = extract_names_from_markdown_table(content)
        return {"stories": names}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading stories data: {str(e)}")


# ============== Serve Frontend Static Files ==============
STATIC_DIR = Path(__file__).parent.parent / "static"

API_PREFIXES = ("/auth/", "/conversations", "/query", "/agent/", "/api", "/health", "/status", "/stats", "/chunks/", "/knowledge-graph", "/operators", "/characters", "/stories", "/debug/", "/eval", "/docs", "/openapi", "/redoc")

if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/index.html")
    async def serve_index():
        return FileResponse(STATIC_DIR / "index.html")

    # Serve index.html for root path "/"
    @app.get("/")
    async def serve_root():
        return FileResponse(STATIC_DIR / "index.html")

    # Use middleware for SPA catch-all instead of route to avoid 405 on API POST paths
    @app.middleware("http")
    async def spa_catch_all(request: Request, call_next):
        response = await call_next(request)
        if response.status_code == 404 and request.method == "GET":
            path = request.url.path.lstrip("/")
            # Only serve index.html for non-API paths
            if not any(path.startswith(p.lstrip("/")) or path == p.lstrip("/").rstrip("/") for p in API_PREFIXES):
                return FileResponse(STATIC_DIR / "index.html")
        return response


# ============== Run Server ==============
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8889))
    uvicorn.run(app, host="0.0.0.0", port=port)

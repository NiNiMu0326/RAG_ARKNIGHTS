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

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
import uvicorn

from backend import config  # 必须在 auth 之前导入，以加载 .env

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

from backend.config import (
    BASE_DIR, CHUNKS_DIR, DATA_DIR,
    ENTITY_RELATIONS_FILE,
)

# Import AgenticRAG components
from backend.agent.sessions import SessionManager
from backend.agent.core import agent_loop
from backend.api.llm_factory import get_available_models, DEFAULT_MODEL

# ============== Lifespan ==============
@asynccontextmanager
async def lifespan(app: FastAPI):
    if not config.SILICONFLOW_API_KEY:
        raise RuntimeError("SILICONFLOW_API_KEY 环境变量未设置，拒绝启动。请在 .env 中配置。")
    await init_db()
    yield


# ============== FastAPI App ==============
app = FastAPI(
    title="Arknights RAG API",
    description="Backend API for Arknights RAG System",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — restrict origins in production via ALLOWED_ORIGINS env var (comma-separated)
_allowed_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5300,http://localhost:8100").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _allowed_origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    req_id = id(request)

    # Log request
    body_info = ""
    if request.method in ("POST", "PUT", "PATCH"):
        # Read body for logging, but restore it so the endpoint can also read it.
        # In older Starlette versions, request.body() consumes the stream,
        # so we must cache the body and restore the receive function.
        body = await request.body()

        # Restore the body so downstream handlers can read it.
        # Method 1: set _body (works in all Starlette versions, body() checks this first)
        request._body = body
        # Method 2: replace _receive (needed if body() doesn't cache on first call)
        async def receive():
            return {"type": "http.request", "body": body}
        request._receive = receive

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

# AgenticRAG Session Manager (singleton)
_session_manager = SessionManager(max_sessions=1000, ttl_seconds=3600)


# ===== Entity Relations Cache =====
# Cache the 116KB entity_relations.json in memory to avoid repeated disk reads.
# Both /knowledge-graph and /stats need this data, and it doesn't change at runtime.
_entity_relations_cache: Optional[Dict] = None

# ===== Quick Questions Cache =====
# Cache quick questions to avoid repeated file reads and graph traversal.
_quick_questions_cache: Optional[List] = None
_quick_questions_cache_time: float = 0
_quick_questions_cache_ttl: float = 300  # 5 minutes


def _load_entity_relations() -> Dict:
    """Load entity relations from JSON file, cached in memory."""
    global _entity_relations_cache
    if _entity_relations_cache is None:
        if ENTITY_RELATIONS_FILE.exists():
            with open(ENTITY_RELATIONS_FILE, "r", encoding="utf-8") as f:
                _entity_relations_cache = json.load(f)
        else:
            _entity_relations_cache = {"entities": [], "relations": []}
    return _entity_relations_cache


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
        "api_key_configured": bool(config.SILICONFLOW_API_KEY),
        "embedding_model": config.EMBEDDING_MODEL,
        "reranker_model": config.RERANKER_MODEL,
        "llm_model": config.DEEPSEEK_LLM_MODEL or "not configured"
    }


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
    """Get entity relations for knowledge graph (cached)."""
    data = _load_entity_relations()
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

    # Count relations (cached)
    data = _load_entity_relations()
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


class RenameRequest(BaseModel):
    name: str

    @field_validator('name')
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('会话名称不能为空')
        return v.strip()


@app.put("/conversations/{session_id}/rename")
async def rename_conversation(session_id: str, req: RenameRequest, user: dict = Depends(get_current_user)):
    """Rename a conversation."""
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    db = await get_db()
    try:
        cursor = await db.execute("SELECT user_id FROM conversations WHERE session_id = ?", (session_id,))
        row = await cursor.fetchone()
        if not row or row["user_id"] != user["user_id"]:
            raise HTTPException(status_code=404, detail="会话不存在")
        await db.execute("UPDATE conversations SET name = ? WHERE session_id = ?", (req.name, session_id))
        await db.commit()
        return {"status": "ok"}
    finally:
        await db.close()


# ============== AgenticRAG Endpoints ==============

@app.post("/agent/session")
async def create_agent_session():
    """Create a new agent session."""
    session_id = await _session_manager.create_session()
    return {"session_id": session_id}


@app.post("/agent/chat")
async def agent_chat(req: AgentChatRequest):
    """Agent chat endpoint with SSE streaming.
    
    If the session_id is invalid or expired, a new session is auto-created.
    """
    session = await _session_manager.get_session(req.session_id)
    actual_session_id = req.session_id

    if session is None:
        # Session expired or invalid — auto-create a new one
        actual_session_id = await _session_manager.create_session()
        logger.warning(f"Session '{req.session_id}' not found/expired, auto-created new session: {actual_session_id}")
    
    model_id = req.model or DEFAULT_MODEL
    logger.info(f"[AGENT CHAT] session={actual_session_id} model={model_id} message={req.message[:100]}")

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    if actual_session_id != req.session_id:
        headers["X-New-Session-Id"] = actual_session_id

    return StreamingResponse(
        agent_loop(
            session_id=actual_session_id,
            user_message=req.message,
            session_manager=_session_manager,
            model_id=model_id,
        ),
        media_type="text/event-stream",
        headers=headers,
    )


@app.get("/agent/session/{session_id}/messages")
async def get_session_messages(session_id: str):
    """Get session message history."""
    session = await _session_manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    return {"messages": session.messages}


@app.delete("/agent/session/{session_id}")
async def delete_agent_session(session_id: str):
    """Delete a session."""
    await _session_manager.delete_session(session_id)
    return {"status": "ok"}


@app.get("/agent/debug/trace")
async def get_agent_debug_trace(session_id: str):
    """Get Agent's complete tool call trace for debugging."""
    session = await _session_manager.get_session(session_id)
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
        "active_sessions": await _session_manager.get_active_count(),
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


# ===== Quick Questions static data caches =====
# Pre-load these at first access to avoid repeated disk I/O on every refresh.
_qq_operator_names: Optional[List[str]] = None
_qq_story_names: Optional[List[str]] = None
_qq_enemy_names: Optional[List[str]] = None
_qq_alias_candidates: Optional[List[tuple]] = None  # [(standard_name, [aliases]), ...]
_qq_graph_operators: Optional[List[str]] = None  # operator nodes from graph
_qq_previous_labels: Optional[set] = None  # dedup: labels from previous batch


def _load_qq_data():
    """Lazy-load all static data needed for quick-question generation."""
    global _qq_operator_names, _qq_story_names, _qq_enemy_names, _qq_alias_candidates, _qq_graph_operators

    if _qq_operator_names is not None:
        return  # already loaded

    from backend.rag.alias_map import ALIAS_MAP
    from collections import defaultdict

    # Operator names (skill questions): from all_operators.json
    operators_file = DATA_DIR / "all_operators.json"
    if operators_file.exists():
        with open(operators_file, 'r', encoding='utf-8') as f:
            operators_data = json.load(f)
        _qq_operator_names = [
            op['干员名'] for op in operators_data
            if '干员名' in op and op.get('星级', '6') not in ('1', '2')
        ]
    else:
        _qq_operator_names = []

    # Story names: from stories/*.md first heading
    stories_dir = DATA_DIR / "stories"
    _qq_story_names = []
    if stories_dir.exists():
        for f in sorted(stories_dir.glob("*.md")):
            try:
                first_line = f.read_text(encoding='utf-8').split('\n', 1)[0].strip()
                if first_line.startswith('# '):
                    _qq_story_names.append(first_line[2:].strip())
            except Exception:
                pass

    # Enemy names: from all_enemies.json
    enemies_file = DATA_DIR / "all_enemies.json"
    if enemies_file.exists():
        with open(enemies_file, 'r', encoding='utf-8') as f:
            enemies_data = json.load(f)
        _qq_enemy_names = [e['名称'] for e in enemies_data if '名称' in e]
    else:
        _qq_enemy_names = []

    # Alias candidates: operators with 2+ aliases
    name_to_aliases = defaultdict(set)
    for alias, standard in ALIAS_MAP.items():
        name_to_aliases[standard].add(alias)
    _qq_alias_candidates = [
        (name, sorted(aliases))
        for name, aliases in name_to_aliases.items()
        if len(aliases) >= 2
    ]

    # Graph operator nodes: operator-type nodes from entity_relations graph
    _qq_graph_operators = []
    try:
        er = _load_entity_relations()
        entities = er.get("entities", {})
        if isinstance(entities, dict):
            for entity_type, entity_list in entities.items():
                if isinstance(entity_list, list):
                    for e in entity_list:
                        name = e.get("name", "") if isinstance(e, dict) else str(e)
                        if name:
                            _qq_graph_operators.append(name)
    except Exception:
        pass


def _pick_excluding(candidates: list, label_suffix: str, exclude_labels: set, key=lambda x: x) -> Optional[str]:
    """Pick a random item from candidates whose derived label is not in exclude_labels.
    Tries up to 20 times, then falls back to random choice."""
    import random
    for _ in range(20):
        chosen = random.choice(candidates)
        label = f"{key(chosen)}{label_suffix}"
        if label not in exclude_labels:
            return chosen, label
    # All excluded — just pick random
    chosen = random.choice(candidates)
    return chosen, f"{key(chosen)}{label_suffix}"


@app.get("/quick-questions")
async def get_quick_questions(refresh: bool = False):
    """生成5个快速问题，基于GraphRAG图数据和别名信息。"""
    import random

    global _quick_questions_cache, _quick_questions_cache_time, _qq_previous_labels

    now = time.time()
    if not refresh and _quick_questions_cache and now - _quick_questions_cache_time < _quick_questions_cache_ttl:
        return {"questions": _quick_questions_cache}

    # Lazy-load static data (cached after first call)
    _load_qq_data()

    # Build exclude set from previous batch (dedup)
    exclude_labels = _qq_previous_labels or set()

    questions = []

    # ===== 1. 关系问题：基于图中直接相连的干员对（O(deg) 替代 O(V+E) BFS） =====
    try:
        op_nodes = _qq_graph_operators or []
        if op_nodes:
            relation_label = None
            for _ in range(30):
                node_a = random.choice(op_nodes)
                # Use entity_relations to find directly connected pairs (fast)
                er = _load_entity_relations()
                relations = er.get("relations", [])
                connected = set()
                for r in relations:
                    s = r.get("source", r.get("head", ""))
                    t = r.get("target", r.get("tail", ""))
                    if s == node_a and t in op_nodes:
                        connected.add(t)
                    elif t == node_a and s in op_nodes:
                        connected.add(s)
                # Also try graph neighbors if graph is available
                try:
                    from backend.rag.graphrag.query import get_graph_builder
                    gb = get_graph_builder()
                    if gb and gb.graph and node_a in gb.graph:
                        for nb in set(list(gb.graph.successors(node_a)) + list(gb.graph.predecessors(node_a))):
                            if nb in op_nodes:
                                connected.add(nb)
                except Exception:
                    pass
                if connected:
                    node_b = random.choice(list(connected))
                    relation_label = f"{node_a}/{node_b}关系"
                    if relation_label not in exclude_labels:
                        questions.append({
                            "label": relation_label,
                            "question": f"{node_a}和{node_b}的关系",
                            "type": "relation",
                        })
                        exclude_labels.add(relation_label)
                        break
            if not questions:  # no relation found after all attempts
                # Fallback: two random operators
                if len(op_nodes) >= 2:
                    a, b = random.sample(op_nodes, 2)
                    label = f"{a}/{b}关系"
                    questions.append({
                        "label": label,
                        "question": f"{a}和{b}的关系",
                        "type": "relation",
                    })
                    exclude_labels.add(label)
        else:
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

    # ===== 2. 技能问题：随机干员（内存中的预加载数据） =====
    if _qq_operator_names:
        chosen, label = _pick_excluding(_qq_operator_names, "技能", exclude_labels)
        questions.append({
            "label": label,
            "question": f"{chosen}的技能是什么",
            "type": "skill",
        })
        exclude_labels.add(label)
    else:
        questions.append({
            "label": "银灰技能",
            "question": "银灰的技能是什么",
            "type": "skill",
        })

    # ===== 3. 故事问题：随机故事 =====
    if _qq_story_names:
        chosen, label = _pick_excluding(_qq_story_names, "故事", exclude_labels)
        questions.append({
            "label": label,
            "question": f"{chosen}的故事内容",
            "type": "story",
        })
        exclude_labels.add(label)
    else:
        questions.append({
            "label": "乌萨斯的孩子们故事",
            "question": "乌萨斯的孩子们的故事内容",
            "type": "story",
        })

    # ===== 4. 敌人问题：随机敌人 =====
    if _qq_enemy_names:
        chosen, label = _pick_excluding(_qq_enemy_names, "敌人", exclude_labels)
        questions.append({
            "label": label,
            "question": f"{chosen}的属性和能力是什么",
            "type": "enemy",
        })
        exclude_labels.add(label)
    else:
        questions.append({
            "label": "源石虫敌人",
            "question": "源石虫的属性和能力是什么",
            "type": "enemy",
        })

    # ===== 5. 别名问题：有多个别名的干员 =====
    if _qq_alias_candidates:
        # Pick excluding by the operator name part of the label
        for _ in range(20):
            chosen_name, aliases = random.choice(_qq_alias_candidates)
            label = f"{chosen_name}别名"
            if label not in exclude_labels:
                questions.append({
                    "label": label,
                    "question": f"{chosen_name}的其他名称有哪些",
                    "type": "alias",
                })
                exclude_labels.add(label)
                break
        else:
            # All excluded, just pick random
            chosen_name, aliases = random.choice(_qq_alias_candidates)
            label = f"{chosen_name}别名"
            questions.append({
                "label": label,
                "question": f"{chosen_name}的其他名称有哪些",
                "type": "alias",
            })
            exclude_labels.add(label)
    else:
        questions.append({
            "label": "银灰别名",
            "question": "银灰的其他名称有哪些",
            "type": "alias",
        })

    # Update caches
    _quick_questions_cache = questions
    _quick_questions_cache_time = time.time()
    _qq_previous_labels = {q["label"] for q in questions}

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


# ============== 前端静态文件 ==============
_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=_frontend_dist / "assets"), name="static-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """SPA catch-all: 非 API 路由统一返回 index.html，由前端路由处理。"""
        file_path = _frontend_dist / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_frontend_dist / "index.html")


# ============== Run Server ==============
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8100))
    uvicorn.run(app, host="0.0.0.0", port=port)

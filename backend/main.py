"""
Arknights RAG Backend - FastAPI Server
Provides REST API for the frontend
"""
import sys
import os
import json
from pathlib import Path
from typing import List, Optional, Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
import uvicorn

# Import RAG components
from backend.rag.orchestrator import RAGOrchestrator, get_orchestrator
from backend.config import (
    BASE_DIR, CHUNKS_DIR, FAISS_INDEX_DIR, DATA_DIR,
    ENTITY_RELATIONS_FILE, EVAL_QUESTIONS_FILE, SILICONFLOW_API_KEY,
    EMBEDDING_MODEL, RERANKER_MODEL, DEEPSEEK_LLM_MODEL, DEEPSEEK_API_KEY, LLM_MODEL,
)
import backend.config as config

try:
    from eval.rag_eval import LLMEvaluator, load_questions, run_evaluation
    _eval_available = True
except ImportError:
    _eval_available = False
    print("WARNING: eval.rag_eval not available, /eval endpoint will be disabled")

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

def get_orch() -> RAGOrchestrator:
    return get_orchestrator(
        api_key=str(SILICONFLOW_API_KEY),
        faiss_index_dir=str(FAISS_INDEX_DIR),
        deepseek_api_key=str(DEEPSEEK_API_KEY)
    )


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


class StepDebugRequest(BaseModel):
    question: str
    step: int  # 1-8, which step to execute
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    # Previous step results (for step-by-step execution)
    step_results: Dict[int, Any] = Field(default_factory=dict)
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

    @field_validator('step')
    @classmethod
    def step_must_be_valid(cls, v: int) -> int:
        if v < 1 or v > 8:
            raise ValueError(f'step must be between 1 and 8, got {v}')
        return v

    @field_validator('top_k_per_channel', 'rerank_top_k')
    @classmethod
    def top_k_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f'top_k values must be positive, got {v}')
        if v > 100:
            raise ValueError(f'top_k values must not exceed 100, got {v}')
        return v


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


class StepDebugResponse(BaseModel):
    step: int
    step_name: str
    step_name_cn: str
    input_data: Any
    output_data: Any
    time_ms: int
    can_continue: bool
    error: Optional[str] = None


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


@app.post("/debug/step", response_model=StepDebugResponse)
async def debug_step(req: StepDebugRequest):
    """Execute a single RAG step for debugging"""
    try:
        orch = get_orch()
        result = orch.run_debug_step(
            step=req.step,
            question=req.question,
            conversation_history=req.conversation_history,
            previous_results=req.step_results,
            use_parent_doc=req.use_parent_doc,
            use_graphrag=req.use_graphrag,
            use_crag=req.use_crag,
            top_k_per_channel=req.top_k_per_channel,
            rerank_top_k=req.rerank_top_k
        )

        return StepDebugResponse(
            step=result['step'],
            step_name=result['name'],
            step_name_cn=result['name_cn'],
            input_data=result.get('input_data'),
            output_data=result.get('output_data'),
            time_ms=result.get('time_ms', 0),
            can_continue=result.get('can_continue', False),
            error=result.get('error')
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


@app.get("/eval")
async def run_eval():
    """Run evaluation on the question set"""
    if not _eval_available:
        raise HTTPException(status_code=503, detail="Eval module not available")

    if not EVAL_QUESTIONS_FILE.exists():
        raise HTTPException(status_code=404, detail="Questions file not found")

    questions = load_questions(EVAL_QUESTIONS_FILE)
    if not questions:
        raise HTTPException(status_code=400, detail="No questions found")

    orch = get_orch()
    evaluator = LLMEvaluator(SILICONFLOW_API_KEY)

    def rag_pipeline(question: str):
        result = orch.query(question=question)
        return {"answer": result.answer}

    result = run_evaluation(
        questions=questions,
        rag_pipeline_fn=rag_pipeline,
        evaluator=evaluator
    )

    return result


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
STATIC_DIR = Path(__file__).parent.parent / "frontend" / "dist"

if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/index.html")
    async def serve_index():
        return FileResponse(STATIC_DIR / "index.html")

    # Serve index.html for root path "/"
    @app.get("/")
    async def serve_root():
        return FileResponse(STATIC_DIR / "index.html")

    # Catch-all: serve index.html for any non-API path (Vue SPA)
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")


# ============== Run Server ==============
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8889))
    uvicorn.run(app, host="0.0.0.0", port=port)

"""
Agent core loop for AgenticRAG.
Implements the native parallel Function Calling loop with asyncio.gather.
"""

import json
import time
import asyncio
import logging
from typing import AsyncGenerator, Dict, List, Any, Optional

from backend.agent.sessions import Session, SessionManager
from backend.agent.prompts import build_messages
from backend.agent.tools import ToolRegistry, get_tool_registry
from backend.api.deepseek import DeepSeekClient, ChatResponse, ToolCall, STREAM_EVENT_THINKING_DELTA, STREAM_EVENT_CONTENT_DELTA, STREAM_EVENT_TOOL_CALLS, STREAM_EVENT_DONE
from backend.api.llm_factory import get_llm_client, get_model_info, DEFAULT_MODEL
from backend import config

logger = logging.getLogger(__name__)


# ===== SSE Event Formatters =====

def format_tool_calls_start(tool_calls: List[ToolCall], round_num: int) -> str:
    """Format tool_calls_start SSE event."""
    tool_calls_list = []
    for tc in tool_calls:
        try:
            args = json.loads(tc.arguments)
        except (json.JSONDecodeError, TypeError):
            args = {}
        tool_calls_list.append({
            "id": tc.id,
            "name": tc.name,
            "arguments": args,
        })
    data = json.dumps({
        "type": "tool_calls_start",
        "round": round_num,
        "tool_calls": tool_calls_list,
    }, ensure_ascii=False)
    return f"data: {data}\n\n"


def format_tool_call_result(tool_call_id: str, result: Any, time_ms: float = 0, tool_name: str = "") -> str:
    """Format tool_call_result SSE event."""
    # Generate summary from result
    if isinstance(result, list):
        summary = f"返回 {len(result)} 条结果"
    elif isinstance(result, dict):
        if result.get("error"):
            summary = f"错误: {result['error']}"
        elif result.get("found") is False:
            summary = result.get("message", "未找到结果")
        elif result.get("mode") == "path":
            path = result.get("path", [])
            edges = result.get("edges", [])
            if path:
                # Build detailed path summary with edge relations
                if edges:
                    edge_strs = []
                    for e in edges:
                        rel = e.get("relation", "")
                        desc = e.get("description", "")
                        if desc:
                            edge_strs.append(f"{e.get('from','')}--{rel}-->{e.get('to','')} ({desc})")
                        else:
                            edge_strs.append(f"{e.get('from','')}--{rel}-->{e.get('to','')}")
                    summary = f"路径: {' → '.join(path)} | 边: {'; '.join(edge_strs)}"
                else:
                    summary = f"路径: {' → '.join(path)}"
            else:
                summary = "无路径"
        elif result.get("mode") == "neighbors":
            neighbors = result.get("neighbors", [])
            summary = f"找到 {len(neighbors)} 个关联实体"
        else:
            summary = "查询完成"
    else:
        summary = str(result)[:100] if result else "完成"

    data = json.dumps({
        "type": "tool_call_result",
        "tool_call_id": tool_call_id,
        "tool_name": tool_name,
        "summary": summary,
        "time_ms": round(time_ms),
        "result": result,
    }, ensure_ascii=False)
    return f"data: {data}\n\n"


def format_tool_executing(tool_call_id: str, tool_name: str) -> str:
    """Format tool_executing SSE event — sent when a tool starts executing."""
    data = json.dumps({
        "type": "tool_executing",
        "tool_call_id": tool_call_id,
        "tool_name": tool_name,
    }, ensure_ascii=False)
    return f"data: {data}\n\n"


def format_answer_delta(delta: str) -> str:
    """Format answer_delta SSE event (streaming token)."""
    data = json.dumps({
        "type": "answer_delta",
        "delta": delta,
    }, ensure_ascii=False)
    return f"data: {data}\n\n"


def format_thinking_delta(content: str) -> str:
    """Format thinking_delta SSE event (LLM reasoning content)."""
    data = json.dumps({
        "type": "thinking_delta",
        "content": content,
    }, ensure_ascii=False)
    return f"data: {data}\n\n"


def format_thinking_start(round_num: int = 1, timestamp_ms: float = 0) -> str:
    """Format thinking_start SSE event — sent at the beginning of each LLM call."""
    data = json.dumps({
        "type": "thinking_start",
        "round": round_num,
        "timestamp_ms": timestamp_ms,
    }, ensure_ascii=False)
    return f"data: {data}\n\n"


def format_answer_done(full_content: str, metrics: Dict = None) -> str:
    """Format answer_done SSE event."""
    data = json.dumps({
        "type": "answer_done",
        "answer": full_content,
        "metrics": metrics or {},
    }, ensure_ascii=False)
    return f"data: {data}\n\n"


def format_error(error_msg: str) -> str:
    """Format error SSE event."""
    data = json.dumps({
        "type": "error",
        "message": error_msg,
    }, ensure_ascii=False)
    return f"data: {data}\n\n"


# ===== Loop Detection =====

def detect_loop(messages: List[Dict], window: int = 3) -> bool:
    """Detect if the agent is stuck in a loop of repeated identical tool_calls.
    
    Checks at the message level (per-round), comparing the full set of tool_calls
    in each assistant message. A loop is detected when `window` consecutive rounds
    produce identical tool_call sets (same function names + arguments).
    """
    recent_rounds = []
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            # Build a sorted, deterministic key for this round's tool_calls
            round_keys = []
            for tc in msg["tool_calls"]:
                fn = tc.get("function", {})
                round_keys.append(f"{fn.get('name', '')}:{fn.get('arguments', '')}")
            round_keys.sort()
            recent_rounds.append(tuple(round_keys))
            if len(recent_rounds) >= window:
                break

    # If all recent rounds are identical, it's a loop
    return len(recent_rounds) >= window and len(set(recent_rounds)) == 1


# ===== Tool Execution =====

async def execute_tool(registry: ToolRegistry, tool_call: ToolCall) -> Any:
    """Execute a single tool call and return the result."""
    try:
        args = json.loads(tool_call.arguments)
    except (json.JSONDecodeError, TypeError):
        args = {}

    logger.info(f"[TOOL EXEC] {tool_call.name} args={json.dumps(args, ensure_ascii=False)[:200]}")
    try:
        result = await registry.execute(tool_call.name, args)
        logger.info(f"[TOOL EXEC DONE] {tool_call.name} result_type={type(result).__name__}")
        return result
    except Exception as e:
        logger.error(f"[TOOL EXEC FAILED] {tool_call.name}({args}): {e}", exc_info=True)
        return {"error": f"工具执行失败: {str(e)}"}


# ===== Agent Loop =====


async def agent_loop(
    session_id: str,
    user_message: str,
    session_manager: SessionManager,
    model_id: str = None,
    max_rounds: int = 8,
) -> AsyncGenerator[str, None]:
    """Agent main loop with parallel Function Calling support.
    
    Each round:
    1. Build messages (system + history + user)
    2. Call LLM with tools (do NOT pass parallel_tool_calls)
    3. If tool_calls returned (1~N) → execute in parallel → add results to messages → continue
    4. If no tool_calls → output final answer
    
    Safety mechanisms:
    - max_rounds hard limit to prevent infinite loops
    - detect_loop() to catch repeated identical tool_calls
    """
    session = session_manager.get_session(session_id)
    if session is None:
        logger.error(f"[SESSION] Session '{session_id}' not found or expired")
        yield format_error("会话不存在或已过期，请创建新会话")
        return

    # Add user message
    session.add_message("user", user_message)
    messages = build_messages(session)
    logger.info(f"[SESSION] session={session_id} user_message={user_message[:100]}")

    loop_start = time.time()

    model_id = model_id or DEFAULT_MODEL
    model_info = get_model_info(model_id)
    client = get_llm_client(model_id)
    registry = get_tool_registry()
    tool_schemas = registry.get_schemas()

    logger.info(f"[MODEL] Using model: {model_id} ({model_info['display_name']})")

    for round_num in range(1, max_rounds + 1):
        # Detect loop
        if detect_loop(session.messages):
            logger.warning(f"[LOOP] Loop detected in session {session_id}")
            yield format_error("我在查找信息时陷入了循环，无法完成回答。请尝试更具体的问题。")
            return

        # Call LLM with tools (streaming)
        try:
            logger.info(f"[LLM CALL] Round {round_num}: Sending {len(messages)} messages to {model_info['display_name']}")
            yield format_thinking_start(round_num, timestamp_ms=time.time() * 1000)
            # Force flush: ensure thinking_start reaches the client immediately
            await asyncio.sleep(0)

            # Collect streaming response
            tool_calls = None
            final_content = ""
            final_reasoning = ""
            stream = client.chat_with_tools_stream(
                messages=messages,
                tools=tool_schemas,
                temperature=0.3,
            )
            async for event in stream:
                etype = event["type"]

                if etype == STREAM_EVENT_THINKING_DELTA:
                    # Stream reasoning content to frontend immediately
                    yield format_thinking_delta(event["content"])

                elif etype == STREAM_EVENT_CONTENT_DELTA:
                    # Stream answer content to frontend immediately
                    yield format_answer_delta(event["delta"])

                elif etype == STREAM_EVENT_TOOL_CALLS:
                    # Model decided to use tools
                    tool_calls = event["tool_calls"]
                    final_content = event.get("content", "")
                    final_reasoning = event.get("reasoning_content", "")

                elif etype == STREAM_EVENT_DONE:
                    # Model answered directly without tools
                    final_content = event.get("content", "")
                    final_reasoning = event.get("reasoning_content", "")

            logger.info(f"[LLM RESPONSE] Round {round_num}: content_len={len(final_content)} tool_calls={len(tool_calls) if tool_calls else 0}")
        except Exception as e:
            logger.error(f"[LLM ERROR] {model_info['display_name']} API call failed: {e}", exc_info=True)
            yield format_error(f"AI 服务暂时不可用: {str(e)}")
            return

        # Check if model wants to use tools
        if not tool_calls:
            # Model decided to answer directly — content was already streamed
            session.add_message("assistant", final_content)

            total_ms = round((time.time() - loop_start) * 1000)
            logger.info(f"[ANSWER] session={session_id} rounds={round_num - 1} total_time={total_ms}ms content_len={len(final_content)}")
            yield format_answer_done(final_content, metrics={
                "total_time_ms": total_ms,
                "num_tool_rounds": round_num - 1,
            })
            return

        # Model returned tool_calls → execute in parallel
        tool_names = [tc.name for tc in tool_calls]
        logger.info(f"[TOOL CALLS] Round {round_num}: {len(tool_calls)} calls: {tool_names}")

        # Record assistant's tool_calls message (strips reasoning_content for API safety)
        session.add_assistant_tool_calls(
            tool_calls, content=final_content,
            reasoning_content=final_reasoning,
        )

        # Notify frontend about tool calls
        yield format_tool_calls_start(tool_calls, round_num)
        # Force flush: yield control to allow SSE event to be sent immediately
        await asyncio.sleep(0)

        # Execute all tool_calls in parallel, each with individual timing
        async def _execute_with_timing(tc: ToolCall):
            """Execute a single tool and return (result, time_ms)."""
            start = time.time()
            result = await execute_tool(registry, tc)
            elapsed = (time.time() - start) * 1000
            return result, elapsed

        # Notify frontend that tools are starting execution
        for tc in tool_calls:
            yield format_tool_executing(tc.id, tc.name)
        # Force flush: ensure tool_executing events reach the client before tool execution
        await asyncio.sleep(0)

        timed_results = await asyncio.gather(
            *[_execute_with_timing(tc) for tc in tool_calls]
        )

        # Record each tool result and notify frontend
        for tc, (result, elapsed_ms) in zip(tool_calls, timed_results):
            session.add_tool_result(tc.id, result)
            # Log tool result summary
            result_summary = ""
            if isinstance(result, list):
                result_summary = f"{len(result)} items"
            elif isinstance(result, dict):
                result_summary = result.get("error", "") or f"keys={list(result.keys())[:5]}"
            else:
                result_summary = str(result)[:100]
            logger.info(f"[TOOL RESULT] {tc.name} ({elapsed_ms:.0f}ms): {result_summary}")
            yield format_tool_call_result(tc.id, result, time_ms=elapsed_ms, tool_name=tc.name)

        # Rebuild messages for next round
        messages = build_messages(session)

    # Exceeded max rounds
    logger.warning(f"Max rounds ({max_rounds}) exceeded in session {session_id}")
    yield format_error("我无法在有限的步骤内完成回答，请尝试更具体的问题。")

"""
每日自动增量同步脚本
====================
用于 cron 每日定时执行，自动检测更新、切块、重建索引。

执行顺序:
  1. lore_sync (剧情 Wiki) → 增量同步角色/剧情/索引
  2. sync_prts (PRTS Wiki) → 增量同步干员/敌人
  3. 如果有新增文件 → 重新切块 → 重建 BM25 → 增量更新 FAISS
  4. 如果索引有更新 → 重启 uvicorn

用法:
  python Scripts/daily_sync.py
  python Scripts/daily_sync.py --dry-run
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = Path(__file__).parent
LOG_FILE = SCRIPTS_DIR / "daily_sync_log.txt"


def log(msg: str):
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{stamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def count_files(dir_path: Path, pattern: str = "*.md") -> int:
    """统计目录下匹配文件数。"""
    if not dir_path.exists():
        return 0
    return len(list(dir_path.glob(pattern)))


def run_script(script_name: str, args: list = None) -> bool:
    """运行一个 Python 脚本，返回是否成功。"""
    script_path = SCRIPTS_DIR / script_name
    cmd = [sys.executable, str(script_path)] + (args or [])
    log(f"  执行: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(BASE_DIR))
    # 输出关键日志行
    for line in result.stdout.strip().split("\n"):
        if any(kw in line for kw in ("新增", "同步", "✓", "✗", "完成", "失败", "跳过", "无变化")):
            log(f"    {line.strip()}")
    if result.returncode != 0:
        log(f"    ✗ 返回码 {result.returncode}: {result.stderr[:300]}")
        return False
    return True


def rebuild_bm25() -> bool:
    """重建所有 BM25 索引（快速，纯本地）。"""
    log("  重建 BM25 索引...")
    bm25_script = BASE_DIR / "backend" / "data" / "bm25_index.py"
    result = subprocess.run(
        [sys.executable, str(bm25_script)],
        capture_output=True, text=True, cwd=str(BASE_DIR)
    )
    if result.returncode != 0:
        log(f"    ✗ {result.stderr[:300]}")
        return False
    for line in result.stdout.strip().split("\n"):
        log(f"    {line.strip()}")
    return True


def rebuild_faiss() -> bool:
    """重建所有 FAISS 索引（需要 API 调用，较慢）。"""
    log("  重建 FAISS 索引（需要 API）...")
    faiss_script = BASE_DIR / "backend" / "build_faiss_index.py"
    result = subprocess.run(
        [sys.executable, str(faiss_script), "--force"],
        capture_output=True, text=True, cwd=str(BASE_DIR),
    )
    if result.returncode != 0:
        log(f"    ✗ {result.stderr[:300]}")
        return False
    for line in result.stdout.strip().split("\n"):
        if any(kw in line for kw in ("Built", "Embedding", "Done", "chunks")):
            log(f"    {line.strip()}")
    return True


def rechunk_all(skip_knowledge: bool = False) -> bool:
    """重新运行 chunker（文本处理，快速）。"""
    log("  重新切块...")
    chunker_script = BASE_DIR / "backend" / "data" / "chunker.py"
    if not chunker_script.exists():
        log("    ✗ chunker.py 不存在")
        return False
    result = subprocess.run(
        [sys.executable, str(chunker_script)],
        capture_output=True, text=True, cwd=str(BASE_DIR)
    )
    if result.returncode != 0:
        log(f"    ✗ {result.stderr[:300]}")
        return False
    for line in result.stdout.strip().split("\n"):
        if "complete" in line.lower() or ":" in line:
            log(f"    {line.strip()}")
    return True


def restart_uvicorn():
    """重启 uvicorn 服务。"""
    log("  重启 uvicorn...")
    import signal
    # 找 uvicorn 进程
    result = subprocess.run(
        ["pgrep", "-f", "uvicorn backend.main"],
        capture_output=True, text=True
    )
    pids = [int(pid) for pid in result.stdout.strip().split("\n") if pid]
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception:
            pass

    # 等待旧进程退出
    import time
    time.sleep(2)

    # 启动新进程
    subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app",
         "--host", "0.0.0.0", "--port", "8889"],
        cwd=str(BASE_DIR),
        stdout=open("/tmp/uvicorn.log", "a"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    log("    ✓ uvicorn 已重启")


def main():
    parser = argparse.ArgumentParser(description="每日自动增量同步")
    parser.add_argument("--dry-run", action="store_true", help="只检测，不实际执行")
    args = parser.parse_args()

    log("=" * 60)
    log("每日自动同步开始" + (" (dry-run)" if args.dry_run else ""))

    any_changes = False

    # ===== 1. 剧情 Wiki 同步 =====
    log("\n[1/3] 剧情 Wiki 增量同步")
    lore_args = ["--dry-run"] if args.dry_run else []
    if run_script("lore_sync.py", lore_args):
        # 检查是否有新增（非 dry-run 模式）
        if not args.dry_run:
            pass  # lore_sync 本身会在日志里报告

    # ===== 2. PRTS Wiki 同步 =====
    log("\n[2/3] PRTS Wiki 增量同步")
    prts_args = ["--update-index"] if not args.dry_run else ["--dry-run"]
    run_script("sync_prts.py", prts_args)

    if args.dry_run:
        log("\n(dry-run 结束)")
        return

    # ===== 3. 检查是否需要重新切块和重建索引 =====
    log("\n[3/3] 索引维护")

    # 重新切块（确保 chunks 目录与 data 目录一致）
    # 这是最快的保证一致性的方式
    rechunk_ok = rechunk_all(skip_knowledge=True)
    if rechunk_ok:
        rebuild_bm25()

    # FAISS 增量更新：只对有 diff 的 collection 重建
    # 简单策略：如果 lore_sync 有更新，重建 operators + stories 的 FAISS
    # 具体判断略复杂，简化处理：总是做增量 FAISS
    # （sync_prts 的 --update-index 已经处理了 knowledge）
    # 这里只处理 operators + stories
    log("  检查 operators + stories FAISS 增量...")
    try:
        sys.path.insert(0, str(BASE_DIR))
        from backend.api.siliconflow import SiliconFlowClient
        from backend.storage.faiss_client import FAISSClientWrapper
        from langchain_core.documents import Document

        client = FAISSClientWrapper()
        emb_client = SiliconFlowClient()

        for coll in ["operators", "stories"]:
            chunks_dir = BASE_DIR / "chunks" / coll
            if not chunks_dir.exists():
                continue

            # 加载现有索引
            result = client.load_index(coll)
            if result is None:
                log(f"    {coll}: 索引不存在，全量构建")
                # 全量构建
                chunk_files = sorted(list(chunks_dir.glob("*.md")) + list(chunks_dir.glob("*.txt")))
                docs = []
                for fp in chunk_files:
                    content = fp.read_text(encoding="utf-8")
                    docs.append(Document(
                        page_content=content,
                        metadata={"chunk_id": fp.stem, "section": fp.stem,
                                  "source_file": fp.name, "source_collection": coll}
                    ))
                if docs:
                    embeddings = emb_client.embed([d.page_content for d in docs])
                    client.build_index(coll, docs, embeddings=embeddings)
                    log(f"      ✓ 已构建 {len(docs)} chunks")
                continue

            index, meta = result
            existing_ids = {m["id"] for m in meta.values()}
            chunk_files = set(p.stem for p in chunks_dir.glob("*.md"))
            chunk_files |= set(p.stem for p in chunks_dir.glob("*.txt"))
            new_ids = chunk_files - existing_ids

            if not new_ids:
                log(f"    {coll}: 无新增 (已有 {index.ntotal})")
                continue

            log(f"    {coll}: +{len(new_ids)} 新 chunks")
            new_docs = []
            for cid in sorted(new_ids):
                for ext in [".md", ".txt"]:
                    fp = chunks_dir / f"{cid}{ext}"
                    if fp.exists():
                        content = fp.read_text(encoding="utf-8")
                        new_docs.append(Document(
                            page_content=content,
                            metadata={"chunk_id": cid, "section": cid,
                                      "source_file": fp.name, "source_collection": coll}
                        ))
                        break

            if new_docs:
                texts = [d.page_content for d in new_docs]
                embeddings = emb_client.embed(texts)
                total = client.add_documents(coll, new_docs, embeddings=embeddings)
                log(f"      ✓ 总计 {total}")
                any_changes = True

    except Exception as e:
        log(f"    ✗ FAISS 增量更新失败: {e}")

    # ===== 4. 重启服务 =====
    if any_changes:
        log("\n索引有更新，重启服务...")
        restart_uvicorn()
    else:
        log("\n无索引变更，跳过重启")

    log("\n每日自动同步完成")


if __name__ == "__main__":
    main()

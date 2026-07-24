"""
明日方舟剧情 Wiki 增量同步
==========================
监测 littlepangding/arknights_lore_wiki，增量下载新角色/新剧情/新索引，
清洗 LLM 警告头/wiki 链接后存入本地 data/ 目录。

用法:
  python Scripts/lore_sync.py                # 增量同步
  python Scripts/lore_sync.py --dry-run       # 只检测
  python Scripts/lore_sync.py --full          # 全量更新（清空本地后重下所有）
"""

import os
import re
import sys
import json
import time
import shutil
import base64
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Tuple, Optional, Set

import requests

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
SCRIPTS_DIR = Path(__file__).parent

# 本地存储路径
LOCAL_STORIES_DIR = DATA_DIR / "stories"
LOCAL_CHARS_DIR = DATA_DIR / "operators"
LOCAL_CHAR_INDEX = DATA_DIR / "char_summary.md"
LOCAL_STORY_INDEX = DATA_DIR / "story_summary.md"

# 远程仓库
REPO_OWNER = "littlepangding"
REPO_NAME = "arknights_lore_wiki"
REPO_BRANCH = "main"
GH_API = "https://api.github.com"
GH_RAW = "https://raw.githubusercontent.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/vnd.github.v3+json",
}

LOG_FILE = SCRIPTS_DIR / "lore_sync_log.txt"


def log(msg: str):
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{stamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ===================== GitHub API =====================

def github_api(path: str) -> Optional[dict]:
    """调用 GitHub API（GET 请求）。"""
    url = f"{GH_API}{path}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code == 200:
        return resp.json()
    log(f"  API 错误: {resp.status_code} {url}")
    return None


def list_repo_dir(dir_path: str) -> List[dict]:
    """列出仓库目录下所有文件（处理分页）。"""
    items = []
    url = f"{GH_API}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{dir_path}?ref={REPO_BRANCH}"
    while url:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            log(f"  列出目录失败: {resp.status_code} {dir_path}")
            break
        data = resp.json()
        if isinstance(data, list):
            items.extend(data)
        # 分页
        if "next" in resp.links:
            url = resp.links["next"]["url"]
        else:
            break
    return items


def download_file(github_path: str) -> Optional[str]:
    """下载单个文件的内容（UTF-8 文本）。

    优先使用 raw.githubusercontent.com（无 API 限流），
    失败时回退到 GitHub API。
    """
    # 方法 1: Raw URL（不限流）
    raw_url = f"{GH_RAW}/{REPO_OWNER}/{REPO_NAME}/{REPO_BRANCH}/{github_path}"
    resp = requests.get(raw_url, headers=HEADERS, timeout=30)
    if resp.status_code == 200:
        return resp.text

    # 方法 2: 回退到 API
    url = f"{GH_API}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{github_path}?ref={REPO_BRANCH}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code == 200:
        try:
            data = resp.json()
            return base64.b64decode(data["content"]).decode("utf-8")
        except Exception as e:
            log(f"  解码失败: {github_path}: {e}")
            return None

    log(f"  下载失败: {github_path} (HTTP {resp.status_code})")
    return None


# ===================== 清洗 =====================

def clean_wiki_md(content: str) -> str:
    """清洗从 arknights_lore_wiki 下载的 markdown 内容。

    移除：
      1. LLM 警告横幅（多行表格）
      2. 页面版本行
      3. wiki 内部链接 [name](link) → name
      4. v1 旧版本链接引用
      5. 多余空白
    """
    lines = content.split("\n")
    cleaned = []
    in_warning = False
    skip_until_empty = False

    for line in lines:
        # 跳过 LLM 警告横幅
        if "| :warning:" in line or "注意！本页面是利用LLM" in line:
            in_warning = True
            continue
        if in_warning:
            if "切勿当成一手来源" in line or "进行修改" in line:
                in_warning = False
            continue

        # 跳过页面版本行
        if line.strip().startswith("页面版本:"):
            continue

        cleaned.append(line)

    text = "\n".join(cleaned)

    # 移除 wiki 内部链接: [name](relative/path.md) → name
    text = re.sub(r"\[([^\]]+)\]\([^)]+\.md\)", r"\1", text)

    # 移除 v1 旧版本引用残留: ([v1](...)) 或 (v1)
    text = re.sub(r"\(\[v1\]\([^)]+\)\)", "", text)
    text = re.sub(r"\(v1\)", "", text)

    # 移除只含链接的残留（如 links to deleted characters）
    text = re.sub(r"\[([^\]]*)\]\([^)]+\)", r"\1", text)

    # 清理多余空行（最多保留一个连续空行）
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip() + "\n"


# ===================== 同步逻辑 =====================

def fetch_remote_names(dir_path: str) -> Set[str]:
    """获取远程仓库目录下所有 .md 文件名。"""
    items = list_repo_dir(dir_path)
    return {i["name"] for i in items if i["name"].endswith(".md")}


def get_local_names(local_dir: Path) -> Set[str]:
    """获取本地目录下所有 .md 文件名。"""
    if not local_dir.exists():
        return set()
    return {f for f in os.listdir(local_dir) if f.endswith(".md")}


def sync_files(
    remote_dir: str,
    local_dir: Path,
    dry_run: bool = False,
) -> Tuple[int, int]:
    """增量同步：下载远程有但本地没有的文件，清洗后保存。

    Returns:
        (downloaded_count, skipped_count)
    """
    local_dir.mkdir(parents=True, exist_ok=True)

    remote_names = fetch_remote_names(remote_dir)
    local_names = get_local_names(local_dir)

    new_names = sorted(remote_names - local_names)
    if not new_names:
        return 0, len(remote_names & local_names)

    for i, fname in enumerate(new_names):
        log(f"  [{i+1}/{len(new_names)}] + {fname}")
        if dry_run:
            continue

        remote_path = f"{remote_dir}/{fname}"
        content = download_file(remote_path)
        if content is None:
            log(f"    ✗ 下载失败")
            continue

        content = clean_wiki_md(content)
        local_path = local_dir / fname
        with open(local_path, "w", encoding="utf-8") as f:
            f.write(content)

        time.sleep(0.1)  # GitHub API 限速

    return len(new_names), len(remote_names & local_names)


def sync_index_file(remote_name: str, local_path: Path, dry_run: bool = False) -> bool:
    """替换式同步：下载远程 index 文件，清洗，覆盖本地。"""
    log(f"  替换索引: {remote_name} → {local_path.name}")
    if dry_run:
        return False

    content = download_file(f"docs/{remote_name}")
    if content is None:
        log(f"    ✗ 下载失败")
        return False

    content = clean_wiki_md(content)
    with open(local_path, "w", encoding="utf-8") as f:
        f.write(content)

    log(f"    ✓ {len(content)} 字符")
    return True


# ===================== 主入口 =====================

def sync_lore(dry_run: bool = False, full: bool = False) -> dict:
    """执行完整同步流程。"""
    log("=" * 60)
    log(f"剧情 Wiki 同步 {'(dry-run)' if dry_run else ''}{'(全量)' if full else '(增量)'}")

    result = {"stories": 0, "chars": 0, "indexes": 0}

    # --- 全量模式：只清空 operators（stories 保留增量）---
    if full and not dry_run:
        log("全量模式：清空 operators 目录...")
        if LOCAL_CHARS_DIR.exists():
            shutil.rmtree(LOCAL_CHARS_DIR)
        LOCAL_CHARS_DIR.mkdir(parents=True, exist_ok=True)
        log("  已清空 data/operators/")

    # --- 1. 剧情 ---
    log("\n[剧情] docs/stories/")
    new_stories, _ = sync_files("docs/stories", LOCAL_STORIES_DIR, dry_run)
    result["stories"] = new_stories
    log(f"  新增: {new_stories}")

    # --- 2. 角色 ---
    log("\n[角色] docs/char_v3/")
    new_chars, _ = sync_files("docs/char_v3", LOCAL_CHARS_DIR, dry_run)
    result["chars"] = new_chars
    log(f"  新增: {new_chars}")

    # --- 3. 索引（有新文件时替换，或全量时强制替换）---
    log("\n[索引]")
    has_changes = new_stories > 0 or new_chars > 0 or full

    if has_changes or full:
        if sync_index_file("story_index.md", LOCAL_STORY_INDEX, dry_run):
            result["indexes"] += 1
        if sync_index_file("char_index.md", LOCAL_CHAR_INDEX, dry_run):
            result["indexes"] += 1
    else:
        log("  无变化，跳过索引更新")

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="剧情 Wiki 增量同步")
    parser.add_argument("--dry-run", action="store_true", help="只检测，不下载")
    parser.add_argument("--full", action="store_true", help="全量更新（清空本地后重下所有）")
    args = parser.parse_args()

    if args.dry_run and args.full:
        print("不能同时使用 --dry-run 和 --full")
        sys.exit(1)

    result = sync_lore(dry_run=args.dry_run, full=args.full)

    if args.dry_run:
        print(f"\n检测完毕: +{result['stories']} 剧情, +{result['chars']} 角色")
    else:
        print(f"\n同步完毕: +{result['stories']} 剧情, +{result['chars']} 角色, {result['indexes']} 索引")

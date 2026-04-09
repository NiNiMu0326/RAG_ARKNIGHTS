import sys
import os
from pathlib import Path

# 设置当前目录为脚本所在目录（backend目录）
SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))
os.chdir(SCRIPT_DIR)

# 导入config
import config

# 从storage.index_manager导入
from storage.index_manager import IndexManager

print('=== Rebuilding ChromaDB vector indexes ===')
manager = IndexManager()
manager.build_all_indexes(force=True)
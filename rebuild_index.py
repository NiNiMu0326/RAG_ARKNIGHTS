import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
backend_dir = project_root / 'backend'
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(backend_dir))

# 从backend目录导入config
from backend import config

# 将config注入到sys.modules
sys.modules['config'] = config

# 现在导入IndexManager
from backend.storage.index_manager import IndexManager

print('=== Rebuilding ChromaDB vector indexes (force) ===')
manager = IndexManager()
manager.build_all_indexes(force=True)
import sqlite3
from pathlib import Path

db_path = Path(r"c:\Users\22859\Desktop\astra-main\backend\data\sessions.db")
print(f"DB exists: {db_path.exists()}")
if db_path.exists():
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    
    # Check if agent_configs table exists
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print(f"Tables: {[t['name'] for t in tables]}")
    
    if 'agent_configs' in [t['name'] for t in tables]:
        rows = conn.execute("SELECT * FROM agent_configs").fetchall()
        print(f"Agent configs count: {len(rows)}")
        for r in rows:
            print(f"  - {r['id']}: {r['name']} (enabled={r['enabled']})")
    else:
        print("agent_configs table does NOT exist")
    
    conn.close()
else:
    print("数据库文件不存在，需要启动后端来创建")

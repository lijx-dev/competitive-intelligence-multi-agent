"""SQLite数据库操作封装，竞品管理、历史分析数据持久化"""
from __future__ import annotations
import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

# 数据库文件路径（放在python目录下，自动生成）
DB_PATH = "ci_system.db"

# ------------------------------
# 数据库初始化（自动建表）
# ------------------------------
def init_db():
    """初始化数据库，创建所需表，启动服务时自动执行"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()

    # 1. 竞品库表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS competitors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,  -- 竞品名称，唯一约束
        urls TEXT NOT NULL,          -- 监控URL，JSON数组格式存储
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    ''')

    # 2. 历史分析记录表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS analysis_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        competitor_id INTEGER,          -- 关联竞品ID
        competitor_name TEXT NOT NULL,  -- 竞品名称
        request_urls TEXT,              -- 本次分析的URL，JSON数组
        analysis_result TEXT NOT NULL,  -- 完整分析结果，JSON格式
        quality_score REAL DEFAULT 0.0, -- 质量评分
        created_at TEXT NOT NULL,
        FOREIGN KEY (competitor_id) REFERENCES competitors (id)
    )
    ''')

    # 3. 系统配置表（key-value + JSON value + 更新时间）
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS system_config (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL DEFAULT '{}',
        updated_at TEXT NOT NULL
    )
    ''')

    # 4. 配置版本历史表（支持回滚）
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS config_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        config_key TEXT NOT NULL,
        value TEXT NOT NULL,
        version INTEGER NOT NULL,
        created_at TEXT NOT NULL
    )
    ''')

    conn.commit()
    conn.close()

# ------------------------------
# 竞品库CRUD操作
# ------------------------------
def create_competitor(name: str, urls: List[str]) -> Dict[str, Any]:
    """新增竞品"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()

    try:
        cursor.execute(
            'INSERT INTO competitors (name, urls, created_at, updated_at) VALUES (?, ?, ?, ?)',
            (name, json.dumps(urls, ensure_ascii=False), now, now)
        )
        conn.commit()
        # 获取新增的竞品ID
        competitor_id = cursor.lastrowid
        return {
            "id": competitor_id,
            "name": name,
            "urls": urls,
            "created_at": now,
            "updated_at": now
        }
    except sqlite3.IntegrityError:
        raise ValueError(f"竞品【{name}】已存在，请勿重复添加")
    finally:
        conn.close()

def get_all_competitors() -> List[Dict[str, Any]]:
    """获取所有竞品列表"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, urls, created_at, updated_at FROM competitors ORDER BY created_at DESC')
    rows = cursor.fetchall()
    conn.close()

    # 格式化返回
    result = []
    for row in rows:
        result.append({
            "id": row[0],
            "name": row[1],
            "urls": json.loads(row[2]),
            "created_at": row[3],
            "updated_at": row[4]
        })
    return result

def get_competitor_by_id(competitor_id: int) -> Optional[Dict[str, Any]]:
    """根据ID获取竞品详情"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, urls, created_at, updated_at FROM competitors WHERE id = ?', (competitor_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None
    return {
        "id": row[0],
        "name": row[1],
        "urls": json.loads(row[2]),
        "created_at": row[3],
        "updated_at": row[4]
    }

def update_competitor(competitor_id: int, name: str, urls: List[str]) -> Dict[str, Any]:
    """更新竞品信息"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()

    cursor.execute(
        'UPDATE competitors SET name = ?, urls = ?, updated_at = ? WHERE id = ?',
        (name, json.dumps(urls, ensure_ascii=False), now, competitor_id)
    )
    conn.commit()
    conn.close()

    if cursor.rowcount == 0:
        raise ValueError(f"ID为{competitor_id}的竞品不存在")
    return {
        "id": competitor_id,
        "name": name,
        "urls": urls,
        "updated_at": now
    }

def delete_competitor(competitor_id: int):
    """删除竞品"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM competitors WHERE id = ?', (competitor_id,))
    conn.commit()
    conn.close()

    if cursor.rowcount == 0:
        raise ValueError(f"ID为{competitor_id}的竞品不存在")

# ------------------------------
# 历史分析记录操作
# ------------------------------
def create_analysis_record(
    competitor_id: Optional[int],
    competitor_name: str,
    request_urls: List[str],
    analysis_result: Dict[str, Any],
    quality_score: float
) -> int:
    """新增分析记录，每次分析完成后自动调用"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()

    cursor.execute(
        '''INSERT INTO analysis_records 
        (competitor_id, competitor_name, request_urls, analysis_result, quality_score, created_at) 
        VALUES (?, ?, ?, ?, ?, ?)''',
        (
            competitor_id,
            competitor_name,
            json.dumps(request_urls, ensure_ascii=False),
            json.dumps(analysis_result, ensure_ascii=False),
            quality_score,
            now
        )
    )
    conn.commit()
    record_id = cursor.lastrowid
    conn.close()
    return record_id

def get_all_analysis_records(competitor_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """获取所有分析记录，可按竞品ID筛选"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()

    if competitor_id:
        cursor.execute(
            'SELECT id, competitor_id, competitor_name, request_urls, analysis_result, quality_score, created_at FROM analysis_records WHERE competitor_id = ? ORDER BY created_at DESC',
            (competitor_id,)
        )
    else:
        cursor.execute(
            'SELECT id, competitor_id, competitor_name, request_urls, analysis_result, quality_score, created_at FROM analysis_records ORDER BY created_at DESC'
        )

    rows = cursor.fetchall()
    conn.close()

    # 格式化返回
    result = []
    for row in rows:
        result.append({
            "id": row[0],
            "competitor_id": row[1],
            "competitor_name": row[2],
            "request_urls": json.loads(row[3]),
            "analysis_result": json.loads(row[4]),
            "quality_score": row[5],
            "created_at": row[6]
        })
    return result

def get_analysis_record_by_id(record_id: int) -> Optional[Dict[str, Any]]:
    """根据ID获取分析记录详情"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, competitor_id, competitor_name, request_urls, analysis_result, quality_score, created_at FROM analysis_records WHERE id = ?',
        (record_id,)
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None
    return {
        "id": row[0],
        "competitor_id": row[1],
        "competitor_name": row[2],
        "request_urls": json.loads(row[3]),
        "analysis_result": json.loads(row[4]),
        "quality_score": row[5],
        "created_at": row[6]
    }


# ============================================================
# 系统配置 CRUD（动态配置管理 + 版本历史 + 导入导出）
# ============================================================

def get_all_config() -> Dict[str, Any]:
    """获取所有系统配置，返回 key -> value 字典"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT key, value, updated_at FROM system_config ORDER BY key')
    rows = cursor.fetchall()
    conn.close()
    result = {}
    for row in rows:
        try:
            result[row[0]] = {"value": json.loads(row[1]), "updated_at": row[2]}
        except json.JSONDecodeError:
            result[row[0]] = {"value": row[1], "updated_at": row[2]}
    return result


def get_config_value(key: str, default: Any = None) -> Any:
    """获取单个配置项的值，不存在时返回 default"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM system_config WHERE key = ?', (key,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return default
    try:
        return json.loads(row[0])
    except json.JSONDecodeError:
        return row[0]


def set_config_value(key: str, value: Any, record_history: bool = True) -> Dict[str, Any]:
    """设置单个配置项的值，自动记录版本历史"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    value_json = json.dumps(value, ensure_ascii=False)

    # 记录版本历史
    if record_history:
        cursor.execute(
            'SELECT COALESCE(MAX(version), 0) + 1 FROM config_history WHERE config_key = ?',
            (key,)
        )
        next_version = cursor.fetchone()[0]
        cursor.execute(
            'INSERT INTO config_history (config_key, value, version, created_at) VALUES (?, ?, ?, ?)',
            (key, value_json, next_version, now)
        )

    # UPSERT system_config
    conn.execute(
        'INSERT OR REPLACE INTO system_config (key, value, updated_at) VALUES (?, ?, ?)',
        (key, value_json, now)
    )
    conn.commit()
    conn.close()
    return {"key": key, "value": value, "updated_at": now}


def batch_set_config(config_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
    """批量设置配置项"""
    results = []
    for key, value in config_dict.items():
        results.append(set_config_value(key, value))
    return results


def get_config_history(key: Optional[str] = None) -> List[Dict[str, Any]]:
    """获取配置版本历史，可按 key 筛选"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    if key:
        cursor.execute(
            'SELECT id, config_key, value, version, created_at FROM config_history WHERE config_key = ? ORDER BY version DESC',
            (key,)
        )
    else:
        cursor.execute(
            'SELECT id, config_key, value, version, created_at FROM config_history ORDER BY config_key, version DESC'
        )
    rows = cursor.fetchall()
    conn.close()
    result = []
    for row in rows:
        try:
            val = json.loads(row[2])
        except json.JSONDecodeError:
            val = row[2]
        result.append({
            "id": row[0],
            "config_key": row[1],
            "value": val,
            "version": row[2],
            "created_at": row[3],
        })
    return result


def rollback_config(key: str, version: int) -> Dict[str, Any]:
    """回滚指定配置项到某个历史版本"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT value FROM config_history WHERE config_key = ? AND version = ?',
        (key, version)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise ValueError(f"配置项 {key} 版本 {version} 不存在")
    try:
        old_value = json.loads(row[0])
    except json.JSONDecodeError:
        old_value = row[0]
    # 回滚也记录历史
    return set_config_value(key, old_value, record_history=True)


def export_config() -> Dict[str, Any]:
    """导出全部配置为 JSON 兼容字典"""
    return {
        "exported_at": datetime.utcnow().isoformat(),
        "configs": get_all_config(),
    }


def import_config(data: Dict[str, Any]) -> int:
    """从导出的 JSON 导入配置，返回导入的配置项数量"""
    configs = data.get("configs", {})
    count = 0
    for key, item in configs.items():
        value = item.get("value", item) if isinstance(item, dict) else item
        set_config_value(key, value, record_history=True)
        count += 1
    return count


def get_db_stats() -> Dict[str, Any]:
    """获取数据库统计信息"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM competitors')
    competitor_count = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM analysis_records')
    analysis_count = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM system_config')
    config_count = cursor.fetchone()[0]
    conn.close()
    return {
        "competitor_count": competitor_count,
        "analysis_count": analysis_count,
        "config_count": config_count,
    }
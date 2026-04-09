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
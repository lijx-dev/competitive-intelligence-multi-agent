"""SQLite数据库操作封装，竞品管理、历史分析数据持久化"""
from __future__ import annotations
import sqlite3
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# 数据库文件路径（放在python目录下，自动生成）
DB_PATH = "ci_system.db"

# ── SQL 注入防护：表名 + 配置键白名单 ──
ALLOWED_SQL_TABLE_NAMES: set[str] = {
    "competitors", "analysis_records", "system_config", "config_history",
    "our_product", "feedback_records", "analysis_snapshots",
    "evolution_feedback", "template_performance", "agent_traces",
}
ALLOWED_CONFIG_KEYS: set[str] = {"llm", "notification", "alert", "pipeline"}


def _validate_safe_table_name(name: str) -> str:
    if name not in ALLOWED_SQL_TABLE_NAMES:
        raise ValueError(f"table name not in whitelist: {name}")
    return name


def _validate_safe_config_key(key: str) -> str:
    parts = key.split(".")
    if parts[0] not in ALLOWED_CONFIG_KEYS:
        raise ValueError(f"config key prefix not allowed: {key}")
    return key

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

    # 5. 我方产品信息表（单行：存储我方产品的结构化信息）
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS our_product (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        name TEXT NOT NULL DEFAULT 'My Product',
        core_features TEXT NOT NULL DEFAULT '[]',
        pricing_model TEXT NOT NULL DEFAULT '订阅制',
        tech_stack TEXT NOT NULL DEFAULT '[]',
        target_market TEXT NOT NULL DEFAULT '',
        competitive_advantages TEXT NOT NULL DEFAULT '[]',
        weaknesses TEXT NOT NULL DEFAULT '[]',
        updated_at TEXT NOT NULL
    )
    ''')
    # 确保始终存在一行（id=1 的单行约束）
    cursor.execute('''
    INSERT OR IGNORE INTO our_product (id, name, core_features, pricing_model, tech_stack, target_market, competitive_advantages, weaknesses, updated_at)
    VALUES (1, 'My Product', '[]', '订阅制', '[]', '', '[]', '[]', datetime('now'))
    ''')
    # ★ 首次启动时自动预置「字节跳动 抖音电商」完整基准数据
    # 如果 core_features 仍为空（首次安装/数据被清空），自动填充
    cursor.execute("SELECT core_features FROM our_product WHERE id = 1")
    row = cursor.fetchone()
    if row and (not row[0] or row[0] == '[]'):
        import json as _json
        baseline = {
            "name": "字节跳动 抖音电商",
            "core_features": _json.dumps([
                "AI驱动的内容推荐引擎（豆包大模型）",
                "千川智能广告投放系统",
                "品牌自播工具套装（直播+短视频+图文）",
                "达人撮合平台（星图）",
                "即时零售（小时达）",
                "抖店商家后台（数据分析+经营诊断）",
                "抖音商城（货架电商入口）",
                "飞书集成（企业协同+客户管理）"
            ], ensure_ascii=False),
            "pricing_model": "佣金制 3-8% + 广告费（千川竞价）",
            "tech_stack": _json.dumps([
                "豆包大模型（Seed 2.0）", "火山引擎推荐系统",
                "即梦AI（视频/图片生成）", "云原生基础设施（ByteSail）",
                "实时数据管道（Kafka+Flink）", "A/B实验平台（Libra）"
            ], ensure_ascii=False),
            "target_market": "全球品牌商家 + 内容创作者 + 本地生活服务商",
            "competitive_advantages": _json.dumps([
                "7亿+ DAU 流量规模，全球领先",
                "AI推荐算法全球第一梯队，转化率行业标杆",
                "内容-电商-本地生活超级APP生态闭环",
                "豆包+即梦AI创作工具矩阵，AIGC能力溢出",
                "品牌商家100万+，覆盖头部国际品牌到新锐国货",
                "飞书+火山引擎提供企业服务协同"
            ], ensure_ascii=False),
            "weaknesses": _json.dumps([
                "流量成本持续攀升，中小商家获客压力大",
                "下沉市场渗透不足（三四线城市占比低于快手10%）",
                "跨境电商起步晚，海外物流仓储能力待建",
                "社区黏性弱于快手（粉丝复购率低15%）",
                "AI供应链和物流AI布局几乎空白",
                "AI客服与对话系统起步晚，电商场景专业度不足"
            ], ensure_ascii=False),
        }
        cursor.execute(
            """UPDATE our_product SET
               name = ?, core_features = ?, pricing_model = ?, tech_stack = ?,
               target_market = ?, competitive_advantages = ?, weaknesses = ?,
               updated_at = datetime('now')
               WHERE id = 1""",
            (baseline["name"], baseline["core_features"], baseline["pricing_model"],
             baseline["tech_stack"], baseline["target_market"],
             baseline["competitive_advantages"], baseline["weaknesses"])
        )
        logger.info("我方产品基准数据已自动预置：字节跳动 抖音电商（8项核心功能+6项优势+6项劣势）")

    # 6. 飞书反馈记录表（人类反馈 → 自进化闭环）
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS feedback_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_id TEXT NOT NULL,
        action TEXT NOT NULL,
        comment TEXT DEFAULT '',
        operator TEXT DEFAULT 'unknown',
        created_at TEXT NOT NULL
    )
    ''')

    # 7. 进化分析快照表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS analysis_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        competitor TEXT NOT NULL,
        dimension TEXT NOT NULL DEFAULT '',
        agent_name TEXT NOT NULL,
        finding TEXT NOT NULL DEFAULT '',
        confidence REAL NOT NULL DEFAULT 0.5,
        template_id TEXT NOT NULL DEFAULT '',
        quality_score REAL DEFAULT 0.0,
        human_verified INTEGER DEFAULT 0,
        feedback_count INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    )
    ''')

    # 8. 进化反馈记录表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS evolution_feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_id INTEGER,
        action TEXT NOT NULL,
        comment TEXT DEFAULT '',
        old_confidence REAL DEFAULT 0.0,
        new_confidence REAL DEFAULT 0.0,
        operator TEXT DEFAULT 'unknown',
        created_at TEXT NOT NULL,
        FOREIGN KEY (snapshot_id) REFERENCES analysis_snapshots(id)
    )
    ''')

    # 9. 模板表现跟踪表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS template_performance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_name TEXT NOT NULL,
        template_id TEXT NOT NULL,
        template_desc TEXT DEFAULT '',
        performance_score REAL DEFAULT 0.5,
        usage_count INTEGER DEFAULT 0,
        success_count INTEGER DEFAULT 0,
        updated_at TEXT NOT NULL,
        UNIQUE(agent_name, template_id)
    )
    ''')

    # 10. Agent Trace 全链路埋点表（2.1 可观测性核心）
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS agent_traces (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trace_id TEXT UNIQUE NOT NULL,
        pipeline_run_id TEXT NOT NULL,
        agent_name TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT,
        prompt_snapshot TEXT NOT NULL DEFAULT '',
        input_state_json TEXT NOT NULL DEFAULT '{}',
        llm_raw_response TEXT,
        parsed_output_json TEXT,
        token_usage_input INTEGER DEFAULT 0,
        token_usage_output INTEGER DEFAULT 0,
        error_message TEXT,
        duration_ms INTEGER DEFAULT 0
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

    # 先获取 created_at 以便完整返回
    cursor.execute('SELECT created_at FROM competitors WHERE id = ?', (competitor_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"ID为{competitor_id}的竞品不存在")

    created_at = row[0]
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
        "created_at": created_at,
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
    """从导出的 JSON 导入配置，返回导入的配置项数量。
    仅允许 ALLOWED_CONFIG_KEYS 中的键，防止恶意配置覆盖。"""
    configs = data.get("configs", {})
    count = 0
    for key, item in configs.items():
        # 安全校验：只允许白名单中的配置键
        _validate_safe_config_key(key)
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


# ============================================================
# 我方产品信息 CRUD（单行表，id 固定为 1）
# ============================================================

OUR_PRODUCT_COLS = [
    "name", "core_features", "pricing_model", "tech_stack",
    "target_market", "competitive_advantages", "weaknesses",
]


def get_our_product() -> Dict[str, Any]:
    """获取我方产品信息，JSON 字段自动反序列化为 list/dict"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(f'''SELECT {", ".join(OUR_PRODUCT_COLS)}, updated_at FROM our_product WHERE id = 1''')
    row = cursor.fetchone()
    conn.close()
    if not row:
        return {col: [] if col in ("core_features", "tech_stack", "competitive_advantages", "weaknesses") else "" for col in OUR_PRODUCT_COLS}
    result = {"updated_at": row[-1]}
    for i, col in enumerate(OUR_PRODUCT_COLS):
        val = row[i]
        if col in ("core_features", "tech_stack", "competitive_advantages", "weaknesses"):
            try:
                result[col] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                result[col] = []
        else:
            result[col] = val or ""
    return result


def update_our_product(data: Dict[str, Any]) -> Dict[str, Any]:
    """更新我方产品信息，JSON 字段自动序列化"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    now = datetime.utcnow().isoformat()
    sets = []
    values = []
    for col in OUR_PRODUCT_COLS:
        if col in data:
            val = data[col]
            if isinstance(val, list):
                val = json.dumps(val, ensure_ascii=False)
            sets.append(f"{col} = ?")
            values.append(val)
    sets.append("updated_at = ?")
    values.append(now)
    values.append(1)  # WHERE id = 1
    cursor = conn.cursor()
    cursor.execute(f"UPDATE our_product SET {', '.join(sets)} WHERE id = ?", values)
    conn.commit()
    conn.close()
    return get_our_product()


# ============================================================
# 飞书反馈记录 CRUD（M6 自进化数据源）
# ============================================================

def create_feedback_record(
    report_id: str,
    action: str,
    comment: str = "",
    operator: str = "unknown",
) -> Dict[str, Any]:
    """记录一条人类反馈"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    now = datetime.utcnow().isoformat()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO feedback_records (report_id, action, comment, operator, created_at) VALUES (?, ?, ?, ?, ?)',
        (report_id, action, comment, operator, now),
    )
    conn.commit()
    fid = cursor.lastrowid
    conn.close()
    return {
        "id": fid,
        "report_id": report_id,
        "action": action,
        "comment": comment,
        "operator": operator,
        "created_at": now,
    }


def get_feedback_records(report_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """获取反馈记录，可按 report_id 筛选"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    if report_id:
        cursor.execute(
            'SELECT id, report_id, action, comment, operator, created_at FROM feedback_records WHERE report_id = ? ORDER BY created_at DESC',
            (report_id,),
        )
    else:
        cursor.execute(
            'SELECT id, report_id, action, comment, operator, created_at FROM feedback_records ORDER BY created_at DESC',
        )
    rows = cursor.fetchall()
    conn.close()
    return [{
        "id": r[0], "report_id": r[1], "action": r[2],
        "comment": r[3], "operator": r[4], "created_at": r[5],
    } for r in rows]


# ============================================================
# 进化引擎 CRUD（analysis_snapshots / evolution_feedback / template_performance）
# ============================================================

def create_analysis_snapshot(
    competitor: str,
    agent_name: str,
    finding: str = "",
    confidence: float = 0.5,
    dimension: str = "",
    template_id: str = "",
    quality_score: float = 0.0,
) -> Dict[str, Any]:
    """保存一次分析快照"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute(
        """INSERT INTO analysis_snapshots
           (competitor, dimension, agent_name, finding, confidence, template_id, quality_score, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (competitor, dimension, agent_name, finding[:2000], confidence, template_id, quality_score, now),
    )
    conn.commit()
    sid = cursor.lastrowid
    conn.close()
    return {
        "id": sid, "competitor": competitor, "dimension": dimension,
        "agent_name": agent_name, "confidence": confidence,
        "template_id": template_id, "created_at": now,
    }


def get_snapshot_by_key(
    competitor: str = "", dimension: str = "", agent_name: str = "",
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """按 竞品+维度+Agent 查询分析快照历史"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    clauses = []
    params: List[Any] = []
    if competitor:
        clauses.append("competitor = ?"); params.append(competitor)
    if dimension:
        clauses.append("dimension = ?"); params.append(dimension)
    if agent_name:
        clauses.append("agent_name = ?"); params.append(agent_name)
    where = " AND ".join(clauses) if clauses else "1=1"
    cursor.execute(
        f"SELECT id, competitor, dimension, agent_name, finding, confidence, template_id, quality_score, human_verified, feedback_count, created_at FROM analysis_snapshots WHERE {where} ORDER BY created_at DESC LIMIT ?",
        params + [limit],
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": r[0], "competitor": r[1], "dimension": r[2],
            "agent_name": r[3], "finding": r[4], "confidence": r[5],
            "template_id": r[6], "quality_score": r[7],
            "human_verified": bool(r[8]), "feedback_count": r[9],
            "created_at": r[10],
        }
        for r in rows
    ]


def create_evolution_feedback(
    snapshot_id: int,
    action: str,
    old_confidence: float = 0.0,
    new_confidence: float = 0.0,
    comment: str = "",
    operator: str = "unknown",
) -> Dict[str, Any]:
    """记录一条进化反馈"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute(
        """INSERT INTO evolution_feedback (snapshot_id, action, comment, old_confidence, new_confidence, operator, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (snapshot_id, action, comment, old_confidence, new_confidence, operator, now),
    )
    conn.commit()
    fid = cursor.lastrowid
    # 同步更新快照的验证状态
    cursor.execute(
        "UPDATE analysis_snapshots SET human_verified = 1, feedback_count = feedback_count + 1 WHERE id = ?",
        (snapshot_id,),
    )
    conn.commit()
    conn.close()
    return {"id": fid, "snapshot_id": snapshot_id, "action": action, "created_at": now}


def get_feedback_stats() -> Dict[str, Any]:
    """反馈统计：总数、确认/纠正比例、按日期准确率趋势"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM evolution_feedback")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT action, COUNT(*) FROM evolution_feedback GROUP BY action")
    by_action = {r[0]: r[1] for r in cursor.fetchall()}
    confirm = by_action.get("confirm", 0)

    cursor.execute(
        "SELECT DATE(created_at) as d, COUNT(*) as cnt, "
        "SUM(CASE WHEN action='confirm' THEN 1 ELSE 0 END) as confirms "
        "FROM evolution_feedback GROUP BY d ORDER BY d DESC LIMIT 30"
    )
    trend = [
        {"date": r[0], "total": r[1], "confirms": r[2],
         "accuracy": round(r[2] / max(r[1], 1), 3)}
        for r in cursor.fetchall()
    ]
    conn.close()
    return {
        "total_feedback": total,
        "confirm_count": confirm,
        "correct_count": by_action.get("correct", 0),
        "accuracy": round(confirm / max(total, 1), 3),
        "trend": trend,
    }


def update_template_score(
    agent_name: str,
    template_id: str,
    performance_score: float,
    usage_count: int = 0,
    success_count: int = 0,
    template_desc: str = "",
) -> Dict[str, Any]:
    """更新或插入模板评分"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute(
        """INSERT INTO template_performance (agent_name, template_id, template_desc, performance_score, usage_count, success_count, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(agent_name, template_id) DO UPDATE SET
             performance_score = excluded.performance_score,
             usage_count = template_performance.usage_count + excluded.usage_count,
             success_count = template_performance.success_count + excluded.success_count,
             updated_at = excluded.updated_at""",
        (agent_name, template_id, template_desc, performance_score, usage_count, success_count, now),
    )
    conn.commit()
    conn.close()
    return {"agent_name": agent_name, "template_id": template_id, "score": performance_score}


def get_template_ranking() -> List[Dict[str, Any]]:
    """获取全部模板评分排行"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT agent_name, template_id, template_desc, performance_score, usage_count, success_count, updated_at "
        "FROM template_performance ORDER BY performance_score DESC"
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "agent_name": r[0], "template_id": r[1], "template_desc": r[2],
            "performance_score": r[3], "usage_count": r[4],
            "success_count": r[5], "updated_at": r[6],
        }
        for r in rows
    ]


# ============================================================
# Agent Trace CRUD（2.1 全链路埋点持久化）
# ============================================================

def create_agent_trace(
    trace_id: str,
    pipeline_run_id: str,
    agent_name: str,
    start_time: str = "",
    end_time: str = "",
    prompt_snapshot: str = "",
    input_state_json: str = "{}",
    llm_raw_response: str = "",
    parsed_output_json: str = "",
    token_usage_input: int = 0,
    token_usage_output: int = 0,
    error_message: str = "",
    duration_ms: int = 0,
) -> Dict[str, Any]:
    """写入一条 Agent Trace 记录"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    if not start_time:
        start_time = now
    cursor.execute(
        """INSERT INTO agent_traces
           (trace_id, pipeline_run_id, agent_name, start_time, end_time,
            prompt_snapshot, input_state_json, llm_raw_response,
            parsed_output_json, token_usage_input, token_usage_output,
            error_message, duration_ms)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (trace_id, pipeline_run_id, agent_name, start_time, end_time or now,
         prompt_snapshot, input_state_json, llm_raw_response,
         parsed_output_json, token_usage_input, token_usage_output,
         error_message, duration_ms),
    )
    conn.commit()
    trace_pk = cursor.lastrowid
    conn.close()
    return {"id": trace_pk, "trace_id": trace_id, "agent_name": agent_name}


def get_trace_by_id(trace_id: str) -> Optional[Dict[str, Any]]:
    """根据 trace_id 获取完整的 Agent Trace 详情"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, trace_id, pipeline_run_id, agent_name, start_time, end_time, "
        "prompt_snapshot, input_state_json, llm_raw_response, parsed_output_json, "
        "token_usage_input, token_usage_output, error_message, duration_ms "
        "FROM agent_traces WHERE trace_id = ?",
        (trace_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0], "trace_id": row[1], "pipeline_run_id": row[2],
        "agent_name": row[3], "start_time": row[4], "end_time": row[5],
        "prompt_snapshot": row[6], "input_state_json": row[7],
        "llm_raw_response": row[8], "parsed_output_json": row[9],
        "token_usage_input": row[10], "token_usage_output": row[11],
        "error_message": row[12], "duration_ms": row[13],
    }


def get_traces_by_pipeline(pipeline_run_id: str) -> List[Dict[str, Any]]:
    """获取某个 Pipeline 运行的所有 Agent Trace 记录"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, trace_id, pipeline_run_id, agent_name, start_time, end_time, "
        "token_usage_input, token_usage_output, error_message, duration_ms "
        "FROM agent_traces WHERE pipeline_run_id = ? ORDER BY start_time ASC",
        (pipeline_run_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": r[0], "trace_id": r[1], "pipeline_run_id": r[2],
            "agent_name": r[3], "start_time": r[4], "end_time": r[5],
            "token_usage_input": r[6], "token_usage_output": r[7],
            "error_message": r[8], "duration_ms": r[9],
        }
        for r in rows
    ]


def get_trace_stats() -> Dict[str, Any]:
    """获取 Agent Trace 统计信息（Token 总消耗、平均延迟等）"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM agent_traces")
    total_traces = cursor.fetchone()[0]
    cursor.execute(
        "SELECT agent_name, COUNT(*) as cnt, "
        "SUM(token_usage_input) as tot_in, SUM(token_usage_output) as tot_out, "
        "AVG(duration_ms) as avg_dur "
        "FROM agent_traces GROUP BY agent_name ORDER BY cnt DESC"
    )
    by_agent = [
        {
            "agent_name": r[0], "trace_count": r[1],
            "total_input_tokens": r[2] or 0, "total_output_tokens": r[3] or 0,
            "avg_duration_ms": round(r[4] or 0, 1),
        }
        for r in cursor.fetchall()
    ]
    conn.close()
    return {"total_traces": total_traces, "by_agent": by_agent}
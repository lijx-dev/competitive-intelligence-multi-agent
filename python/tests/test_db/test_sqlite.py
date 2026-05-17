"""
test_sqlite.py —— SQLite 数据库操作测试。

覆盖：自动建表、竞品 CRUD、名称唯一约束、历史记录 CRUD、按竞品筛选记录。
使用 monkeypatch 将 DB_PATH 重定向到临时文件，不影响真实数据。
"""

import json
import os
import pytest
import sqlite3
from src.db import sqlite as db_module


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    """每个测试使用独立的临时数据库文件。"""
    db_path = str(tmp_path / "test_ci.db")
    monkeypatch.setattr(db_module, "DB_PATH", db_path)
    db_module.init_db()
    yield db_path
    # 清理
    if os.path.exists(db_path):
        os.remove(db_path)


# ==================== 初始化 ====================

def test_init_db_creates_tables():
    """init_db 创建 competitors 和 analysis_records 两张表。"""
    conn = sqlite3.connect(db_module.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    assert "competitors" in tables
    assert "analysis_records" in tables


# ==================== 竞品 CRUD ====================

def test_create_competitor_success(sample_competitor):
    """新增竞品返回完整记录（含 id、时间戳）。"""
    result = db_module.create_competitor(**sample_competitor)
    assert result["id"] == 1
    assert result["name"] == sample_competitor["name"]
    assert result["urls"] == sample_competitor["urls"]
    assert "created_at" in result
    assert "updated_at" in result


def test_create_competitor_duplicate_name(sample_competitor):
    """竞品名称唯一约束：重复名称抛出 ValueError。"""
    db_module.create_competitor(**sample_competitor)
    with pytest.raises(ValueError, match="已存在"):
        db_module.create_competitor(**sample_competitor)


def test_get_all_competitors(sample_competitor):
    """get_all_competitors 返回全部竞品，按时间倒序。"""
    db_module.create_competitor(name="Comp A", urls=["https://a.com"])
    db_module.create_competitor(**sample_competitor)
    result = db_module.get_all_competitors()
    assert len(result) == 2
    # 按 created_at DESC 排序，后创建的在前
    assert result[0]["name"] == sample_competitor["name"]


def test_get_competitor_by_id(sample_competitor):
    """按 ID 查询竞品详情；不存在的 ID 返回 None。"""
    db_module.create_competitor(**sample_competitor)
    found = db_module.get_competitor_by_id(1)
    assert found is not None
    assert found["name"] == sample_competitor["name"]
    not_found = db_module.get_competitor_by_id(999)
    assert not_found is None


def test_update_competitor(sample_competitor):
    """更新竞品名称和 URL 后返回最新数据。"""
    db_module.create_competitor(**sample_competitor)
    updated = db_module.update_competitor(1, name="New Name", urls=["https://new.com"])
    assert updated["name"] == "New Name"
    assert updated["urls"] == ["https://new.com"]
    # 验证持久化
    row = db_module.get_competitor_by_id(1)
    assert row["name"] == "New Name"


def test_update_nonexistent_competitor():
    """更新不存在的 ID 抛出 ValueError。"""
    with pytest.raises(ValueError, match="不存在"):
        db_module.update_competitor(999, name="X", urls=[])


def test_delete_competitor(sample_competitor):
    """删除竞品后 get_all 不再包含该记录。"""
    db_module.create_competitor(**sample_competitor)
    db_module.create_competitor(name="Comp B", urls=["https://b.com"])
    db_module.delete_competitor(1)
    remaining = db_module.get_all_competitors()
    assert len(remaining) == 1
    assert remaining[0]["name"] == "Comp B"


def test_delete_nonexistent_competitor():
    """删除不存在的 ID 抛出 ValueError。"""
    with pytest.raises(ValueError, match="不存在"):
        db_module.delete_competitor(999)


# ==================== 历史分析记录 CRUD ====================

def test_create_and_get_analysis_records(sample_battlecard):
    """创建分析记录后可通过 get_all_analysis_records 获取。"""
    record_id = db_module.create_analysis_record(
        competitor_id=None,
        competitor_name="TestComp",
        request_urls=["https://test.com"],
        analysis_result=sample_battlecard,
        quality_score=9.2,
    )
    assert record_id == 1
    records = db_module.get_all_analysis_records()
    assert len(records) == 1
    assert records[0]["competitor_name"] == "TestComp"
    assert records[0]["quality_score"] == 9.2
    assert records[0]["analysis_result"]["competitor"] == "Acme Corp"


def test_get_analysis_record_by_id():
    """按 ID 查询分析记录详情；不存在的 ID 返回 None。"""
    db_module.create_analysis_record(
        competitor_id=None, competitor_name="X", request_urls=[],
        analysis_result={"key": "val"}, quality_score=8.0,
    )
    found = db_module.get_analysis_record_by_id(1)
    assert found is not None
    assert found["competitor_name"] == "X"
    not_found = db_module.get_analysis_record_by_id(999)
    assert not_found is None


def test_filter_records_by_competitor_id():
    """get_all_analysis_records 可按 competitor_id 筛选。"""
    db_module.create_analysis_record(
        competitor_id=1, competitor_name="CompA", request_urls=[],
        analysis_result={}, quality_score=7.0,
    )
    db_module.create_analysis_record(
        competitor_id=2, competitor_name="CompB", request_urls=[],
        analysis_result={}, quality_score=8.0,
    )
    filtered = db_module.get_all_analysis_records(competitor_id=1)
    assert len(filtered) == 1
    assert filtered[0]["competitor_name"] == "CompA"


def test_analysis_record_with_null_competitor_id():
    """competitor_id 可以为 NULL（竞品未入库时的分析）。"""
    db_module.create_analysis_record(
        competitor_id=None, competitor_name="External", request_urls=[],
        analysis_result={}, quality_score=5.0,
    )
    records = db_module.get_all_analysis_records()
    assert len(records) == 1
    assert records[0]["competitor_id"] is None

"""
test_web_scraper.py —— 网页抓取工具测试。

覆盖：SHA-256 Hash 计算、HTML 文本提取、定价信息抽取、招聘列表抽取。
不发起真实 HTTP 请求（使用本地 HTML 字符串）。
"""

import hashlib
import pytest
from src.tools.web_scraper import content_hash, extract_text, extract_pricing, extract_job_listings


# ==================== content_hash ====================

def test_content_hash_consistency():
    """相同内容产生相同 Hash。"""
    text = "Hello World"
    assert content_hash(text) == content_hash(text)


def test_content_hash_difference():
    """不同内容产生不同 Hash。"""
    h1 = content_hash("Hello")
    h2 = content_hash("World")
    assert h1 != h2


def test_content_hash_is_sha256_hex():
    """返回值是 64 位十六进制 SHA-256 摘要。"""
    digest = content_hash("test")
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)
    # 与标准 hashlib 结果一致
    expected = hashlib.sha256(b"test").hexdigest()
    assert digest == expected


# ==================== extract_text ====================

def test_extract_text_strips_tags():
    """extract_text 去除 HTML 标签，仅返回可见文本。"""
    html = "<html><body><h1>Title</h1><p>Paragraph text.</p></body></html>"
    result = extract_text(html)
    assert "Title" in result
    assert "Paragraph text." in result
    assert "<h1>" not in result


def test_extract_text_removes_script_and_style():
    """extract_text 移除 <script> 和 <style> 内容。"""
    html = """
    <html><head><style>.cls{color:red;}</style></head>
    <body><p>Visible</p><script>console.log('hidden');</script></body></html>
    """
    result = extract_text(html)
    assert "Visible" in result
    assert ".cls" not in result
    assert "console.log" not in result


# ==================== extract_pricing ====================

def test_extract_pricing_parses_plan():
    """extract_pricing 从定价模块中提取计划名称和价格。"""
    html = """
    <div class="pricing">
        <div class="plan">
            <h2>Pro Plan</h2>
            <span class="price">$49/mo</span>
            <ul><li>Feature A</li><li>Feature B</li></ul>
        </div>
    </div>
    """
    result = extract_pricing(html)
    assert len(result) >= 1
    plan = result[0]
    assert plan["plan"] == "Pro Plan"
    assert plan["price"] == "$49/mo"
    assert "Feature A" in plan["features"]


def test_extract_pricing_empty_page():
    """无定价模块时返回空列表。"""
    html = "<html><body><p>No pricing here</p></body></html>"
    result = extract_pricing(html)
    assert result == []


# ==================== extract_job_listings ====================

def test_extract_job_listings_parses_jobs():
    """extract_job_listings 从招聘页提取职位信息。"""
    html = """
    <div class="job">
        <h3><a class="title">Senior Engineer</a></h3>
        <span class="location">Remote</span>
    </div>
    <div class="position">
        <h4><a class="title">Product Manager</a></h4>
        <span class="location">San Francisco</span>
    </div>
    """
    result = extract_job_listings(html)
    assert len(result) == 2
    assert result[0]["title"] == "Senior Engineer"
    assert result[0]["location"] == "Remote"
    assert result[1]["title"] == "Product Manager"


def test_extract_job_listings_empty():
    """无职位信息时返回空列表。"""
    html = "<html><body><p>Welcome to our blog</p></body></html>"
    result = extract_job_listings(html)
    assert result == []

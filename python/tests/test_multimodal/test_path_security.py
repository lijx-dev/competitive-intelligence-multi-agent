"""
多模态路径安全测试 — 覆盖路径穿越拦截、文件后缀白名单、文件大小限制。
"""
import os
import tempfile

import pytest

from src.services.multimodal.path_security import (
    validate_safe_path,
    validate_allowed_suffix,
    validate_file_size,
    MAX_FILE_SIZE_BYTES,
    ALLOWED_UPLOAD_SUFFIXES,
    DEFAULT_MULTIMODAL_ROOT,
)


class TestPathTraversalProtection:
    """路径穿越攻击防护"""

    def test_valid_path_inside_root(self):
        """白名单根目录内的路径应通过"""
        valid = os.path.join(DEFAULT_MULTIMODAL_ROOT, "test.jpg")
        result = validate_safe_path(valid)
        assert result is not None
        assert result.endswith("test.jpg")

    def test_path_traversal_blocked(self):
        """../../etc/passwd 类路径必须被拦截"""
        malicious = os.path.join(DEFAULT_MULTIMODAL_ROOT, "..", "..", "etc", "passwd")
        result = validate_safe_path(malicious)
        assert result is None

    def test_absolute_path_outside_root_blocked(self):
        """绝对路径在根目录外必须被拦截"""
        result = validate_safe_path("/etc/passwd")
        assert result is None

    def test_nonexistent_path_valid_structure(self):
        """不存在的文件但路径结构合法应通过"""
        valid = os.path.join(DEFAULT_MULTIMODAL_ROOT, "subdir", "image.png")
        result = validate_safe_path(valid)
        assert result is not None


class TestFileSuffixWhitelist:
    """文件后缀白名单"""

    @pytest.mark.parametrize("suffix", [".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mp3", ".wav", ".flac"])
    def test_allowed_suffixes(self, suffix):
        """白名单内的后缀应通过"""
        assert validate_allowed_suffix(f"file{suffix}") is True
        assert validate_allowed_suffix(f"file{suffix.upper()}") is True

    @pytest.mark.parametrize("suffix", [".php", ".exe", ".sh", ".py", ".js", ".html", ""])
    def test_disallowed_suffixes(self, suffix):
        """危险后缀必须被拒绝"""
        assert validate_allowed_suffix(f"file{suffix}") is False


class TestFileSizeLimit:
    """文件大小限制"""

    def test_small_file_passes(self):
        """小于限制的文件应通过"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"x" * 1024)  # 1KB
            path = f.name
        try:
            assert validate_file_size(path) is True
        finally:
            os.unlink(path)

    def test_large_file_blocked(self):
        """超过限制的文件必须被拒绝"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"x" * (MAX_FILE_SIZE_BYTES + 1))
            path = f.name
        try:
            assert validate_file_size(path) is False
        finally:
            os.unlink(path)

    def test_nonexistent_file_returns_false(self):
        """不存在的文件返回 False（安全默认值）"""
        assert validate_file_size("/nonexistent/path/file.jpg") is False

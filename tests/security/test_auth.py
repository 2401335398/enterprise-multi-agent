"""
要求 5 / 6：服务端鉴权 + 关闭文档。

覆盖：
  - 演示模式下无 key / 错 key -> 401
  - 正确的 X-API-Key 或 Authorization: Bearer -> 放行
  - dev 模式零回归（不带 key 照常工作）
  - 演示模式但没配 key -> 拒绝启动
  - 演示模式下 /docs 与 /openapi.json 不存在
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from app.security.auth import (
    DemoConfigError,
    parse_api_keys,
    validate_demo_config,
)


# 与 conftest.demo_mode 里配的一致
ALICE_KEY = "test-key-alice"
BOB_KEY = "test-key-bob"


# ============================================================
# 1. 未授权访问
# ============================================================

def test_demo_rejects_request_without_key(demo_mode, asgi):
    response = asgi.post_chat({"message": "你好"})

    assert response.status_code == 401


def test_demo_rejects_request_with_wrong_key(demo_mode, asgi):
    response = asgi.post_chat(
        {"message": "你好"},
        headers={"X-API-Key": "not-a-real-key"},
    )

    assert response.status_code == 401


def test_demo_rejects_key_belonging_to_nobody(
    demo_mode, asgi
):
    # 长得像但不在表里
    response = asgi.post_chat(
        {"message": "你好"},
        headers={"X-API-Key": ALICE_KEY + "x"},
    )

    assert response.status_code == 401


def test_demo_401_does_not_reach_workflow(
    demo_mode, asgi, stub_workflow
):
    """
    401 必须在依赖里就断掉 —— 不能"先跑完 workflow 再返回 401"，
    那样攻击者光靠发请求就能把 token 烧光。
    """

    response = asgi.post_chat({"message": "你好"})

    assert response.status_code == 401
    assert stub_workflow["session_ids"] == []


# ============================================================
# 2. 授权访问
# ============================================================

def test_demo_accepts_x_api_key(
    demo_mode, asgi, stub_workflow
):
    response = asgi.post_chat(
        {"message": "你好"},
        headers={"X-API-Key": ALICE_KEY},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "stub answer"


def test_demo_accepts_bearer_token(
    demo_mode, asgi, stub_workflow
):
    """兼容 Bearer，便于接 Cloudflare Access 的 Service Token。"""

    response = asgi.post_chat(
        {"message": "你好"},
        headers={
            "Authorization": f"Bearer {ALICE_KEY}"
        },
    )

    assert response.status_code == 200


def test_bearer_scheme_is_case_insensitive(
    demo_mode, asgi, stub_workflow
):
    response = asgi.post_chat(
        {"message": "你好"},
        headers={"Authorization": f"bearer {ALICE_KEY}"},
    )

    assert response.status_code == 200


def test_non_bearer_authorization_is_rejected(
    demo_mode, asgi, stub_workflow
):
    response = asgi.post_chat(
        {"message": "你好"},
        headers={"Authorization": f"Basic {ALICE_KEY}"},
    )

    assert response.status_code == 401


def test_health_needs_no_key_in_demo(demo_mode, asgi):
    """
    /health 不加鉴权：探活不该需要凭据，且它不泄露任何业务数据。
    """

    assert asgi.get("/health").status_code == 200


# ============================================================
# 3. dev 模式零回归
# ============================================================

def test_dev_allows_request_without_key(
    dev_mode, asgi, stub_workflow
):
    response = asgi.post_chat({"message": "你好"})

    assert response.status_code == 200


def test_dev_ignores_garbage_key(
    dev_mode, asgi, stub_workflow
):
    """dev 模式不做校验，传什么 key 都不影响。"""

    response = asgi.post_chat(
        {"message": "你好"},
        headers={"X-API-Key": "garbage"},
    )

    assert response.status_code == 200


# ============================================================
# 4. 启动闸门
# ============================================================

def test_demo_without_keys_refuses_to_start(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "app_mode", "demo")
    monkeypatch.setattr(settings, "demo_api_keys", "")

    with pytest.raises(DemoConfigError):
        validate_demo_config()


def test_demo_with_keys_passes_gate(demo_mode):
    validate_demo_config()  # 不抛即通过


def test_dev_without_keys_is_fine(dev_mode):
    validate_demo_config()


# ============================================================
# 5. key 配置解析
# ============================================================

def test_parse_api_keys_ok():
    mapping = parse_api_keys("alice:k1,bob:k2")

    assert set(mapping) == {"k1", "k2"}
    assert mapping["k1"].name == "alice"
    assert mapping["k2"].name == "bob"


def test_parse_api_keys_ignores_blanks():
    mapping = parse_api_keys("  alice:k1 ,, bob:k2  ")

    assert len(mapping) == 2


@pytest.mark.parametrize(
    "raw",
    [
        "alice",          # 没有冒号
        ":k1",            # 没有名字
        "alice:",         # 没有 key
    ],
)
def test_parse_api_keys_rejects_malformed(raw):
    with pytest.raises(DemoConfigError):
        parse_api_keys(raw)


def test_parse_api_keys_splits_on_first_colon_only():
    """
    只在**第一个**冒号处切分，所以 key 本身可以含冒号。
    副作用：名字里带冒号是表达不出来的（"a:b:c" 会被读成
    name=a / key="b:c"），因此命名空间不会出现 "a:b:..." 这种歧义前缀。
    """

    mapping = parse_api_keys("alice:s3cret:with:colons")

    assert list(mapping) == ["s3cret:with:colons"]
    assert mapping["s3cret:with:colons"].name == "alice"


def test_parse_api_keys_rejects_duplicate_key():
    with pytest.raises(DemoConfigError):
        parse_api_keys("alice:same,bob:same")


def test_duplicate_key_error_does_not_leak_the_key():
    """
    报错信息里不能出现 key 的任何片段 —— 日志会被收集。
    """

    try:
        parse_api_keys("alice:super-secret-value,bob:super-secret-value")

    except DemoConfigError as exc:

        assert "super-secret-value" not in str(exc)
        assert "super" not in str(exc)


# ============================================================
# 6. 要求 6：演示模式关闭 Swagger / ReDoc / OpenAPI
#
# 必须在子进程里跑：docs_url 是在 import app.main 的那一刻
# 由 settings 决定的，进程内 monkeypatch 改不了已经建好的 app。
# ============================================================

_DOCS_PROBE = (
    "import app.main as m;"
    "print('docs_url =', m.app.docs_url);"
    "print('redoc_url =', m.app.redoc_url);"
    "print('openapi_url =', m.app.openapi_url)"
)


def _probe_docs(env_overrides: dict) -> str:
    env = dict(os.environ)
    env.update(env_overrides)
    env["PYTHONIOENCODING"] = "utf-8"
    env.setdefault("HF_HUB_OFFLINE", "1")
    env.setdefault("TRANSFORMERS_OFFLINE", "1")

    completed = subprocess.run(
        [sys.executable, "-c", _DOCS_PROBE],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=600,
    )

    assert completed.returncode == 0, completed.stderr

    return completed.stdout


def test_demo_mode_disables_all_docs():
    output = _probe_docs(
        {
            "APP_MODE": "demo",
            "DEMO_API_KEYS": "alice:k1",
        }
    )

    assert "docs_url = None" in output
    assert "redoc_url = None" in output
    assert "openapi_url = None" in output


def test_dev_mode_keeps_docs():
    output = _probe_docs(
        {"APP_MODE": "dev", "DEMO_API_KEYS": ""}
    )

    assert "docs_url = /docs" in output
    assert "openapi_url = /openapi.json" in output


# ============================================================
# 7. 要求 7：密钥一律来自环境变量
# ============================================================

def test_llm_api_key_has_no_default():
    """
    结构上的保证：没有默认值，就写不出"忘配环境变量也能跑"的代码。
    """

    from app.core.config import Settings

    field = Settings.model_fields["llm_api_key"]

    assert field.is_required()


def test_no_hardcoded_api_keys_in_source():
    """
    扫源码里的密钥字面量。这是防回归 —— 现在没有，以后也不该有。
    """

    import re
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]

    key_pattern = re.compile(r"sk-[A-Za-z0-9_\-]{16,}")

    offenders: list[str] = []

    for source_root in ("app", "evals", "tests", "scripts"):

        directory = repo_root / source_root

        if not directory.exists():
            continue

        for path in directory.rglob("*.py"):

            text = path.read_text(
                encoding="utf-8", errors="ignore"
            )

            if key_pattern.search(text):
                offenders.append(
                    str(path.relative_to(repo_root))
                )

    assert offenders == [], (
        f"源码里出现疑似硬编码密钥：{offenders}"
    )

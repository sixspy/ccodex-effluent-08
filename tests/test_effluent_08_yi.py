"""effluent-08 失败测乙：对账齐套灯不得单凭准排行点亮。

口径：齐套 = 封批快照齐套 —— 许可在管批次（已裁定/已准排/已封批）逐批
持有当前代最新封批快照；与准排写口不混用。预置夹具：许可 DP-2026-X08
下 SM-H08 已有正式准排行但缺最新封批快照，同许可 SM-X8-A-001 已封批，
旧口径 seal_count>=1 即把影子意图误记齐套。
"""
import pytest
from fastapi.testclient import TestClient

from app import app
from db import init_db


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    monkeypatch.setattr("db.DB_PATH", tmp_path / "yi.db")
    init_db()
    yield


def _auth(c, user="admin", password="admin123"):
    tok = c.post("/api/login", json={"username": user, "password": password}).json()[
        "token"
    ]
    return {"Authorization": "Bearer " + tok}


def _sample(c, h, code):
    items = c.get("/api/samples", headers=h).json()["items"]
    return next(s for s in items if s["sample_code"] == code)


def test_yi_released_but_snapshot_missing_not_qitao():
    """SM-H08 有正式准排行、缺最新快照：对账不得标齐套。"""
    c = TestClient(app)
    h = _auth(c)
    proof = c.get("/api/proof/sample/SM-H08", headers=h).json()
    assert proof["released"] is True, "预置：SM-H08 已有正式准排行"
    assert proof["snapshot_ok"] is False, "预置：SM-H08 最新封批快照缺失"
    data = c.get("/api/reconcile/DP-2026-X08", headers=h).json()
    assert data["seal_count"] >= 1, "预置：同许可确有封批（旧口径因此误亮）"
    assert data["proof_ready"] is False, "齐套灯不得单凭准排行/他批封批点亮"
    detail = next(s for s in data["samples"] if s["sample_code"] == "SM-H08")
    assert detail["snapshot_ok"] is False
    assert detail["released"] is True
    assert data["missing_snapshot"] >= 1


def test_yi_qitao_only_after_every_pipeline_sample_sealed():
    """在管批次逐批补齐最新快照后，齐套灯才允许亮。"""
    c = TestClient(app)
    h = _auth(c)
    for code in ("SM-X8-A-002", "SM-H08"):
        s = _sample(c, h, code)
        r = c.post("/api/seals", headers=h, json={"sample_id": s["id"]})
        assert r.status_code == 200, r.text
    data = c.get("/api/reconcile/DP-2026-X08", headers=h).json()
    assert data["missing_snapshot"] == 0
    assert data["proof_ready"] is True
    for s in data["samples"]:
        if s["status"] in ("已裁定", "已准排", "已封批"):
            assert s["snapshot_ok"] is True, s["sample_code"]

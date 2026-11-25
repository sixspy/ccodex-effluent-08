"""effluent-08 失败测甲：无最新封批快照时准排必须整笔回退、正式册零增。

口径（docs/effluent-08-no-snapshot-no-release.md，甲路径，2026-11-25 锁死）：
最新封批快照缺失 → 准排拒写（409），discharge_releases 正式册零增，
偏离记 audit「无快照禁准偏航」。预置夹具：排污辛第8槽 SM-X8-A-002
（已裁定、无封批快照，旧码却能准排）。
"""
import pytest
from fastapi.testclient import TestClient

from app import app
from db import init_db


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    monkeypatch.setattr("db.DB_PATH", tmp_path / "jia.db")
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


def _formal_releases(c, h):
    return c.get("/api/releases", headers=h).json()["items"]


def test_jia_no_snapshot_release_rejected_zero_growth():
    """预置夹具 SM-X8-A-002 无最新封批快照：准排须 409 拒写且正式册零增。"""
    c = TestClient(app)
    h = _auth(c)
    target = _sample(c, h, "SM-X8-A-002")
    assert target["status"] == "已裁定"
    before = len(_formal_releases(c, h))
    r = c.post(
        "/api/releases",
        headers=h,
        json={"sample_id": target["id"], "officer": "验收员"},
    )
    assert r.status_code == 409, r.text
    after = _formal_releases(c, h)
    assert len(after) == before, "正式册必须零增"
    assert not any(x["sample_code"] == "SM-X8-A-002" for x in after)


def test_jia_deviation_audited_as_no_snapshot_drift():
    """偏离说明须记「无快照禁准偏航」并拒写。"""
    c = TestClient(app)
    h = _auth(c)
    target = _sample(c, h, "SM-X8-A-002")
    c.post(
        "/api/releases",
        headers=h,
        json={"sample_id": target["id"], "officer": "验收员"},
    )
    audit = c.get("/api/audit", headers=h).json()["items"]
    drift = [
        a
        for a in audit
        if a["action"] == "无快照禁准偏航" and a["target"] == "SM-X8-A-002"
    ]
    assert drift, "缺最新快照的准排偏离须记 audit「无快照禁准偏航」"


def test_jia_legal_chain_seal_then_release():
    """合法链路：先封批出最新快照再准排，才允许正式册增行。"""
    c = TestClient(app)
    h = _auth(c)
    outfalls = c.get("/api/outfalls", headers=h).json()["items"]
    of = next(x for x in outfalls if x["outfall_code"] == "OF-X8-A")
    created = c.post(
        "/api/samples",
        headers=h,
        json={
            "outfall_id": of["id"],
            "permit_ref": "DP-2026-X08",
            "sample_code": "SM-X8-JIA-OK",
            "flow_m3h": 1500,
            "metrics": {"cod": 30.0, "nh3n": 2.0, "tp": 0.2},
        },
    ).json()
    sid = created["id"]
    r0 = c.post("/api/releases", headers=h, json={"sample_id": sid, "officer": "验收员"})
    assert r0.status_code == 409, "未封批出快照前准排须拒写"
    seal = c.post("/api/seals", headers=h, json={"sample_id": sid})
    assert seal.status_code == 200
    r1 = c.post("/api/releases", headers=h, json={"sample_id": sid, "officer": "验收员"})
    assert r1.status_code == 200, r1.text
    assert any(x["sample_code"] == "SM-X8-JIA-OK" for x in _formal_releases(c, h))

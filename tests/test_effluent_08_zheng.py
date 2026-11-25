"""effluent-08 争用失败测：两路会话同批同时抢准排须占准排锁。

口径：抢准排须先占准排锁（sample:{id}，占锁即提交对其他会话可见）；
后到只记争用痕（contention_log「争用失败」）不写准排，败方零行。
"""
import threading

import pytest
from fastapi.testclient import TestClient

from app import app
from db import init_db


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    monkeypatch.setattr("db.DB_PATH", tmp_path / "zheng.db")
    init_db()
    yield


def _auth(c, user, password):
    tok = c.post("/api/login", json={"username": user, "password": password}).json()[
        "token"
    ]
    return {"Authorization": "Bearer " + tok}


def _make_releasable(c, h, code):
    """合法链路造可准排批：入库 → 封批出最新快照。"""
    outfalls = c.get("/api/outfalls", headers=h).json()["items"]
    of = next(x for x in outfalls if x["outfall_code"] == "OF-X8-A")
    created = c.post(
        "/api/samples",
        headers=h,
        json={
            "outfall_id": of["id"],
            "permit_ref": "DP-2026-X08",
            "sample_code": code,
            "flow_m3h": 1500,
            "metrics": {"cod": 30.0, "nh3n": 2.0, "tp": 0.2},
        },
    ).json()
    sid = created["id"]
    seal = c.post("/api/seals", headers=h, json={"sample_id": sid})
    assert seal.status_code == 200, seal.text
    return sid


def _release_rows(c, h, code):
    items = c.get("/api/releases", headers=h).json()["items"]
    return [x for x in items if x["release_ref"] == f"RL-{code}"]


def test_zheng_loser_only_contention_trace_zero_rows():
    """甲会话占准排锁，乙会话同批抢准排：409、零行、只记争用痕。"""
    c = TestClient(app)
    ha = _auth(c, "admin", "admin123")
    hw = _auth(c, "writer", "writer123")
    sid = _make_releasable(c, ha, "SM-X8-ZHENG-1")
    lock_key = f"sample:{sid}"
    r = c.post(f"/api/locks/acquire?lock_key={lock_key}", headers=ha)
    assert r.status_code == 200
    r2 = c.post("/api/releases", headers=hw, json={"sample_id": sid, "officer": "乙路"})
    assert r2.status_code == 409, r2.text
    assert _release_rows(c, ha, "SM-X8-ZHENG-1") == [], "败方零行"
    locks = c.get("/api/locks", headers=ha).json()
    assert any(
        x["lock_key"] == lock_key and x["action"] == "争用失败"
        for x in locks["contention"]
    ), "后到只记争用痕"
    r3 = c.post(f"/api/locks/release?lock_key={lock_key}", headers=ha)
    assert r3.status_code == 200
    r4 = c.post("/api/releases", headers=hw, json={"sample_id": sid, "officer": "乙路"})
    assert r4.status_code == 200, r4.text
    assert len(_release_rows(c, ha, "SM-X8-ZHENG-1")) == 1


def test_zheng_concurrent_same_batch_single_formal_row():
    """两路会话并发打同批准排：恰一胜，败方零行，正式册恰一行。"""
    c = TestClient(app)
    ha = _auth(c, "admin", "admin123")
    hw = _auth(c, "writer", "writer123")
    sid = _make_releasable(c, ha, "SM-X8-ZHENG-2")
    results = []
    barrier = threading.Barrier(2)

    def fire(hdr, officer):
        barrier.wait()
        r = c.post("/api/releases", headers=hdr, json={"sample_id": sid, "officer": officer})
        results.append(r.status_code)

    t1 = threading.Thread(target=fire, args=(ha, "甲路"))
    t2 = threading.Thread(target=fire, args=(hw, "乙路"))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    wins = [s for s in results if s == 200]
    assert len(wins) == 1, f"须恰一胜，实得 {results}"
    assert all(s in (200, 400, 409) for s in results), f"不许 5xx：{results}"
    assert len(_release_rows(c, ha, "SM-X8-ZHENG-2")) == 1, "正式册恰一行"

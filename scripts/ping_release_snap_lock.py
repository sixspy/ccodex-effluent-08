# -*- coding: utf-8 -*-
"""effluent-08 并发脚本 ping_release_snap_lock：两路会话同批抢准排。

验证准排锁口径：占锁即提交；后到只记争用痕不写准排，败方零行。
先决条件：服务已启动（默认 http://127.0.0.1:8000），夹具含排污辛第8槽。

用法：
    python scripts/ping_release_snap_lock.py [--base http://127.0.0.1:8000]
"""
from __future__ import annotations

import argparse
import json
import threading
import time
import urllib.error
import urllib.request


def _req(base, method, path, token=None, body=None):
    req = urllib.request.Request(base + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data=data, timeout=30) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return exc.code, payload


def _login(base, user, password):
    st, data = _req(base, "POST", "/api/login", body={"username": user, "password": password})
    assert st == 200, (st, data)
    return data["token"]


def _make_releasable(base, token, code):
    """合法链路造可准排批：入库 → 封批出最新快照。"""
    st, outfalls = _req(base, "GET", "/api/outfalls", token)
    of = next(x for x in outfalls["items"] if x["outfall_code"] == "OF-X8-A")
    st, created = _req(
        base, "POST", "/api/samples", token,
        {
            "outfall_id": of["id"],
            "permit_ref": "DP-2026-X08",
            "sample_code": code,
            "flow_m3h": 1500,
            "metrics": {"cod": 30.0, "nh3n": 2.0, "tp": 0.2},
        },
    )
    assert st == 200, (st, created)
    sid = created["id"]
    st, seal = _req(base, "POST", "/api/seals", token, {"sample_id": sid})
    assert st == 200, (st, seal)
    return sid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    args = ap.parse_args()
    base = args.base.rstrip("/")
    ta = _login(base, "admin", "admin123")
    tw = _login(base, "writer", "writer123")
    code = f"SM-X8-PING-{int(time.time()) % 100000:05d}"
    sid = _make_releasable(base, ta, code)
    lock_key = f"sample:{sid}"
    print(f"批次 {code} (id={sid}) 已封批出快照，锁键 {lock_key}")

    # 第一段：甲会话占准排锁，乙会话同批抢准排 → 409、零行、只记争用痕
    st, _ = _req(base, "POST", f"/api/locks/acquire?lock_key={lock_key}", ta)
    assert st == 200
    st, payload = _req(base, "POST", "/api/releases", tw, {"sample_id": sid, "officer": "乙路"})
    print(f"占锁中乙路准排: HTTP {st} {json.dumps(payload, ensure_ascii=False)}")
    assert st == 409, st
    st, locks = _req(base, "GET", "/api/locks", ta)
    traces = [x for x in locks["contention"] if x["lock_key"] == lock_key]
    assert traces, "后到只记争用痕"
    print(f"争用痕已记: {traces[0]['action']} {traces[0]['detail']}")
    st, _ = _req(base, "POST", f"/api/locks/release?lock_key={lock_key}", ta)
    assert st == 200

    # 第二段：两路会话并发打同批准排 → 恰一胜，败方零行
    results = []
    barrier = threading.Barrier(2)

    def fire(token, officer):
        barrier.wait()
        st, payload = _req(base, "POST", "/api/releases", token, {"sample_id": sid, "officer": officer})
        results.append((officer, st, payload))

    t1 = threading.Thread(target=fire, args=(ta, "甲路"))
    t2 = threading.Thread(target=fire, args=(tw, "乙路"))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    for officer, st, payload in results:
        print(f"{officer}: HTTP {st} {json.dumps(payload, ensure_ascii=False)}")
    wins = [r for r in results if r[1] == 200]
    assert len(wins) == 1, f"须恰一胜: {[(r[0], r[1]) for r in results]}"
    st, releases = _req(base, "GET", "/api/releases", ta)
    rows = [x for x in releases["items"] if x["release_ref"] == f"RL-{code}"]
    assert len(rows) == 1, f"败方零行，正式册恰一行，实得 {len(rows)}"
    print(f"正式册准排行={len(rows)}（恰一行）")
    print("ping_release_snap_lock: PASS 占锁拒写、争用痕已记、并发恰一胜、败方零行")


if __name__ == "__main__":
    main()

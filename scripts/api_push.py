#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 GitHub Git Data API 推送本地仓库（绕开不稳定的 github.com:443 git push）。

用法：python3 scripts/api_push.py <本地仓库目录> <owner/repo> <branch> [提交信息]

逻辑：本地 HEAD 树 → 与远端分支树对比 → 只上传有差异的 blob → 生成新 tree/commit → 更新 ref。
"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com"
TOKEN = Path("/root/.github_token").read_text().strip()


def req(method: str, url: str, payload=None, allow=(200, 201)):
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Authorization", "token " + TOKEN)
    r.add_header("Accept", "application/vnd.github+json")
    r.add_header("User-Agent", "liwenya-kb-publisher")
    if data:
        r.add_header("Content-Type", "application/json")
    for attempt in range(5):
        try:
            with urllib.request.urlopen(r, timeout=120) as resp:
                body = resp.read().decode()
                if resp.status not in allow:
                    raise RuntimeError(f"{method} {url} -> {resp.status}: {body[:200]}")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            detail = e.read().decode()[:300]
            if e.code in allow:
                return json.loads(detail) if detail else {}
            if e.code in (502, 503, 504) and attempt < 4:
                time.sleep(4 * (attempt + 1))
                continue
            raise RuntimeError(f"{method} {url} -> {e.code}: {detail}")
        except Exception as e:  # 网络抖动
            if attempt < 4:
                time.sleep(4 * (attempt + 1))
                continue
            raise
    raise RuntimeError("unreachable")


def local_tree(repo_dir: Path):
    """返回 {path: (mode, sha)}，取自本地 HEAD 提交。"""
    out = subprocess.run(["git", "-C", str(repo_dir), "ls-tree", "-r", "-z", "HEAD"],
                         capture_output=True, check=True).stdout
    files = {}
    for entry in out.split(b"\0"):
        if not entry:
            continue
        meta, path = entry.split(b"\t", 1)
        mode, typ, sha = meta.decode().split()
        files[path.decode("utf-8", "surrogateescape")] = (mode, sha)
    return files


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        return 1
    repo_dir = Path(sys.argv[1]).resolve()
    full = sys.argv[2]
    branch = sys.argv[3]
    message = sys.argv[4] if len(sys.argv) > 4 else "更新站点/知识库"

    local = local_tree(repo_dir)
    print(f"[api-push] 本地 {len(local)} 个文件")

    ref = None
    try:
        ref = req("GET", f"{API}/repos/{full}/git/ref/heads/{branch}")
    except RuntimeError as e:
        if "-> 404" not in str(e) and "-> 409" not in str(e):
            raise
        print("[api-push] 远端分支不存在（空仓库），将创建首个提交")

    remote = {}
    parent = None
    base_tree = None
    if ref:
        parent = ref["object"]["sha"]
        commit = req("GET", f"{API}/repos/{full}/git/commits/{parent}")
        base_tree = commit["tree"]["sha"]
        tree = req("GET", f"{API}/repos/{full}/git/trees/{base_tree}?recursive=1")
        for node in tree.get("tree", []):
            if node["type"] == "blob":
                remote[node["path"]] = (node["mode"], node["sha"])
        print(f"[api-push] 远端 {len(remote)} 个文件（{parent[:8]}）")

    changed = [p for p, (m, s) in local.items() if remote.get(p, (None, None))[1] != s]
    deleted = [p for p in remote if p not in local]
    print(f"[api-push] 需要新增/更新 {len(changed)} 个，删除 {len(deleted)} 个")

    entries = []
    for i, path in enumerate(changed, 1):
        mode, sha = local[path]
        raw = subprocess.run(["git", "-C", str(repo_dir), "cat-file", "blob", sha],
                             capture_output=True, check=True).stdout
        blob = req("POST", f"{API}/repos/{full}/git/blobs",
                   {"content": base64.b64encode(raw).decode(), "encoding": "base64"})
        entries.append({"path": path, "mode": mode, "type": "blob", "sha": blob["sha"]})
        if i % 20 == 0 or i == len(changed):
            print(f"[api-push]   已上传 {i}/{len(changed)}")
    for path in deleted:
        entries.append({"path": path, "mode": "100644", "type": "blob", "sha": None})

    if not entries:
        print("[api-push] 无差异，跳过")
        return 0

    tree_payload = {"tree": entries}
    if base_tree:
        tree_payload["base_tree"] = base_tree
    new_tree = req("POST", f"{API}/repos/{full}/git/trees", tree_payload)
    commit_payload = {"message": message, "tree": new_tree["sha"]}
    if parent:
        commit_payload["parents"] = [parent]
    new_commit = req("POST", f"{API}/repos/{full}/git/commits", commit_payload)
    if ref:
        req("PATCH", f"{API}/repos/{full}/git/refs/heads/{branch}", {"sha": new_commit["sha"], "force": False})
    else:
        req("POST", f"{API}/repos/{full}/git/refs", {"ref": f"refs/heads/{branch}", "sha": new_commit["sha"]})
    print(f"[api-push] ✅ 已推送 {full}@{branch} → {new_commit['sha'][:8]}（{len(changed)} 改 / {len(deleted)} 删）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""把 games CSV 匯入（或更新）到 Google 試算表的 Games 工作表。

用法：
    python upload_games.py --url https://script.google.com/macros/s/XXXX/exec --key ADMIN_KEY cpbl_2026.csv tpvl_2026.csv

CSV 欄位（第一列是標題）：league,game_id,date,time,away,home,venue,note
  必填：league、date（YYYY-MM-DD）、away、home
  game_id 留空時會自動用「聯盟-日期-時間-主隊」產生；有官方場次編號建議填上，延賽改期才能正確覆寫。
  ADMIN_KEY 在 Apps Script 執行 setup() 後的執行記錄裡。
"""
import argparse
import csv
import json
import sys

import requests

REQUIRED = ("league", "date", "away", "home")
CHUNK = 300


def read_csv(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    good, bad = [], 0
    for i, r in enumerate(rows, start=2):
        r = {k.strip(): (v or "").strip() for k, v in r.items() if k}
        if all(r.get(k) for k in REQUIRED):
            good.append(r)
        else:
            bad += 1
            print(f"  {path} 第 {i} 列缺少必填欄位，略過：{r}", file=sys.stderr)
    print(f"{path}：{len(good)} 場可匯入" + (f"，{bad} 列略過" if bad else ""))
    return good


def post(url: str, payload: dict) -> dict:
    # 用 text/plain 送出；Apps Script 會 302 轉址，requests 會自動跟過去取回 JSON
    r = requests.post(url, data=json.dumps(payload).encode("utf-8"),
                      headers={"Content-Type": "text/plain;charset=utf-8"}, timeout=120)
    r.raise_for_status()
    try:
        return r.json()
    except ValueError:
        raise RuntimeError("回應不是 JSON。請確認網址是「網頁應用程式」的 /exec 網址，且存取權為「所有人」。")


def main():
    ap = argparse.ArgumentParser(description="匯入賽程 CSV 到球賽行事曆")
    ap.add_argument("--url", required=True, help="Apps Script 網頁應用程式網址（/exec 結尾）")
    ap.add_argument("--key", required=True, help="ADMIN_KEY")
    ap.add_argument("csv", nargs="+", help="一個或多個 CSV 檔")
    args = ap.parse_args()

    games = [g for path in args.csv for g in read_csv(path)]
    if not games:
        sys.exit("沒有可匯入的比賽。")

    totals = {"added": 0, "updated": 0, "skipped": 0}
    for i in range(0, len(games), CHUNK):
        part = games[i:i + CHUNK]
        res = post(args.url, {"action": "upsertGames", "key": args.key, "games": part})
        if not res.get("ok"):
            sys.exit(f"匯入失敗：{res.get('message') or res}")
        for k in totals:
            totals[k] += res.get(k, 0)
        print(f"  已送出 {min(i + CHUNK, len(games))}/{len(games)}")
    print(f"完成：新增 {totals['added']}、更新 {totals['updated']}、略過 {totals['skipped']}")


if __name__ == "__main__":
    main()

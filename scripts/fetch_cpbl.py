#!/usr/bin/env python3
"""抓中華職棒或亞洲冬季棒球聯盟的賽程，輸出成行事曆用的 games CSV。

用法：
    # 中職一軍例行賽
    python fetch_cpbl.py --year 2026 --months 3-10 --out cpbl_2026.csv
    # 中職季後賽
    python fetch_cpbl.py --year 2026 --months 10 --kinds E,C --out cpbl_post.csv
    # 亞洲冬季棒球聯盟（awb.cpbl.com.tw），賽事類別自動偵測
    python fetch_cpbl.py --site awb --year 2026 --out awb_2026.csv

輸出欄位：league,game_id,date,time,away,home,venue,note
game_id 使用官方場次編號（CPBL-2026-A-130、AWB-2026-X-12）。延賽後場次編號不變、日期改變，
所以重新抓一次再匯入，Apps Script 會用 game_id 覆寫成新日期。

兩個網站的賽程資料都來自 /schedule/getgamedatas（需要頁面上的驗證 token）。
網站改版時欄位名稱可能變動；加上 --dump-raw raw.json 可以把原始資料存下來檢查。
"""
import argparse
import csv
import json
import re
import sys
import time

import requests

SITES = {
    "cpbl": {"base": "https://www.cpbl.com.tw", "league": "CPBL", "months": "3-10", "kinds": "A"},
    "awb":  {"base": "https://awb.cpbl.com.tw", "league": "AWB",  "months": "11-12", "kinds": "auto"},
}
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.6",
}
# 中職官網常用的賽事類別代碼；冬盟的代碼由頁面自動偵測，名稱也從頁面讀
CPBL_KIND_NAMES = {"A": "", "E": "季後挑戰賽", "C": "總冠軍賽", "G": "熱身賽", "B": "明星賽"}
FIELDS = ["league", "game_id", "date", "time", "away", "home", "venue", "note"]


def parse_months(spec: str) -> list[int]:
    months = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            months.update(range(int(a), int(b) + 1))
        elif part:
            months.add(int(part))
    bad = [m for m in months if not 1 <= m <= 12]
    if bad:
        raise SystemExit(f"月份超出範圍：{bad}")
    return sorted(months)


def load_schedule_page(session: requests.Session, base: str) -> str:
    r = session.get(f"{base}/schedule", timeout=30)
    r.raise_for_status()
    return r.text


def find_token(html: str) -> str:
    patterns = [
        r"RequestVerificationToken['\"]?\s*:\s*['\"]([^'\"]+)['\"]",
        r'name="__RequestVerificationToken"[^>]*value="([^"]+)"',
        r'value="([^"]+)"[^>]*name="__RequestVerificationToken"',
    ]
    for pat in patterns:
        m = re.search(pat, html)
        if m:
            return m.group(1)
    raise RuntimeError("在賽程頁找不到驗證 token，可能是網站改版。")


def find_kinds(html: str) -> dict[str, str]:
    """從賽程頁的賽事類別下拉選單找出代碼與名稱，例如 {'X': '亞洲冬季棒球聯盟'}。"""
    kinds: dict[str, str] = {}
    # <select ... kindCode ...> <option value="X">名稱</option> ... </select>
    for sel in re.finditer(r"<select[^>]*(?:kind|Kind)[^>]*>(.*?)</select>", html, re.S):
        for m in re.finditer(r'<option[^>]*value="([^"]*)"[^>]*>\s*([^<]*?)\s*</option>', sel.group(1)):
            code, name = m.group(1).strip(), m.group(2).strip()
            if code:
                kinds[code] = name
    if not kinds:
        # 頁面以 JavaScript 設定預設類別時，例如 kindCode: 'X' 或 KindCode = "X"
        for m in re.finditer(r"[Kk]ind[Cc]ode['\"]?\s*[:=]\s*['\"]([A-Za-z0-9]{1,3})['\"]", html):
            kinds.setdefault(m.group(1), "")
    return kinds


def pick(d: dict, *keys: str) -> str:
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            return str(v).strip()
    return ""


def fetch_month(session, base, token, year, month, kind):
    r = session.post(
        f"{base}/schedule/getgamedatas",
        data={"calendar": f"{year}/{month:02d}/01", "location": "", "kindCode": kind},
        headers={"RequestVerificationToken": token,
                 "X-Requested-With": "XMLHttpRequest",
                 "Referer": f"{base}/schedule"},
        timeout=30,
    )
    r.raise_for_status()
    j = r.json()
    if not j.get("Success", True):
        raise RuntimeError(f"網站回傳失敗：{j}")
    games = j.get("GameDatas", [])
    if isinstance(games, str):
        games = json.loads(games) if games else []
    return games


def to_row(g: dict, league: str, year: int, kind: str, note: str) -> dict | None:
    sno = pick(g, "GameSno", "GameSNo")
    date_raw = pick(g, "GameDate", "PreExeDate")
    start = pick(g, "PreExeDate", "GameDateTimeS", "GameDate")
    away = pick(g, "VisitingTeamName", "VisitingTeamAbbrName")
    home = pick(g, "HomeTeamName", "HomeTeamAbbrName")
    if not (sno and date_raw and away and home):
        return None
    date = date_raw[:10].replace("/", "-")
    tm = start[11:16] if len(start) >= 16 and start[11:16] != "00:00" else ""
    return {
        "league": league,
        "game_id": f"{league}-{year}-{kind}-{sno}",
        "date": date,
        "time": tm,
        "away": away,
        "home": home,
        "venue": pick(g, "FieldAbbe", "FieldName"),
        "note": note,
    }


def main():
    ap = argparse.ArgumentParser(description="抓中職／冬盟賽程 → games CSV")
    ap.add_argument("--site", choices=SITES, default="cpbl", help="cpbl（預設）或 awb（亞洲冬季棒球聯盟）")
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--months", default=None, help="例如 3-10 或 11,12（中職預設 3-10，冬盟預設 11-12）")
    ap.add_argument("--kinds", default=None,
                    help="賽事類別代碼，逗號分隔；auto 代表從網頁自動偵測（中職預設 A，冬盟預設 auto）")
    ap.add_argument("--out", default=None, help="輸出 CSV 路徑（預設 <site>_<year>.csv）")
    ap.add_argument("--dump-raw", default=None, help="把網站原始資料存成 JSON，方便除錯")
    ap.add_argument("--dump-html", default=None, help="把賽程頁 HTML 存下來，方便除錯")
    ap.add_argument("--sleep", type=float, default=2.0, help="每次請求間隔秒數（預設 2）")
    args = ap.parse_args()

    site = SITES[args.site]
    base, league = site["base"], site["league"]
    months = parse_months(args.months or site["months"])
    out = args.out or f"{args.site}_{args.year}.csv"
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        html = load_schedule_page(session, base)
        token = find_token(html)
    except Exception as e:  # noqa: BLE001
        sys.exit(f"無法讀取 {base}/schedule：{e}\n"
                 "可以改用 games_template.csv 手動整理賽程，再用 upload_games.py 匯入。")
    if args.dump_html:
        with open(args.dump_html, "w", encoding="utf-8") as f:
            f.write(html)

    kinds_arg = (args.kinds or site["kinds"]).strip()
    if kinds_arg.lower() == "auto":
        detected = find_kinds(html)
        if detected:
            print("偵測到賽事類別：" + "、".join(f"{c}={n or '（未命名）'}" for c, n in detected.items()))
            kind_names = detected
        else:
            # 偵測不到時，試空白代碼（部分網站代表全部類別）
            print("網頁上找不到賽事類別選單，改用空白代碼嘗試抓全部比賽。"
                  "若結果為 0 場，請加 --dump-html page.html 檢查，再用 --kinds 指定。")
            kind_names = {"": ""}
    else:
        codes = [k.strip().upper() for k in kinds_arg.split(",") if k.strip()]
        kind_names = {c: (CPBL_KIND_NAMES.get(c, c) if args.site == "cpbl" else "") for c in codes}

    rows: dict[str, dict] = {}
    raw = []
    for kind, kind_name in kind_names.items():
        # 冬盟只有一種賽事時，note 不需要重複寫聯盟名稱
        note = "" if args.site == "awb" and len(kind_names) == 1 else kind_name
        for month in months:
            label = f"{args.year}/{month:02d} 類別 {kind or '全部'}"
            try:
                games = fetch_month(session, base, token, args.year, month, kind)
            except Exception as e:  # noqa: BLE001
                print(f"  {label}：失敗（{e}）", file=sys.stderr)
                time.sleep(args.sleep)
                continue
            raw.extend(games)
            kept = 0
            for g in games:
                row = to_row(g, league, args.year, kind or pick(g, "KindCode") or "X", note)
                if row and row["date"].startswith(str(args.year)):
                    # 同一場次出現兩次（原訂與補賽）時保留日期較晚的那筆
                    old = rows.get(row["game_id"])
                    if not old or row["date"] >= old["date"]:
                        rows[row["game_id"]] = row
                    kept += 1
            print(f"  {label}：{kept} 場")
            time.sleep(args.sleep)

    if args.dump_raw:
        with open(args.dump_raw, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=1)
        print(f"原始資料已存到 {args.dump_raw}")

    if not rows:
        sys.exit("沒有抓到任何比賽。請加上 --dump-raw raw.json --dump-html page.html 檢查網站回傳的內容。")

    ordered = sorted(rows.values(), key=lambda r: (r["date"], r["time"] or "99:99", r["game_id"]))
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(ordered)
    print(f"共 {len(ordered)} 場，已寫入 {out}")


if __name__ == "__main__":
    main()

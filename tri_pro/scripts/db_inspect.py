"""dev.db 내용 빠르게 훑어보는 인스펙터.

사용:
  python3 scripts/db_inspect.py                       # 전체 요약 + 환자 목록
  python3 scripts/db_inspect.py patients              # 환자 5명 상세
  python3 scripts/db_inspect.py config C-1042         # 환자 PRO config
  python3 scripts/db_inspect.py responses C-1042      # 환자 PRO 응답 (최근 30일)
  python3 scripts/db_inspect.py scores C-1042         # 환자 PRO 점수
  python3 scripts/db_inspect.py audit C-1042          # 변경 이력
  python3 scripts/db_inspect.py llm                   # LLM 발화 audit (모든 환자)
  python3 scripts/db_inspect.py push                  # Web Push 구독 상태
  python3 scripts/db_inspect.py table <테이블명>       # 임의 테이블 raw dump
  python3 scripts/db_inspect.py sql "SELECT ..."       # 임의 SQL
"""
import json
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "backend" / "dev.db"


def conn():
    if not DB.exists():
        print(f"❌ DB 없음: {DB}")
        print("   ./setup.sh 또는 ./backend/venv/bin/python backend/seed.py 실행")
        sys.exit(1)
    c = sqlite3.connect(str(DB))
    c.row_factory = sqlite3.Row
    return c


def hr(label: str, char: str = "─"):
    print(f"\n{char * 4} {label} {char * (60 - len(label))}")


def fetch(sql: str, params=()):
    with conn() as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def fmt_table(rows: list[dict], cols: list[str] = None):
    if not rows:
        print("  (없음)")
        return
    if not cols:
        cols = list(rows[0].keys())
    widths = {col: max(len(col), *(len(str(r.get(col, "")))[:40] for r in rows)) for col in cols}
    print("  " + " ".join(f"\033[36m{c:<{widths[c]}}\033[0m" for c in cols))
    print("  " + " ".join("─" * widths[c] for c in cols))
    for r in rows:
        print("  " + " ".join(f"{str(r.get(c, ''))[:40]:<{widths[c]}}" for c in cols))


def cmd_default():
    """전체 요약."""
    hr("📊 테이블 행 수")
    tables = [r["name"] for r in fetch(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    for t in tables:
        cnt = fetch(f'SELECT COUNT(*) AS n FROM "{t}"')[0]["n"]
        print(f"  {t:<28} {cnt}")

    hr("👥 환자 (Patient)")
    rows = fetch("SELECT id, name, birth_year, icd10, cycle_day FROM patient")
    for r in rows:
        age = 2026 - r["birth_year"]
        print(f"  {r['id']:<8} {r['name']:<6} {age}세 · {r['icd10']:<8} · D{r['cycle_day']}")


def cmd_patients():
    hr("👥 환자 전체")
    fmt_table(fetch("SELECT * FROM patient"))


def cmd_config(pid: str):
    hr(f"⚙ {pid} PRO Config")
    rows = fetch("SELECT * FROM patientproconfig WHERE patient_id = ?", (pid,))
    if not rows:
        print(f"  (config 없음)")
        return
    cfg = rows[0]
    print(f"  patient_id:   {cfg['patient_id']}")
    print(f"  frequency:    {cfg['frequency']}")
    print(f"  hads_enabled: {cfg['hads_enabled']}")
    print(f"  hads_subs:    {cfg['hads_subscales']}")
    print(f"  thresholds:   PRO-CTCAE_red={cfg['threshold_pro_ctcae_red']}, "
          f"persist={cfg['threshold_pro_ctcae_persist_days']}, "
          f"HADS y/r={cfg['threshold_hads_yellow']}/{cfg['threshold_hads_red']}")
    print(f"\n  pro_ctcae:")
    pc = json.loads(cfg["pro_ctcae_config"] or "{}")
    for sym, attrs in pc.items():
        print(f"    {sym}: {', '.join(attrs)}")
    print(f"\n  tools:")
    tools = json.loads(cfg["tools_config"] or "{}")
    for name, val in tools.items():
        if name.startswith("__"):
            continue
        marker = "🔒" if val.get("required") else "  "
        on = "ON " if val.get("enabled") else "OFF"
        print(f"    {marker} {name:<10} {on}  freq={val.get('frequency')}")
    print(f"\n  updated:      {cfg['updated_at']} by {cfg['updated_by']}")


def cmd_responses(pid: str):
    hr(f"📋 {pid} PRO 응답 (최근 30일)")
    rows = fetch("""
        SELECT s.id AS session_id, s.started_at, s.ui_mode, s.flex_mode,
               r.tool_code, r.item_code, r.attribute, r.raw_value, r.source
          FROM prosession s
          JOIN proresponse r ON r.session_id = s.id
         WHERE s.patient_id = ?
         ORDER BY s.started_at DESC, r.id
         LIMIT 80
    """, (pid,))
    fmt_table(rows, ["started_at", "session_id", "flex_mode", "tool_code",
                     "item_code", "attribute", "raw_value", "source"])


def cmd_scores(pid: str):
    hr(f"📊 {pid} PRO 점수")
    rows = fetch("""
        SELECT computed_at, tool_code, subscale, value,
               classification, mcid_flag
          FROM proscore
         WHERE patient_id = ?
         ORDER BY computed_at DESC
         LIMIT 50
    """, (pid,))
    fmt_table(rows)


def cmd_audit(pid: str):
    hr(f"📋 {pid} PRO Config 변경 이력")
    rows = fetch("""
        SELECT id, changed_at, changed_by, action
          FROM prosetauditlog
         WHERE patient_id = ?
         ORDER BY changed_at DESC
    """, (pid,))
    fmt_table(rows)


def cmd_llm():
    hr("🤖 LLM 발화 Audit (최근 20건)")
    rows = fetch("""
        SELECT id, patient_id, created_at, guardrail_triggered, llm_mode,
               substr(prompt, 1, 50) AS prompt
          FROM llmaudit
         ORDER BY created_at DESC
         LIMIT 20
    """)
    fmt_table(rows)


def cmd_push():
    hr("🔔 Web Push 구독 현황")
    rows = fetch("""
        SELECT patient_id, COUNT(*) AS devices, MAX(created_at) AS last
          FROM pushsubscription
         GROUP BY patient_id
    """)
    fmt_table(rows)


def cmd_table(name: str):
    hr(f"🔍 {name} 전체 (최대 50행)")
    fmt_table(fetch(f'SELECT * FROM "{name}" LIMIT 50'))


def cmd_sql(sql: str):
    hr("📝 Custom SQL")
    rows = fetch(sql)
    fmt_table(rows)


COMMANDS = {
    "patients":   lambda a: cmd_patients(),
    "config":     lambda a: cmd_config(a[0]),
    "responses":  lambda a: cmd_responses(a[0]),
    "scores":     lambda a: cmd_scores(a[0]),
    "audit":      lambda a: cmd_audit(a[0]),
    "llm":        lambda a: cmd_llm(),
    "push":       lambda a: cmd_push(),
    "table":      lambda a: cmd_table(a[0]),
    "sql":        lambda a: cmd_sql(a[0]),
}


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        cmd_default()
    elif args[0] in COMMANDS:
        try:
            COMMANDS[args[0]](args[1:])
        except IndexError:
            print(f"❌ 인자 부족 — 예: python3 scripts/db_inspect.py {args[0]} C-1042")
    else:
        print(__doc__)

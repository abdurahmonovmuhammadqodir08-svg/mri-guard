import sqlite3
# python check_hash.py
con = sqlite3.connect("mri_guard.db")
cur = con.cursor()

for (table,) in cur.execute("select name from sqlite_master where type='table'").fetchall():
    cols = [r[1] for r in cur.execute(f"pragma table_info({table})")]
    pw_cols = [c for c in cols if "pass" in c.lower() or "hash" in c.lower()]
    if not pw_cols:
        continue
    print(f"\n=== {table}: {pw_cols} ===")
    for col in pw_cols:
        for rid, val in cur.execute(f"select rowid, {col} from {table}"):
            val = val or ""
            if val.startswith(("$2a$", "$2b$", "$2y$")):
                kind = "bcrypt (OK)"
            elif val.startswith("$argon2"):
                kind = "argon2 (OK)"
            elif val.startswith(("pbkdf2_", "$pbkdf2", "scrypt")):
                kind = "pbkdf2/scrypt (OK)"
            else:
                kind = "XESHLANMAGAN YOKI NOMA'LUM  <-- tekshiring"
            print(f"id={rid:<4} {val[:12]}...  {len(val):>4} belgi  {kind}")

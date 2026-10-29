"""Machine master data (Make / Model / Machine) in Etex_admin — reference lists
used to recognize machines in supplier email / WhatsApp intake, and to populate
dropdowns. Safe to re-run; seeds a starter vocabulary only when a table is empty."""
from app.db import admin_engine, execute, q

DDL = [
    """CREATE TABLE IF NOT EXISTS machine_makes (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(160) NOT NULL,
        category VARCHAR(160) NULL,
        active TINYINT NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uq_make (name)
    ) CHARACTER SET utf8mb4""",
    """CREATE TABLE IF NOT EXISTS models (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(160) NOT NULL,
        active TINYINT NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uq_model (name)
    ) CHARACTER SET utf8mb4""",
    """CREATE TABLE IF NOT EXISTS machines (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(160) NOT NULL,
        active TINYINT NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uq_machine (name)
    ) CHARACTER SET utf8mb4""",
]
for ddl in DDL:
    execute(admin_engine, ddl)
print("  tables ready: machine_makes, models, machines")

SEED_MAKES = [
    ("CORINO", "Straightener"), ("Somet", "Rapier"), ("Sulzer", "Projectile"),
    ("Muller", "Jacquard"), ("Toyoda", "Weaving"), ("Picanol", "Rapier"),
    ("Rieter", "Spinning"), ("Trutzschler", "Carding"), ("Mimaki", "Printing"),
    ("JCB", "Construction"),
]
SEED_MODELS = [
    "Somet Rapier", "Sulzer Projectile", "Calandering Machine", "Stenter",
    "Drawframe", "Open End", "Carding Trutzschler", "Simplex / Roving Frames",
    "Scissor Lift Rental", "Boom Lift Rental", "Muller MBJ3", "Super Excel",
    "Rotary Cutter", "Spindle Spinning Machine",
]
SEED_MACHINES = [
    "Corino", "Toyoda", "CNC", "JCB", "Sulzer", "Somet", "Picanol", "Rieter",
    "Reach Stacker", "Crane", "Telehandler",
]


def seed(table, rows, cols):
    if q(admin_engine, f"SELECT COUNT(*) c FROM {table}")[0]["c"]:
        print(f"  {table}: already has data — seed skipped")
        return
    for r in rows:
        vals = r if isinstance(r, tuple) else (r,)
        placeholders = ",".join(f":{c}" for c in cols)
        params = dict(zip(cols, vals))
        try:
            execute(admin_engine, f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})", params)
        except Exception:
            pass
    print(f"  {table}: seeded {len(rows)} row(s)")


seed("machine_makes", SEED_MAKES, ["name", "category"])
seed("models", SEED_MODELS, ["name"])
seed("machines", SEED_MACHINES, ["name"])
print("migrate_v5 done")

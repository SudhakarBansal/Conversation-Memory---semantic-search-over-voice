"""
Day-1 spike: prove we can talk to Nyas Postgres.
Write a row, read it back, clean up. No app logic — just connectivity.
"""
import os
import psycopg

# Load DATABASE_URL from .env (tiny parser; avoids an extra dependency for the spike)
def load_env(path=".env"):
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

load_env()
url = os.environ["DATABASE_URL"]
print(f"Connecting to: {url.split('@')[1]}")  # print host only, never the password

with psycopg.connect(url, connect_timeout=15) as conn:
    with conn.cursor() as cur:
        print("✓ Connected")
        cur.execute("SELECT version();")
        print("  Server:", cur.fetchone()[0].split(",")[0])

        # Create a throwaway table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS spike_test (
                id   SERIAL PRIMARY KEY,
                note TEXT NOT NULL
            );
        """)
        # Insert a row
        cur.execute("INSERT INTO spike_test (note) VALUES (%s) RETURNING id;",
                    ("hello from the conversation-memory spike",))
        new_id = cur.fetchone()[0]
        print(f"✓ Inserted row id={new_id}")

        # Read it back
        cur.execute("SELECT id, note FROM spike_test WHERE id = %s;", (new_id,))
        row = cur.fetchone()
        print(f"✓ Read back: {row}")

        # --- Does pgvector exist? (We expect NO, per FormulateAI.) ---
        cur.execute("SELECT 1 FROM pg_available_extensions WHERE name = 'vector';")
        has_vector = cur.fetchone() is not None
        print(f"  pgvector available: {has_vector}  (expected False — we use numpy cosine instead)")

        # Clean up the throwaway table so the DB stays tidy
        cur.execute("DROP TABLE spike_test;")
        print("✓ Cleaned up (dropped spike_test)")
    conn.commit()

print("\n🎉 Postgres spike PASSED — Nyas DB read/write works.")

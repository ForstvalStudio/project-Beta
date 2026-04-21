import sqlite3
conn = sqlite3.connect('db/tracker.sqlite')
print('=== assets PRAGMA ===')
for r in conn.execute('PRAGMA table_info(assets)').fetchall():
    print(r)

print('\n=== assets CREATE SQL ===')
for r in conn.execute("SELECT sql FROM sqlite_master WHERE name='assets'").fetchall():
    print(r[0])

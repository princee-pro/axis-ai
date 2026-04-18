import sqlite3

with open("schema_dump.txt", "w") as f:
    conn = sqlite3.connect('jarvis_memory.db')
    for row in conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';").fetchall():
        if row[0]:
            f.write(row[0] + "\n-------\n")
    conn.close()

    try:
        r_conn = sqlite3.connect('data/reminders.db')
        for row in r_conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';").fetchall():
            if row[0]:
                f.write(row[0] + "\n-------\n")
        r_conn.close()
    except Exception as e:
        f.write("Reminders DB Error: " + str(e) + "\n-------\n")

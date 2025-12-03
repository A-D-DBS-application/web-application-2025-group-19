from app import create_app

app = create_app()

if __name__ == '__main__':
    import os
    use_sqlite = os.getenv("USE_SQLITE", "0") == "1"
    db_type = "SQLite (local)" if use_sqlite else "PostgreSQL (Supabase)"
    print(f"🚀 Running on port 8888 using {db_type}")
    app.run(debug=True, port=8888)


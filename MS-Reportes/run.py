from app import create_app

app = create_app()

if __name__ == "__main__":
    puerto = int(app.config.get("PORT", 5005))
    app.run(host="127.0.0.1", port=puerto)

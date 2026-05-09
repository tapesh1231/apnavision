from app import create_app

app = create_app()

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    # Production-ready WSGI server for Windows/Linux Pilot Hosting
    try:
        from waitress import serve
        print(f"Starting ApnaVision Pilot Server on port {port}...")
        serve(app, host="0.0.0.0", port=port)
    except ImportError:
        print("Waitress not installed. Falling back to Flask dev server.")
        app.run(host="0.0.0.0", port=port, debug=True)

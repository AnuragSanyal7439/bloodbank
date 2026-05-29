from bloodbank import create_app


def main():
    app = create_app()
    with app.app_context():
        print("SQLite schema and demo data are ready in the instance folder.")


if __name__ == "__main__":
    main()


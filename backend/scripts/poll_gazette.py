from app import create_app
from app.routes.internal import run_poll_gazette


def main() -> None:
    app = create_app()
    with app.app_context():
        result = run_poll_gazette()
        print(result)


if __name__ == "__main__":
    main()

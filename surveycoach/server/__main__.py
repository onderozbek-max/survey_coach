"""Run the loopback-only Studio: python -m surveycoach.server --db ./studio.sqlite3."""
import argparse
from pathlib import Path

import uvicorn

from surveycoach.server import create_app


def main():
    parser = argparse.ArgumentParser(description="SurveyCoach private local Studio (bounded approved-link reader)")
    parser.add_argument("--db", type=Path, default=Path.home() / ".surveycoach" / "studio.sqlite3")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--developer", action="store_true", help="offer the raw snapshot import in the page")
    args = parser.parse_args()
    uvicorn.run(create_app(args.db, developer=args.developer or None), host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()

"""Entry point so `python -m sync render <id>` works without installing the package."""

from .cli import app

if __name__ == "__main__":
    app()

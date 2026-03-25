__version__ = "1.0.0"


def main() -> None:
    from .server import main as server_main

    server_main()


def get_mcp():
    from .server import mcp

    return mcp


__all__ = ["__version__", "get_mcp", "main"]

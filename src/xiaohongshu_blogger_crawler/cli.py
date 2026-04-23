from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import typer

from xiaohongshu_blogger_crawler.config import settings
from xiaohongshu_blogger_crawler.logging_config import configure_logging
from xiaohongshu_blogger_crawler.services.crawler_service import CrawlerService

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Crawl public blogger profile data from Xiaohongshu.",
)


@app.command()
def crawl(
    blogger_id: str = typer.Option(..., "--blogger-id", help="Target blogger id."),
    output: Path | None = typer.Option(
        None,
        "--output",
        help="Output JSON path. Defaults to data/<blogger_id>.json",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging."),
) -> None:
    """Fetch one blogger profile and save it as JSON."""
    log_level = logging.DEBUG if verbose else logging.INFO
    configure_logging(level=log_level)

    service = CrawlerService(settings)
    profile = asyncio.run(service.crawl_blogger(blogger_id=blogger_id, output=output))
    typer.echo(profile.model_dump_json(indent=2, by_alias=True))


@app.command("crawl-names")
def crawl_names(
    output: Path | None = typer.Option(
        None,
        "--output",
        help="Output TXT path. Defaults to XHS_OUTPUT_DIR/XHS_BATCH_TXT_FILENAME.",
    ),
    name: list[str] = typer.Option(
        [],
        "--name",
        help="Blogger name. Repeat this option for multiple names.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging."),
) -> None:
    """Fetch bloggers by names from config and save results into one txt file."""
    log_level = logging.DEBUG if verbose else logging.INFO
    configure_logging(level=log_level)

    service = CrawlerService(settings)
    names_override = name if name else None
    output_path, results = asyncio.run(
        service.crawl_bloggers_by_names_to_txt(names=names_override, output=output)
    )

    found_count = sum(1 for item in results if item.is_found)
    typer.echo(f"Saved: {output_path.as_posix()} | total={len(results)} | found={found_count}")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host."),
    port: int = typer.Option(8000, "--port", "-p", help="Bind port."),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload (dev mode)."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging."),
) -> None:
    """Start the FastAPI web server for blogger search."""
    import uvicorn

    log_level = "debug" if verbose else "info"
    configure_logging(level=logging.DEBUG if verbose else logging.INFO)
    typer.echo(f"Starting server at http://{host}:{port}")
    uvicorn.run(
        "xiaohongshu_blogger_crawler.api:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
    )


@app.command()
def dashboard(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host."),
    port: int = typer.Option(8001, "--port", "-p", help="Bind port."),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload (dev mode)."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging."),
) -> None:
    """Start the deploy-task dashboard server."""
    import uvicorn

    log_level = "debug" if verbose else "info"
    configure_logging(level=logging.DEBUG if verbose else logging.INFO)
    typer.echo(f"Starting dashboard at http://{host}:{port}")
    uvicorn.run(
        "xiaohongshu_blogger_crawler.dashboard.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
    )


if __name__ == "__main__":
    app()

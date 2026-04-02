# xiaohongshu_blogger_crawler

A Python 3.12+ project scaffold for crawling public Xiaohongshu blogger data.

## Quick start

```bash
python -m venv .venv
.venv\\Scripts\\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
```

Run single profile crawl by blogger id:

```bash
xhs-crawler crawl --blogger-id YOUR_BLOGGER_ID
```

Run batch crawl by names from `.env` and save one txt file:

```bash
xhs-crawler crawl-names
```

Or override names in command line:

```bash
xhs-crawler crawl-names --name 达人A --name 达人B --output data/custom_results.txt
```

## Cookie and names config

`.env` example:

```env
XHS_COOKIE=your_xiaohongshu_cookie
XHS_BLOGGER_NAMES=["达人A", "达人B", "达人C"]
```

## Project structure

```text
xiaohongshu_blogger_crawler/
├─ pyproject.toml
├─ .env.example
├─ src/
│  └─ xiaohongshu_blogger_crawler/
│     ├─ cli.py
│     ├─ config.py
│     ├─ logging_config.py
│     ├─ clients/
│     ├─ models/
│     ├─ parsers/
│     ├─ services/
│     └─ storage/
└─ tests/
```

## Notes

- This scaffold targets publicly visible data and search result pages.
- Respect Xiaohongshu terms of service, robots policy, and local laws.
- The parser is pattern-based and may need updates when the page structure changes.

"""Rows examined and latency for the route search, without and with its index.

    make bench

`make bench` starts a throwaway MySQL from the image CI uses, runs this, and
removes the container. To run it by hand against a server you can wipe:

    BENCH_DATABASE_URL=mysql+pymysql://USER:PASSWORD@127.0.0.1:3317/aerofare_bench \\
        uv run python -m scripts.bench_route_search

It reseeds the database (the name must end in _bench), drops the composite
index the way the migration's downgrade does, measures, recreates the index
with the migration's definition, measures again, and writes
benchmarks/route_search.md.
"""

import os
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Connection, Engine, create_engine, text

from app.flights.schemas import FlightSearch
from app.flights.services import build_search_query
from scripts.seed_flights import bench_url

FLIGHTS = 200_000
AIRPORTS = 60
SEED = 42
WARMUP = 3
RUNS = 20

# The index from migration 2b19d14b47a1. It is checked against the index the
# migration actually built before anything is dropped.
INDEX_NAME = "ix_flights_route_start_time"
INDEX_COLUMNS = ("departure_airport", "arrival_airport", "start_time")

# What the frontend sends: a route and a departure/arrival date window.
WINDOW = {"start_time": datetime(2030, 6, 15), "end_time": datetime(2030, 6, 21, 23, 59, 59)}

# (departure, arrival). Seed 42 spreads routes uniformly, so "busy" and "quiet"
# only span 31 to 84 flights per route; there are no hub routes in this data.
ROUTES = [
    (27, 28),  # 84 flights, the busiest route
    (24, 2),  # 83
    (60, 48),  # 81
    (1, 2),  # 66, the route in docs/query-optimization.md
    (57, 36),  # 35
    (52, 37),  # 33
    (5, 60),  # 31, the quietest route
]
EXPLAIN_ROUTE = (1, 2)

OUTPUT = Path(__file__).resolve().parent.parent / "benchmarks" / "route_search.md"

# The last search statement this connection ran. The history keeps the last
# few statements per thread, including these lookups, hence the SQL_TEXT filter.
LAST_SEARCH_EXAMINED = text(
    "SELECT ROWS_EXAMINED FROM performance_schema.events_statements_history "
    "WHERE THREAD_ID = PS_CURRENT_THREAD_ID() AND SQL_TEXT LIKE 'SELECT flights.id%' "
    "ORDER BY EVENT_ID DESC LIMIT 1"
)


def route_params(route: tuple[int, int]) -> FlightSearch:
    return FlightSearch(departure_airport=route[0], arrival_airport=route[1], **WINDOW)


def index_columns(conn: Connection) -> dict[str, tuple[str, ...]]:
    rows = conn.execute(
        text(
            "SELECT index_name, column_name FROM information_schema.statistics "
            "WHERE table_schema = DATABASE() AND table_name = 'flights' "
            "ORDER BY index_name, seq_in_index"
        )
    ).all()
    indexes: dict[str, tuple[str, ...]] = {}
    for name, column in rows:
        indexes[name] = indexes.get(name, ()) + (column,)
    return indexes


def drop_route_index(conn: Connection) -> None:
    """Back to the schema before the index, as the migration's downgrade does.

    Creating the composite index made MySQL drop the foreign key's own index on
    departure_airport, so the foreign key refuses to lose the composite one
    until that index exists again."""
    conn.execute(text("CREATE INDEX departure_airport ON flights (departure_airport)"))
    conn.execute(text(f"DROP INDEX {INDEX_NAME} ON flights"))
    conn.execute(text("ANALYZE TABLE flights"))


def create_route_index(conn: Connection) -> None:
    """Forward to the migrated schema. The explicit departure_airport index is
    dropped afterwards, because the migrated schema does not have one."""
    conn.execute(text(f"CREATE INDEX {INDEX_NAME} ON flights ({', '.join(INDEX_COLUMNS)})"))
    conn.execute(text("DROP INDEX departure_airport ON flights"))
    conn.execute(text("ANALYZE TABLE flights"))


def measure(conn: Connection, params: FlightSearch) -> dict:
    """Median latency over RUNS calls after WARMUP, and the rows MySQL examined.

    Only the query and fetching its rows are timed, not the performance_schema
    lookup after it. Rows examined is read after every timed call and must not
    change between calls."""
    stmt = build_search_query(params)
    timings: list[float] = []
    examined: set[int] = set()
    returned = 0
    for i in range(WARMUP + RUNS):
        start = time.perf_counter_ns()
        returned = len(conn.execute(stmt).fetchall())
        elapsed_ms = (time.perf_counter_ns() - start) / 1e6
        if i >= WARMUP:
            timings.append(elapsed_ms)
            examined.add(conn.execute(LAST_SEARCH_EXAMINED).scalar_one())
    if len(examined) != 1:
        sys.exit(f"Rows examined changed between calls for {params}: {sorted(examined)}")
    return {"returned": returned, "examined": examined.pop(), "median_ms": statistics.median(timings)}


def explain(engine: Engine, conn: Connection, params: FlightSearch) -> list[dict]:
    # literal_binds gives the same SQL text pymysql sends; FORMAT=TRADITIONAL
    # because this MySQL defaults to the tree format.
    sql = str(build_search_query(params).compile(dialect=engine.dialect, compile_kwargs={"literal_binds": True}))
    return [dict(row) for row in conn.exec_driver_sql("EXPLAIN FORMAT=TRADITIONAL " + sql).mappings()]


def markdown_table(rows: list[dict]) -> str:
    columns = list(rows[0])
    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    lines += ["| " + " | ".join("NULL" if r[c] is None else str(r[c]) for c in columns) + " |" for r in rows]
    return "\n".join(lines)


def write_report(meta: dict, counts: dict, before: dict, after: dict, plans: dict) -> None:
    lines = [
        "# Route search benchmark",
        "",
        "Generated by `scripts/bench_route_search.py`. Do not edit by hand: rerun `make bench`.",
        "",
        f"- MySQL: {meta['version']} (image `{meta['image']}`, the one CI uses)",
        f"- Flights: {meta['flights']:,} between {AIRPORTS} airports, seed {SEED} (`scripts/seed_flights.py`)",
        f"- Search: route + departure window {WINDOW['start_time']:%Y-%m-%d} to {WINDOW['end_time']:%Y-%m-%d}, "
        "limit 100, ordered by departure (what the frontend sends)",
        f"- Latency: median of {RUNS} calls after {WARMUP} warm-up calls, query and row fetch only, "
        "from the host to MySQL in Docker",
        "- Rows examined: `performance_schema.events_statements_history.ROWS_EXAMINED` for "
        "`PS_CURRENT_THREAD_ID()`, identical on every timed call",
        f"- Without the index: `{INDEX_NAME}` dropped and a `departure_airport` index created, as in the "
        "migration's downgrade. With it: recreated as `(" + ", ".join(INDEX_COLUMNS) + ")`, as in migration "
        "`2b19d14b47a1`",
        f"- Host: {meta['host']}, Python {platform.python_version()}, {meta['date']}",
        "",
        "| Route | Flights on route | Rows returned | Rows examined without | Rows examined with "
        "| Examined ratio | Median ms without | Median ms with |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for route in ROUTES:
        b, a = before[route], after[route]
        lines.append(
            f"| {route[0]} → {route[1]} | {counts[route]} | {a['returned']} | {b['examined']:,} | {a['examined']:,} "
            f"| {b['examined'] / a['examined']:.0f}x | {b['median_ms']:.2f} | {a['median_ms']:.2f} |"
        )
    lines += [
        "",
        f"## EXPLAIN, route {EXPLAIN_ROUTE[0]} → {EXPLAIN_ROUTE[1]}",
        "",
        "`rows` in EXPLAIN is the optimizer's estimate, not what was read. The table above is what was read.",
        "",
        "Without the index:",
        "",
        markdown_table(plans["without"]),
        "",
        "With the index:",
        "",
        markdown_table(plans["with"]),
        "",
        "## Reproduce",
        "",
        "```bash",
        "make bench",
        "```",
        "",
        "Needs Docker and uv. It starts a fresh MySQL container on port 3317 (`BENCH_PORT` changes it), "
        "seeds it, measures, writes this file and removes the container.",
        "",
    ]
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text("\n".join(lines))


def main() -> None:
    url = bench_url()
    subprocess.run(
        [sys.executable, "-m", "scripts.seed_flights", "--recreate",
         "--flights", str(FLIGHTS), "--airports", str(AIRPORTS), "--seed", str(SEED)],
        check=True,
    )

    # Every statement commits on its own, as each API request's does, and no
    # BEGIN/COMMIT sits between a search and its performance_schema lookup.
    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        consumer = conn.execute(
            text("SELECT ENABLED FROM performance_schema.setup_consumers WHERE NAME = 'events_statements_history'")
        ).scalar_one_or_none()
        if consumer != "YES":
            sys.exit(f"performance_schema consumer events_statements_history is {consumer!r}, need 'YES'")

        flights = conn.execute(text("SELECT COUNT(*) FROM flights")).scalar_one()
        if flights != FLIGHTS:
            sys.exit(f"Expected {FLIGHTS:,} flights, found {flights:,}")
        migrated = index_columns(conn)
        if migrated.get(INDEX_NAME) != INDEX_COLUMNS:
            sys.exit(f"The migration built {INDEX_NAME} as {migrated.get(INDEX_NAME)}, expected {INDEX_COLUMNS}")
        conn.execute(text("ANALYZE TABLE flights, airports"))

        counts = {}
        for route in ROUTES:
            counts[route] = conn.execute(
                text("SELECT COUNT(*) FROM flights WHERE departure_airport = :d AND arrival_airport = :a"),
                {"d": route[0], "a": route[1]},
            ).scalar_one()

        meta = {
            "version": conn.execute(text("SELECT VERSION()")).scalar_one(),
            "image": os.environ.get("BENCH_IMAGE", "not recorded (run outside make bench)"),
            "flights": flights,
            "host": f"{platform.system()} {platform.machine()}",
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        }

        drop_route_index(conn)
        if INDEX_NAME in index_columns(conn):
            sys.exit(f"{INDEX_NAME} is still there after dropping it")
        before = {route: measure(conn, route_params(route)) for route in ROUTES}
        plans = {"without": explain(engine, conn, route_params(EXPLAIN_ROUTE))}

        create_route_index(conn)
        if index_columns(conn) != migrated:
            sys.exit(f"Indexes after recreating differ from the migrated schema: {index_columns(conn)} vs {migrated}")
        after = {route: measure(conn, route_params(route)) for route in ROUTES}
        plans["with"] = explain(engine, conn, route_params(EXPLAIN_ROUTE))

    for route in ROUTES:
        if before[route]["returned"] != after[route]["returned"]:
            sys.exit(f"Route {route} returned different rows without and with the index")

    write_report(meta, counts, before, after, plans)
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()

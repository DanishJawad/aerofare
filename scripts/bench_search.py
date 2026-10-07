"""Time the query behind GET /flights/search and show how MySQL runs it.

    BENCH_DATABASE_URL=mysql+pymysql://USER:PASSWORD@localhost:3306/aerofare_bench \\
        uv run python -m scripts.bench_search --label before

Run scripts.seed_flights first. The output is Markdown, ready to paste into
docs/query-optimization.md. It runs the real search_flights() from the app, so
what is measured is what a request costs, minus HTTP.
"""

import argparse
import statistics
import sys
import time
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.flights.enums import FlightClass
from app.flights.schemas import FlightSearch
from app.flights.services import build_search_query, search_flights
from scripts.seed_flights import bench_url

ONE_DAY = {"start_time": datetime(2030, 6, 15), "end_time": datetime(2030, 6, 15, 23, 59, 59)}
ONE_WEEK = {"start_time": datetime(2030, 6, 15), "end_time": datetime(2030, 6, 21, 23, 59, 59)}
ONE_MONTH = {"start_time": datetime(2030, 6, 1), "end_time": datetime(2030, 6, 30, 23, 59, 59)}
ROUTE = {"departure_airport": 1, "arrival_airport": 2}

# The first three are what the frontend sends: a route, usually with dates.
# The last is a control: no route, so an index that starts with the route
# cannot help it. It is here to show where the optimisation stops working.
SCENARIOS = {
    "route + one week": FlightSearch(**ROUTE, **ONE_WEEK),
    "route + one month + class": FlightSearch(**ROUTE, **ONE_MONTH, flight_class=FlightClass.ECONOMY),
    "route only": FlightSearch(**ROUTE),
    "control: one day, no route": FlightSearch(**ONE_DAY),
}


def literal_sql(engine, params: FlightSearch) -> str:
    """The query as plain SQL text, so EXPLAIN can run exactly what the API runs."""
    stmt = build_search_query(params)
    return str(stmt.compile(dialect=engine.dialect, compile_kwargs={"literal_binds": True}))


def rows_examined(engine, params: FlightSearch) -> tuple[int, int]:
    """(rows MySQL examined, rows it sent back), from its own statement history."""
    with engine.connect() as conn:
        sent = len(conn.execute(build_search_query(params)).fetchall())
        examined = conn.execute(
            text(
                "SELECT ROWS_EXAMINED FROM performance_schema.events_statements_history "
                "WHERE THREAD_ID = (SELECT THREAD_ID FROM performance_schema.threads "
                "                   WHERE PROCESSLIST_ID = CONNECTION_ID()) "
                "AND SQL_TEXT LIKE 'SELECT flights.id%' ORDER BY EVENT_ID DESC LIMIT 1"
            )
        ).scalar_one()
    return examined, sent


def time_search(engine, params: FlightSearch, runs: int, warmup: int) -> list[float]:
    """Milliseconds per call, with a new Session each time like one per request."""
    timings = []
    for i in range(warmup + runs):
        start = time.perf_counter_ns()
        with Session(engine) as db:
            search_flights(params, db)
        elapsed_ms = (time.perf_counter_ns() - start) / 1e6
        if i >= warmup:
            timings.append(elapsed_ms)
    return timings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--label", required=True, help='e.g. "before" or "after"')
    parser.add_argument("--runs", type=int, default=50)
    parser.add_argument("--warmup", type=int, default=10)
    args = parser.parse_args()

    engine = create_engine(bench_url(), pool_pre_ping=True)
    with engine.connect() as conn:
        version = conn.execute(text("SELECT VERSION()")).scalar_one()
        flights = conn.execute(text("SELECT COUNT(*) FROM flights")).scalar_one()
        # MySQL caches table statistics for a day by default; turn that off so the
        # sizes below describe the table as it is now, not as it was yesterday.
        conn.execute(text("SET SESSION information_schema_stats_expiry = 0"))
        data_mb, index_mb = conn.execute(
            text(
                "SELECT ROUND(data_length / 1048576, 1), ROUND(index_length / 1048576, 1) "
                "FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'flights'"
            )
        ).one()
        indexes = conn.execute(
            text(
                "SELECT index_name, GROUP_CONCAT(column_name ORDER BY seq_in_index) "
                "FROM information_schema.statistics WHERE table_schema = DATABASE() "
                "AND table_name = 'flights' GROUP BY index_name ORDER BY index_name"
            )
        ).all()
    if flights == 0:
        sys.exit("The flights table is empty. Run scripts.seed_flights first.")

    print(f"## {args.label}\n")
    print(f"MySQL {version}, {flights:,} flights, median of {args.runs} runs after {args.warmup} warm-up runs.")
    print("Indexes on flights: " + "; ".join(f"`{name}` ({cols})" for name, cols in indexes))
    print(f"Table size: {data_mb} MB data, {index_mb} MB indexes\n")

    print("| Search | Rows returned | Rows MySQL examined | Index used | Median ms | p95 ms | Min ms |")
    print("|---|---:|---:|---|---:|---:|---:|")
    plans = []
    for name, params in SCENARIOS.items():
        sql = literal_sql(engine, params)
        with engine.connect() as conn:
            # FORMAT=TRADITIONAL because newer MySQL versions default to TREE output.
            plan = conn.exec_driver_sql("EXPLAIN FORMAT=TRADITIONAL " + sql).mappings().one()
            tree = "\n".join(row[0] for row in conn.exec_driver_sql("EXPLAIN ANALYZE " + sql))
        examined, sent = rows_examined(engine, params)
        t = sorted(time_search(engine, params, args.runs, args.warmup))
        p95 = t[min(len(t) - 1, int(len(t) * 0.95))]
        print(
            f"| {name} | {sent} | {examined:,} | `{plan['key']}` ({plan['type']}) | "
            f"{statistics.median(t):.2f} | {p95:.2f} | {t[0]:.2f} |"
        )
        plans.append((name, tree))

    print("\n### EXPLAIN ANALYZE\n")
    for name, tree in plans:
        print(f"**{name}**\n\n```\n{tree}\n```\n")


if __name__ == "__main__":
    main()

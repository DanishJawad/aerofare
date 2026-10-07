"""Fill a throwaway database with a reproducible flights table, for benchmarking.

    BENCH_DATABASE_URL=mysql+pymysql://USER:PASSWORD@localhost:3306/aerofare_bench \\
        uv run python -m scripts.seed_flights --recreate

The same seed always produces the same rows, so two runs (or two machines)
benchmark the same data. The database name must end in _bench because
--recreate drops it.
"""

import argparse
import os
import random
import re
import subprocess
import sys
from collections.abc import Iterator
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import URL, create_engine, insert, text
from sqlalchemy.engine import make_url

from app.flights.enums import FlightClass

BATCH_SIZE = 5_000
FIRST_DEPARTURE = datetime(2030, 1, 1)  # naive UTC, like the values the API stores
DEPARTURE_SPREAD_DAYS = 365


def generate_flights(count: int, airport_count: int, seed: int = 42) -> Iterator[dict]:
    """Yield `count` flights between airports 1..airport_count.

    Routes are uniform: every airport is as busy as every other. Real traffic is
    skewed towards a few hubs, so a busy-route search would match more rows here
    than this data suggests. That is a limit of the data, noted in the results."""
    if airport_count < 2:
        raise ValueError("need at least two airports")
    rng = random.Random(seed)
    classes = list(FlightClass)
    for _ in range(count):
        departure = rng.randint(1, airport_count)
        arrival = rng.randint(1, airport_count - 1)
        if arrival >= departure:  # skips `departure`, so the two never match
            arrival += 1
        start = FIRST_DEPARTURE + timedelta(minutes=rng.randrange(DEPARTURE_SPREAD_DAYS * 24 * 60))
        total_seats = rng.randint(100, 300)
        yield {
            "airline_name": rng.choice(["PIA", "Airblue", "SereneAir", "Emirates", "Qatar"]),
            "departure_airport": departure,
            "arrival_airport": arrival,
            "start_time": start,
            "end_time": start + timedelta(minutes=rng.randint(60, 600)),
            "price": Decimal(rng.randint(5_000, 90_000)) / 100,
            "total_seats": total_seats,
            "available_seats": rng.randint(0, total_seats),
            "flight_class": rng.choice(classes),
        }


def bench_url() -> URL:
    raw = os.environ.get("BENCH_DATABASE_URL")
    if not raw:
        sys.exit("Set BENCH_DATABASE_URL, e.g. mysql+pymysql://USER:PASSWORD@localhost:3306/aerofare_bench")
    url = make_url(raw)
    if not (url.database or "").endswith("_bench"):
        sys.exit(f"Refusing to run: the database must end in '_bench', got {url.database!r}")
    return url


def recreate_database(url: URL) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_]+", url.database):
        sys.exit(f"Unexpected characters in database name {url.database!r}")
    server = URL.create(url.drivername, url.username, url.password, url.host, url.port, query=url.query)
    engine = create_engine(server, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS `{url.database}`"))
        conn.execute(text(f"CREATE DATABASE `{url.database}`"))
    engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--flights", type=int, default=200_000)
    parser.add_argument("--airports", type=int, default=60)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--recreate", action="store_true", help="drop and rebuild the database first")
    args = parser.parse_args()
    url = bench_url()

    if args.recreate:
        recreate_database(url)
    # Build the schema the same way the app does: from the migrations. The
    # subprocess gets the benchmark URL, so the app's own settings are untouched.
    env = {**os.environ, "DATABASE_URL": url.render_as_string(hide_password=False)}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True, env=env)

    # Imported here, after the URL is validated: importing app code loads settings.
    from app.airports.models import Airport
    from app.flights.models import Flight

    engine = create_engine(url)
    with engine.begin() as conn:
        if conn.execute(text("SELECT COUNT(*) FROM flights")).scalar_one():
            sys.exit("The flights table already has rows. Re-run with --recreate.")
        conn.execute(
            insert(Airport),
            [{"name": f"Airport {i:02d}", "city": f"City {i:02d}", "country": "PK"} for i in range(1, args.airports + 1)],
        )
        batch: list[dict] = []
        for flight in generate_flights(args.flights, args.airports, args.seed):
            batch.append(flight)
            if len(batch) == BATCH_SIZE:
                conn.execute(insert(Flight), batch)
                batch = []
        if batch:
            conn.execute(insert(Flight), batch)

    with engine.connect() as conn:
        # Refresh the optimizer's statistics so the plans are decided on the real data.
        conn.execute(text("ANALYZE TABLE flights"))
        rows = conn.execute(text("SELECT COUNT(*) FROM flights")).scalar_one()
        data_mb, index_mb = conn.execute(
            text(
                "SELECT ROUND(data_length / 1048576, 1), ROUND(index_length / 1048576, 1) "
                "FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'flights'"
            )
        ).one()
    print(f"Seeded {rows:,} flights across {args.airports} airports (seed {args.seed}).")
    print(f"flights table: {data_mb} MB data, {index_mb} MB indexes")


if __name__ == "__main__":
    main()

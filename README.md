# Aerofare

A flight-booking REST API and web client: search flights, book seats, and manage refunds, with
the concurrency and auth handling a real booking system needs. Built to learn backend
engineering properly rather than to ship a demo. The interesting part isn't the CRUD, it's
making sure two people can't book the same last seat, and that a cancelled booking actually
reverses everything it touched.

## The problem

Most student booking-app clones stop at "insert a row." That breaks the moment two requests hit
the same flight at once: both read the same seat count, both succeed, and the flight oversells.
A booking system that can't guarantee this is broken, whatever else it does.

## Approach

- **FastAPI + SQLAlchemy 2.0**, layered as router to service to model per feature (airports,
  flights, auth, bookings, payments), with Pydantic schemas as the request/response boundary.
- **Booking a flight takes a row lock** (`SELECT ... FOR UPDATE`) on the flight before checking
  and decrementing seats, so a concurrent request blocks instead of racing. The seat decrement,
  the booking row, and its payment record commit as one transaction.
- **JWT auth with server-side revocation.** Tokens carry a `jti`; logging out blacklists it in
  Redis with a TTL matching the token's remaining lifetime, so a revoked token stops working
  immediately instead of waiting out its expiry.
- **Alembic migrations** track every schema change. The schema is never hand-created.
- **React + TypeScript frontend** consuming the same API a real client would: JWT in
  `localStorage`, 401 handling, loading/error/empty states on every screen, an admin area gated
  on a role read from the server, not the token.

## What went wrong, and what it taught me

The migration chain looked complete. It had only ever run against a database whose tables were
actually built earlier by SQLAlchemy's `create_all()`, before Alembic was wired in properly, so
the first migration was silently empty and nobody noticed, because the target database already
had every table it was supposed to create. It only surfaced when I pointed the app at a
genuinely empty database: `alembic upgrade head` failed immediately. Fixed it by writing the
real `CREATE TABLE` statements into that migration and rebuilding the schema from scratch to
prove it now works end to end. The lesson: a migration chain that has never been run against
zero isn't verified, it's untested.

## Run it locally

Needs MySQL and Redis running locally.

```bash
cp .env.example .env        # fill in DATABASE_URL, SECRET_KEY, REDIS_URL
uv sync
alembic upgrade head
fastapi dev app/main.py     # http://localhost:8000/docs
```

```bash
cd frontend
cp .env.example .env
npm install
npm run dev                 # http://localhost:5173
```

## What's next

- Automated tests around the booking and payment lifecycle, starting with the concurrent-booking
  case above.
- Deployment, once I've learned it properly rather than rushing it.
- Pagination on list endpoints, rate limiting on login, background email notifications on
  booking confirmation.

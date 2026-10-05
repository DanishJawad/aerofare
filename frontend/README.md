# Aerofare frontend

React + TypeScript client for the Aerofare FastAPI backend. Anyone can browse and search
flights; logged-in users can book, cancel, and see their payments; admins get a separate area
for airports, flights, bookings, and refunds. The only runtime dependency beyond React is
`react-router-dom`.

## Run it locally

The backend must be running on `http://localhost:8000`. Its CORS config only allows
`http://localhost:5173`, so keep Vite on that port.

```bash
cp .env.example .env   # VITE_API_URL=http://localhost:8000
npm install
npm run dev            # http://localhost:5173
```

`npm run build` type-checks and builds; `npm run lint` runs ESLint.

To see the admin area you need a user with `is_admin = true` in the database. There is no
endpoint that grants it.

## Routes

| Path | Access | What it does |
|---|---|---|
| `/` | public | Search and browse flights. Filters live in the query string. |
| `/flights/:id` | public (booking needs login) | Itinerary, seat picker, book |
| `/login`, `/signup` | public | Auth. Signup logs you straight in. |
| `/bookings` | user | Upcoming and past trips, cancel with confirmation |
| `/payments` | user | Payment history |
| `/profile` | user | Edit details, change password, log out |
| `/admin/flights`, `/admin/airports` | admin | List, create, edit |
| `/admin/bookings` | admin | Read-only, filter by status |
| `/admin/payments` | admin | Refund with confirmation |

## How it's put together

- `src/api.ts`: one `request()` function. Attaches the JWT from `localStorage`, turns FastAPI
  errors (`detail` as a string or a 422 array) into an `ApiError` with a readable message and
  per-field errors, and on any 401 clears the token and sends the user to `/login`.
- `src/auth/`: `AuthProvider` restores the session from `/users/me` on load. `is_admin` comes
  from that call, not from the token (the token only carries the user id).
- `src/lib/useAsync.ts`: the loading / error / data pattern every data screen uses, with
  `reload()` after mutations so the server stays the source of truth.
- `src/lib/format.ts`: money, dates, and the UTC handling described below.

## Design tokens

All values live as CSS custom properties at the top of `src/index.css`. Use only these:

- Spacing: 4, 8, 12, 16, 24, 32, 48, 64px
- Type: 12, 14, 16, 20, 32px; weights 400 and 600. 12px is only for non-essential labels.
- Color: gray ramp `#111827 / #374151 / #6b7280 / #e5e7eb / #f9fafb`, teal accent `#0f766e`,
  plus green, amber, red for status only. Status is always written out as text too.
- Radius 8px everywhere. One shadow, used only for dialogs.

## Times and time zones

The API returns datetimes without an offset. They are UTC, so `parseApiDate` appends `Z` before
parsing and every screen shows local time. When sending times (admin flight form, search
filters), the client converts to UTC first. The backend now normalises any offset it receives to
UTC before storing it, so this is a client-side safety net rather than a workaround for a bug.

## Known gaps

- No pagination: every list loads in full.
- No automated tests for the UI yet.

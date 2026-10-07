import pytest


@pytest.fixture
def airports(client, admin_headers) -> dict[str, int]:
    ids = {}
    for code, city in [("LHE", "Lahore"), ("KHI", "Karachi"), ("ISB", "Islamabad")]:
        r = client.post(
            "/airports", json={"name": code, "city": city, "country": "PK"}, headers=admin_headers
        )
        ids[code] = r.json()["id"]
    return ids


def _flight(client, admin_headers, dep, arr, day, price="100.00", flight_class="economy"):
    """A two-hour flight departing at 08:00 UTC on 2030-06-<day>."""
    r = client.post(
        "/flights",
        json={
            "airline_name": "PIA",
            "departure_airport": dep,
            "arrival_airport": arr,
            "start_time": f"2030-06-{day:02d}T08:00:00Z",
            "end_time": f"2030-06-{day:02d}T10:00:00Z",
            "price": price,
            "total_seats": 100,
            "available_seats": 100,
            "flight_class": flight_class,
        },
        headers=admin_headers,
    )
    return r.json()["id"]


def _search(client, **params) -> set[int]:
    r = client.get("/flights/search", params=params)
    assert r.status_code == 200
    return {f["id"] for f in r.json()}


def test_no_filters_returns_every_flight(client, admin_headers, airports):
    a = _flight(client, admin_headers, airports["LHE"], airports["KHI"], 10)
    b = _flight(client, admin_headers, airports["KHI"], airports["ISB"], 11)
    assert _search(client) == {a, b}


def test_route_filters_match_direction_exactly(client, admin_headers, airports):
    lhe_khi = _flight(client, admin_headers, airports["LHE"], airports["KHI"], 10)
    khi_lhe = _flight(client, admin_headers, airports["KHI"], airports["LHE"], 10)
    lhe_isb = _flight(client, admin_headers, airports["LHE"], airports["ISB"], 10)

    both = {"departure_airport": airports["LHE"], "arrival_airport": airports["KHI"]}
    assert _search(client, **both) == {lhe_khi}
    assert _search(client, departure_airport=airports["LHE"]) == {lhe_khi, lhe_isb}
    assert _search(client, arrival_airport=airports["LHE"]) == {khi_lhe}


def test_date_window_needs_departure_after_start_and_arrival_before_end(
    client, admin_headers, airports
):
    route = (airports["LHE"], airports["KHI"])
    day10 = _flight(client, admin_headers, *route, 10)
    day11 = _flight(client, admin_headers, *route, 11)
    day12 = _flight(client, admin_headers, *route, 12)

    window = {"start_time": "2030-06-11T00:00:00Z", "end_time": "2030-06-11T23:59:59Z"}
    assert _search(client, **window) == {day11}

    from_the_11th = {"start_time": "2030-06-11T00:00:00Z"}
    assert _search(client, **from_the_11th) == {day11, day12}

    # Arrival is at 10:00, so a window ending at 09:00 excludes that day's flight.
    assert _search(client, end_time="2030-06-10T09:00:00Z") == set()
    assert day10 in _search(client, end_time="2030-06-10T10:00:00Z")


def test_class_and_price_filters(client, admin_headers, airports):
    route = (airports["LHE"], airports["KHI"])
    cheap = _flight(client, admin_headers, *route, 10, price="80.00")
    mid = _flight(client, admin_headers, *route, 10, price="150.00")
    business = _flight(client, admin_headers, *route, 10, price="400.00", flight_class="business")

    assert _search(client, flight_class="business") == {business}
    assert _search(client, max_price="100.00") == {cheap}
    assert _search(client, min_price="100.00", max_price="200.00") == {mid}
    assert _search(client, min_price="80.00", max_price="80.00") == {cheap}  # bounds are inclusive


def test_filters_combine_with_and_and_no_match_is_an_empty_list(client, admin_headers, airports):
    wanted = _flight(client, admin_headers, airports["LHE"], airports["KHI"], 10, price="120.00")
    _flight(client, admin_headers, airports["LHE"], airports["KHI"], 20, price="120.00")
    _flight(client, admin_headers, airports["LHE"], airports["ISB"], 10, price="120.00")

    found = _search(
        client,
        departure_airport=airports["LHE"],
        arrival_airport=airports["KHI"],
        start_time="2030-06-10T00:00:00Z",
        end_time="2030-06-10T23:59:59Z",
        max_price="150.00",
    )
    assert found == {wanted}
    assert _search(client, departure_airport=airports["ISB"]) == set()  # 200 and [], not 404

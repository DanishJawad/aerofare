from datetime import timedelta

import pytest

from scripts.seed_flights import DEPARTURE_SPREAD_DAYS, FIRST_DEPARTURE, generate_flights


def test_the_same_seed_gives_the_same_flights():
    """The benchmark is only comparable between runs if the data is identical."""
    assert list(generate_flights(500, 60, seed=7)) == list(generate_flights(500, 60, seed=7))
    assert list(generate_flights(500, 60, seed=7)) != list(generate_flights(500, 60, seed=8))


def test_every_generated_flight_is_one_the_api_would_accept():
    flights = list(generate_flights(5_000, 12))

    assert len(flights) == 5_000
    for f in flights:
        assert 1 <= f["departure_airport"] <= 12
        assert 1 <= f["arrival_airport"] <= 12
        assert f["departure_airport"] != f["arrival_airport"]
        assert f["end_time"] > f["start_time"]
        assert FIRST_DEPARTURE <= f["start_time"] < FIRST_DEPARTURE + timedelta(days=DEPARTURE_SPREAD_DAYS)
        assert 0 <= f["available_seats"] <= f["total_seats"]
        assert f["price"] > 0


def test_routes_are_spread_over_every_airport_pair():
    """Rejecting 'same airport' by skipping a value must not bias which airports
    get picked: every airport should appear as a departure and an arrival."""
    flights = list(generate_flights(5_000, 5))
    assert {f["departure_airport"] for f in flights} == {1, 2, 3, 4, 5}
    assert {f["arrival_airport"] for f in flights} == {1, 2, 3, 4, 5}


def test_fewer_than_two_airports_is_an_error():
    with pytest.raises(ValueError):
        list(generate_flights(1, 1))

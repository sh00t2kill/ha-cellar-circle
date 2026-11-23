from conftest import load

parse = load("parse")

# Shapes copied from a real reply (spike, 2026-11-23), names changed.
PEOPLE = {
    "total": 3,
    "people": [
        {"name": "A", "iOweThemWine": {"bottles": 6}, "theyOweMeWine": {"bottles": 0}, "money": None},
        {"name": "B", "iOweThemWine": {"bottles": 0}, "theyOweMeWine": {"bottles": 2}, "money": {"net": {"cents": 5500, "currency": "AUD", "display": "$55.00"}, "direction": "they owe me", "overdueDays": 0}},
        {"name": "C", "iOweThemWine": {"bottles": 1}, "theyOweMeWine": {"bottles": 0}, "money": {"net": {"cents": 1200, "currency": "AUD", "display": "$12.00"}, "direction": "I owe them", "overdueDays": 3}},
    ],
}
ITEMS = {"total": 2, "items": [{"what": "Collect 2 bottles", "community": "X", "url": "https://x/1"}, {"what": "Pay B $55.00", "community": "X", "url": "https://x/2"}]}


def test_totals():
    s = parse.summarise(ITEMS, PEOPLE, {"total": 4, "offers": []})
    assert (s.open_items_total, s.open_offers_total) == (2, 4)
    assert (s.bottles_i_owe, s.bottles_owed_to_me) == (7, 2)
    assert (s.money_owed_to_me_cents, s.money_i_owe_cents) == (5500, 1200)
    assert s.currency == "AUD"
    assert s.people[1]["money"] == "they owe me $55.00"


def test_empty_replies():
    s = parse.summarise({}, {}, {})
    assert (s.open_items_total, s.bottles_i_owe, s.money_i_owe_cents, s.open_offers_total) == (0, 0, 0, 0)


def test_swaps():
    swaps = {"total": 3, "listings": [{"wine": "2019 Shiraz", "producer": "P", "lookingFor": "a nebbiolo", "url": "https://x/s/1"}, {"wine": "2020 Pinot", "producer": "Q", "url": "https://x/s/2"}]}
    mine = {"total": 1, "listings": [{"wine": "2019 Shiraz", "producer": "P", "lookingFor": None, "url": "https://x/s/1"}]}
    s = parse.summarise(ITEMS, PEOPLE, {"total": 0}, swaps, mine)
    assert (s.open_swaps_total, s.my_swaps_total) == (3, 1)
    assert s.open_swaps[0]["wants"] == "a nebbiolo" and s.open_swaps[1]["wants"] == ""
    assert s.my_swaps[0]["wine"] == "2019 Shiraz"


def test_swaps_missing_is_zero():
    s = parse.summarise(ITEMS, PEOPLE, {"total": 0})
    assert (s.open_swaps_total, s.my_swaps_total, s.open_swaps) == (0, 0, [])

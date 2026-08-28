from enum import Enum

class FlightClass(str, Enum):
    ECONOMY = "economy"
    BUSINESS = "business"
    FIRST = "first"

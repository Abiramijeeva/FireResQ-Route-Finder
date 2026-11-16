# Sample road network. All weights are estimated travel times in minutes.
# Roads are undirected in this academic demonstration.

ROAD_GRAPH = {
    "H": [("A", 4), ("B", 2)],
    "A": [("H", 4), ("B", 1), ("C", 5), ("D", 9)],
    "B": [("H", 2), ("A", 1), ("C", 8), ("D", 10)],
    "C": [("A", 5), ("B", 8), ("D", 2), ("P", 6)],
    "D": [("B", 10), ("A", 9), ("C", 2), ("P", 3)],
    "P": [("C", 6), ("D", 3)],
}

# Approximate sample-road lengths in kilometers; Dijkstra continues to optimize
# travel time from ROAD_GRAPH rather than these display-only distance values.
ROAD_DISTANCES_KM = {
    "A:H": 3.2,
    "B:H": 1.8,
    "A:B": 1.1,
    "A:C": 4.4,
    "A:D": 7.6,
    "B:C": 6.3,
    "B:D": 8.0,
    "C:D": 1.7,
    "C:P": 5.2,
    "D:P": 2.5,
}

LOCATION_NAMES = {
    "H": "Fire Station",
    "A": "Junction A",
    "B": "Junction B",
    "C": "Junction C",
    "D": "Junction D",
    "P": "Fire Incident Location",
}

LOCATION_DESIGNATIONS = {
    "H": "Fire station",
    "A": "Road junction",
    "B": "Road junction",
    "C": "Road junction",
    "D": "Road junction",
    "P": "Fire incident",
}

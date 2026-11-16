import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch

import app as web_app
from dijkstra import dijkstra, k_shortest_routes, shortest_alternative_route
from graph_data import LOCATION_DESIGNATIONS, LOCATION_NAMES, ROAD_GRAPH
from osm_routing import make_route_options
from trip_tracking import create_trip, get_trip


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.payload = payload

    def json(self):
        return self.payload


class RoutePlannerTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_database_path = web_app.DATABASE_PATH
        web_app.DATABASE_PATH = os.path.join(self.temporary_directory.name, "test.db")
        web_app.initialize_database()
        web_app.app.config["TESTING"] = True
        self.client = web_app.app.test_client()

    def tearDown(self):
        web_app.DATABASE_PATH = self.original_database_path
        self.temporary_directory.cleanup()

    def route_form(self, **overrides):
        form = {
            "action": "find",
            "routing_mode": "demo",
            "source": "H",
            "destination": "P",
            "priority": "Critical",
            "departure_time": "2026-01-01T08:00",
        }
        form.update(overrides)
        return form

    def osm_route_form(self, **overrides):
        form = {
            "action": "find",
            "routing_mode": "osm",
            "source": "H",
            "destination": "P",
            "origin_text": "Kengeri Satellite Town, Bengaluru",
            "hospital_id": "adarsh",
            "destination_mode": "hospital",
            "destination_text": "",
            "origin_lat": "",
            "origin_lon": "",
            "priority": "High",
            "departure_time": "2026-01-01T08:00",
        }
        form.update(overrides)
        return form

    def road_condition_form(self, closed_roads=(), delays=None):
        closed_roads = set(closed_roads)
        delays = delays or {}
        form = {"action": "update_conditions"}
        for first, second, _ in web_app.get_base_roads():
            key = web_app.road_key(first, second)
            if key in closed_roads:
                form[f"close_{key}"] = "on"
            form[f"delay_{key}"] = str(delays.get(key, 0))
        return form

    def history_rows(self):
        with web_app.database_connection() as connection:
            return connection.execute(
                "SELECT * FROM route_history ORDER BY id"
            ).fetchall()

    def make_trip(self):
        return create_trip(
            web_app.DATABASE_PATH,
            "AMB-TEST-1",
            "Dispatch origin",
            12.921,
            77.482,
            "Test Hospital",
            12.925,
            77.485,
            "Critical",
            12_000,
            600,
            json.dumps([[77.482, 12.921], [77.485, 12.925]]),
        )

    @staticmethod
    def sample_geocode():
        return [
            {
                "lat": "12.9210",
                "lon": "77.4820",
                "display_name": "Kengeri Satellite Town, Bengaluru, Karnataka, India",
            }
        ]

    @staticmethod
    def sample_osrm_routes():
        return {
            "code": "Ok",
            "routes": [
                {
                    "duration": 600,
                    "distance": 12000,
                    "geometry": {
                        "coordinates": [
                            [77.4820, 12.9210],
                            [77.4830, 12.9205],
                            [77.4847891, 12.9208444],
                        ]
                    },
                    "legs": [
                        {
                            "steps": [
                                {"duration": 300, "distance": 5000, "name": "Main Road"},
                                {"duration": 300, "distance": 7000, "name": "Cross Road"},
                            ]
                        }
                    ],
                },
                {
                    "duration": 900,
                    "distance": 18000,
                    "geometry": {
                        "coordinates": [
                            [77.4820, 12.9210],
                            [77.4860, 12.9230],
                            [77.4847891, 12.9208444],
                        ]
                    },
                    "legs": [
                        {
                            "steps": [
                                {"duration": 900, "distance": 18000, "name": "Central Avenue"}
                            ]
                        }
                    ],
                },
            ],
        }

    def test_route_search_shows_alternative_eta_priority_and_persists_history(self):
        response = self.client.post("/", data=self.route_form())
        content = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Alternative route", content)
        self.assertIn("Critical severity", content)
        self.assertIn("2026-01-01 08:13", content)
        rows = self.history_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["duration_minutes"], 13)
        self.assertEqual(rows[0]["priority"], "Critical")
        self.assertEqual(rows[0]["arrival_time"], "2026-01-01T08:13")
        self.assertEqual(rows[0]["estimated_distance_km"], 11.5)
        self.assertEqual(rows[0]["severity"], "Critical")
        self.assertEqual(rows[0]["source"], "H")
        self.assertEqual(rows[0]["destination"], "P")
        self.assertEqual(json.loads(rows[0]["route_codes"]), ["H", "B", "A", "C", "D", "P"])
        self.assertIn("11.5 km", content)
        self.assertIn("SAVED JOURNEYS", content)
        self.assertIn("AVERAGE ESTIMATED TIME", content)
        self.assertIn("13 min", content)

    def test_fire_resq_dashboard_shows_fire_workflow_and_severity_levels(self):
        response = self.client.get("/")
        content = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("FireResQ", content)
        self.assertIn("Starting Fire Station", content)
        self.assertIn("Destination Fire Incident", content)
        self.assertIn("Find Shortest Route", content)
        self.assertIn("Intelligent Fire Emergency Route Finder", content)
        self.assertIn("Faster Routes. Smarter Emergency Response.", content)
        self.assertIn('src="/static/images/fire-engine.jpg"', content)
        self.assertIn('src="/static/images/fire-station.jpg"', content)
        self.assertIn('src="/static/images/fire-rescue.jpg"', content)
        self.assertIn("CC BY-SA 4.0", content)
        self.assertIn("Fire Station", content)
        self.assertIn("Fire Incident", content)
        self.assertIn("Available demo designations", content)
        for code, name in LOCATION_NAMES.items():
            self.assertIn(
                f"<span>{LOCATION_DESIGNATIONS[code]}</span>{code} — {name}",
                content,
            )
        for severity in ("Low", "Medium", "High", "Critical"):
            self.assertIn(f">{severity}<", content)
        self.assertNotIn("Ambulance", content)
        self.assertNotIn("Hospital", content)
        self.assertNotIn("Patient Location", content)
        for image in ("fire-engine.jpg", "fire-station.jpg", "fire-rescue.jpg"):
            with self.subTest(image=image):
                image_response = self.client.get(f"/static/images/{image}")
                status_code = image_response.status_code
                image_response.close()
                self.assertEqual(status_code, 200)

    def test_each_sample_location_pair_has_a_distinct_alternative(self):
        for source in ROAD_GRAPH:
            for destination in ROAD_GRAPH:
                if source == destination:
                    continue
                shortest, _ = dijkstra(ROAD_GRAPH, source, destination)
                alternative, duration = shortest_alternative_route(
                    ROAD_GRAPH, source, destination, shortest
                )
                self.assertIsNotNone(alternative, (source, destination))
                self.assertNotEqual(alternative, shortest)
                self.assertGreaterEqual(duration, 0)

    def test_demo_finds_up_to_three_unique_routes_in_duration_order(self):
        routes = k_shortest_routes(ROAD_GRAPH, "H", "P", limit=3)

        self.assertEqual(len(routes), 3)
        self.assertEqual(len({tuple(path) for path, _ in routes}), 3)
        self.assertEqual([duration for _, duration in routes], [13, 14, 14])

    def test_osrm_options_are_limited_to_three_distinct_geometries(self):
        route_template = self.sample_osrm_routes()["routes"][0]
        routes = []
        for index in range(5):
            route = json.loads(json.dumps(route_template))
            route["duration"] += index * 60
            route["geometry"]["coordinates"][1][0] += index * 0.01
            routes.append(route)

        options = make_route_options(
            routes,
            {"display_name": "Start", "lat": 12.9, "lon": 77.4},
            {
                "name": "Hospital",
                "display_name": "Hospital",
                "lat": 12.91,
                "lon": 77.5,
            },
        )

        self.assertEqual(len(options), 3)
        self.assertEqual(
            [route["duration_seconds"] for route in options],
            sorted(route["duration_seconds"] for route in options),
        )
        self.assertEqual(
            len({tuple(map(tuple, route["geometry"])) for route in options}), 3
        )

    def test_selected_alternative_is_recorded_in_history(self):
        self.client.post("/", data=self.route_form())
        response = self.client.post(
            "/", data=self.route_form(action="select_route", route_index="1")
        )

        self.assertEqual(response.status_code, 200)
        rows = self.history_rows()
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(
            json.loads(rows[0]["route_codes"]), json.loads(rows[1]["route_codes"])
        )

    def test_traffic_increase_changes_calculated_route(self):
        response = self.client.post(
            "/",
            data=self.road_condition_form(delays={"A:C": 20}),
        )
        self.assertIn("Road conditions updated and saved.", response.get_data(as_text=True))

        graph = web_app.get_effective_graph(web_app.load_road_conditions())
        path, duration = dijkstra(graph, "H", "P")
        self.assertIsNotNone(path)
        self.assertEqual(duration, 15)
        self.assertEqual(web_app.load_road_conditions()["A:C"]["added_minutes"], 20)
        route_response = self.client.post("/", data=self.route_form())
        self.assertIn(">15 <span>min</span>", route_response.get_data(as_text=True))

    def test_closures_can_make_destination_unreachable_and_can_be_restored(self):
        self.client.post(
            "/",
            data=self.road_condition_form(closed_roads={"A:H", "B:H"}),
        )
        response = self.client.post("/", data=self.route_form())
        self.assertIn(
            "No route exists between these locations",
            response.get_data(as_text=True),
        )
        self.assertEqual(self.history_rows(), [])

        self.client.post("/", data={"action": "restore_conditions"})
        graph = web_app.get_effective_graph(web_app.load_road_conditions())
        path, duration = dijkstra(graph, "H", "P")
        self.assertEqual(duration, 13)
        self.assertIsNotNone(path)

    def test_invalid_traffic_increase_is_rejected_without_saving(self):
        response = self.client.post(
            "/", data=self.road_condition_form(delays={"A:C": -1})
        )

        self.assertIn("whole numbers from 0 to 10000", response.get_data(as_text=True))
        self.assertEqual(web_app.load_road_conditions()["A:C"]["added_minutes"], 0)

    def test_history_and_conditions_survive_database_reinitialization(self):
        self.client.post("/", data=self.route_form(priority="High"))
        self.client.post("/", data=self.road_condition_form(delays={"A:C": 7}))

        web_app.initialize_database()

        self.assertEqual(len(self.history_rows()), 1)
        self.assertEqual(self.history_rows()[0]["priority"], "High")
        self.assertEqual(web_app.load_road_conditions()["A:C"]["added_minutes"], 7)

    def test_history_distance_column_migrates_without_losing_existing_journeys(self):
        with web_app.database_connection() as connection:
            connection.execute("DROP TABLE route_history")
            connection.execute(
                """
                CREATE TABLE route_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    route_codes TEXT NOT NULL,
                    duration_minutes INTEGER NOT NULL,
                    priority TEXT NOT NULL,
                    departure_time TEXT NOT NULL,
                    arrival_time TEXT NOT NULL,
                    searched_at TEXT NOT NULL,
                    data_source TEXT NOT NULL DEFAULT 'demo'
                )
                """
            )
            connection.execute(
                """
                INSERT INTO route_history (
                    source, destination, route_codes, duration_minutes, priority,
                    departure_time, arrival_time, searched_at, data_source
                ) VALUES ('H', 'P', ?, 13, 'High', '2026-01-01T08:00',
                          '2026-01-01T08:13', '2026-01-01T07:00:00', 'demo')
                """,
                (json.dumps(["H", "B", "A", "C", "D", "P"]),),
            )

        web_app.initialize_database()

        migrated = self.history_rows()[0]
        self.assertEqual(migrated["duration_minutes"], 13)
        self.assertIsNone(migrated["estimated_distance_km"])
        self.assertEqual(migrated["severity"], "High")

    def test_invalid_route_values_are_rejected_without_history(self):
        for values, error in (
            ({"priority": "Urgent"}, "valid fire severity"),
            ({"source": "unknown"}, "start at Fire Station H"),
            (
                {"source": "P", "destination": "H"},
                "end at Fire Incident P",
            ),
            ({"departure_time": "not-a-date"}, "valid departure date"),
        ):
            response = self.client.post("/", data=self.route_form(**values))
            self.assertIn(error, response.get_data(as_text=True))
        self.assertEqual(self.history_rows(), [])

    @patch("osm_routing.requests.get")
    def test_osm_route_displays_map_distance_eta_priority_and_history(
        self, get
    ):
        get.side_effect = [
            FakeResponse(200, self.sample_geocode()),
            FakeResponse(200, self.sample_osrm_routes()),
        ]

        response = self.client.post("/", data=self.osm_route_form())
        content = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("External OpenStreetMap / OSRM road-route estimate", content)
        self.assertIn(
            "Dijkstra is not used to calculate these mapped routes", content
        )
        self.assertIn("no live traffic", content)
        self.assertIn("Alternative 1", content)
        self.assertIn("12.0 km", content)
        self.assertIn("2026-01-01 08:10", content)
        self.assertIn('id="osm-map"', content)
        self.assertIn("map-tiles.js", content)
        self.assertNotIn("cartocdn.com", content)
        tile_script = self.client.get("/static/map-tiles.js")
        self.assertEqual(tile_script.status_code, 200)
        tile_script_content = tile_script.get_data(as_text=True)
        tile_script.close()
        self.assertIn("attribution: config.attribution", tile_script_content)
        self.assertIn("maxZoom: config.maxZoom", tile_script_content)
        self.assertNotIn("CARTO", tile_script_content)
        self.assertIn(
            'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
            content,
        )
        self.assertIn("OpenStreetMap contributors", content)
        self.assertIn("strict-origin-when-cross-origin", content)
        rows = self.history_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["source"], "Kengeri Satellite Town, Bengaluru, Karnataka, India"
        )
        self.assertEqual(rows[0]["destination"], "Adarsh Hospital")
        self.assertEqual(rows[0]["duration_minutes"], 10)
        self.assertEqual(rows[0]["estimated_distance_km"], 12.0)
        self.assertEqual(rows[0]["priority"], "High")
        self.assertEqual(rows[0]["data_source"], "osm_osrm")
        self.assertEqual(
            json.loads(rows[0]["route_codes"])[-1], "Adarsh Hospital"
        )
        osrm_call = get.call_args_list[1]
        self.assertIn(
            "/route/v1/driving/77.482,12.921;77.4847891,12.9208444",
            osrm_call.args[0],
        )
        self.assertEqual(osrm_call.kwargs["params"]["geometries"], "geojson")
        self.assertEqual(osrm_call.kwargs["params"]["alternatives"], "3")
        self.assertIn("12.0 km", content)

    def test_homepage_uses_valid_configured_tile_provider_and_attribution(self):
        with patch.dict(
            os.environ,
            {
                "MAP_TILE_URL": "https://tiles.example.test/{z}/{x}/{y}.png",
                "MAP_TILE_ATTRIBUTION": "Example tile provider",
                "MAP_TILE_MAX_ZOOM": "17",
            },
        ):
            response = self.client.get("/")

        content = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("https://tiles.example.test/{z}/{x}/{y}.png", content)
        self.assertIn("Example tile provider", content)
        self.assertIn('"maxZoom": 17', content)

    def test_invalid_tile_provider_configuration_is_reported(self):
        with patch.dict(
            os.environ,
            {
                "MAP_TILE_URL": "http://tiles.example.test/{z}/{x}/{y}.png",
                "MAP_TILE_ATTRIBUTION": "Example tile provider",
                "MAP_TILE_MAX_ZOOM": "17",
            },
        ):
            with self.assertRaisesRegex(ValueError, "must be an HTTPS tile URL"):
                self.client.get("/")

    @patch("app.get_osrm_routes")
    @patch("app.geocode_location")
    def test_osm_fire_route_starts_at_station_and_ends_at_incident(
        self, geocode, osrm
    ):
        geocode.return_value = {
            "lat": 12.925,
            "lon": 77.495,
            "display_name": "Fire incident, Bengaluru",
        }
        osrm.return_value = self.sample_osrm_routes()["routes"]

        response = self.client.post(
            "/",
            data=self.osm_route_form(
                origin_text="Fire incident, Bengaluru",
                station_mode="fire_station",
                fire_station_id="kengeri-fire-station",
                destination_text="",
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(osrm.call_args.args[0]["display_name"], "Kengeri Fire Station, Kengeri, Bengaluru, Karnataka, India")
        self.assertEqual(osrm.call_args.args[1]["display_name"], "Fire incident, Bengaluru")
        history = self.history_rows()[0]
        self.assertEqual(history["source"], "Kengeri Fire Station, Kengeri, Bengaluru, Karnataka, India")
        self.assertEqual(history["destination"], "Fire incident, Bengaluru")

    @patch("app.get_osrm_routes")
    @patch("app.geocode_location")
    def test_current_location_is_origin_and_incident_remains_destination(
        self, geocode, osrm
    ):
        incident_name = "Kengeri Satellite Town, Bengaluru"
        geocode.return_value = {
            "lat": 12.925,
            "lon": 77.495,
            "display_name": incident_name,
        }
        osrm.return_value = self.sample_osrm_routes()["routes"]

        response = self.client.post(
            "/",
            data=self.osm_route_form(
                incident_text=incident_name,
                origin_text="",
                station_mode="current_location",
                station_lat="12.9179",
                station_lon="77.4817",
                station_label="Your current location (12.917900, 77.481700)",
                destination_text="",
                origin_lat="",
                origin_lon="",
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(osrm.call_args.args[0]["lat"], 12.9179)
        self.assertEqual(osrm.call_args.args[0]["lon"], 77.4817)
        self.assertEqual(osrm.call_args.args[0]["origin_type"], "current_location")
        self.assertEqual(osrm.call_args.args[1]["display_name"], incident_name)
        self.assertEqual(geocode.call_count, 1)
        history = self.history_rows()[0]
        self.assertTrue(history["source"].startswith("Your current location"))
        self.assertEqual(history["destination"], incident_name)
        self.assertIn("not a registered fire station", response.get_data(as_text=True))

    @patch("app.get_osrm_routes")
    @patch("app.geocode_location")
    def test_selected_station_uses_record_coordinates_without_geocoding_station(
        self, geocode, osrm
    ):
        incident_name = "Kengeri Satellite Town, Bengaluru"
        geocode.return_value = {
            "lat": 12.925,
            "lon": 77.495,
            "display_name": incident_name,
        }
        osrm.return_value = self.sample_osrm_routes()["routes"]

        response = self.client.post(
            "/",
            data=self.osm_route_form(
                incident_text=incident_name,
                origin_text="",
                station_mode="fire_station",
                fire_station_id="kengeri-fire-station",
                station_text="",
                destination_text="",
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(geocode.call_count, 1)
        self.assertEqual(osrm.call_args.args[0]["lat"], 12.9179)
        self.assertEqual(osrm.call_args.args[0]["lon"], 77.4817)
        self.assertEqual(osrm.call_args.args[1]["display_name"], incident_name)

    @patch("osm_routing.requests.get")
    def test_osrm_request_uses_station_then_incident_coordinates(self, get):
        incident_name = "Kengeri Satellite Town, Bengaluru"
        get.side_effect = [
            FakeResponse(200, [{
                "lat": "12.925",
                "lon": "77.495",
                "display_name": incident_name,
            }]),
            FakeResponse(200, {
                "code": "Ok",
                "routes": [{
                    "duration": 600,
                    "distance": 4500,
                    "geometry": {
                        "coordinates": [
                            [77.4817, 12.9179],
                            [77.495, 12.925],
                        ]
                    },
                    "legs": [{"steps": []}],
                }],
            }),
        ]

        response = self.client.post(
            "/",
            data=self.osm_route_form(
                incident_text=incident_name,
                origin_text="",
                station_mode="fire_station",
                fire_station_id="kengeri-fire-station",
                station_text="",
                destination_text="",
            ),
        )

        self.assertEqual(response.status_code, 200)
        route_call = get.call_args_list[1]
        self.assertIn(
            "/route/v1/driving/77.4817,12.9179;77.495,12.925",
            route_call.args[0],
        )
        self.assertEqual(route_call.kwargs["params"]["overview"], "full")
        self.assertEqual(route_call.kwargs["params"]["geometries"], "geojson")
        content = response.get_data(as_text=True)
        self.assertIn(
            "Kengeri Fire Station, Kengeri, Bengaluru, Karnataka, India"
            " → Kengeri Satellite Town, Bengaluru",
            content,
        )
        history = self.history_rows()[0]
        self.assertEqual(
            history["source"],
            "Kengeri Fire Station, Kengeri, Bengaluru, Karnataka, India",
        )
        self.assertEqual(history["destination"], incident_name)

    @patch("osm_routing.requests.get")
    def test_selected_osrm_alternative_is_saved_and_successful_geocode_is_cached(
        self, get
    ):
        get.side_effect = [
            FakeResponse(200, self.sample_geocode()),
            FakeResponse(200, self.sample_osrm_routes()),
            FakeResponse(200, self.sample_osrm_routes()),
        ]
        self.client.post("/", data=self.osm_route_form())
        response = self.client.post(
            "/",
            data=self.osm_route_form(action="select_route", route_index="1"),
        )

        self.assertEqual(response.status_code, 200)
        rows = self.history_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["duration_minutes"], 15)
        self.assertEqual(rows[1]["data_source"], "osm_osrm")
        self.assertEqual(get.call_count, 3)

    @patch("osm_routing.requests.get")
    def test_custom_worldwide_destination_is_geocoded_and_routed(self, get):
        get.side_effect = [
            FakeResponse(200, self.sample_geocode()),
            FakeResponse(
                200,
                [{
                    "lat": "13.0827",
                    "lon": "80.2707",
                    "display_name": "Apollo Hospitals, Chennai, India",
                }],
            ),
            FakeResponse(200, {
                "code": "Ok",
                "routes": [{
                    "duration": 1200,
                    "distance": 25000,
                    "geometry": {"coordinates": [[77.482, 12.921], [80.2707, 13.0827]]},
                    "legs": [{"steps": [{"duration": 1200, "distance": 25000, "name": "Road"}]}],
                }],
            }),
        ]

        response = self.client.post(
            "/",
            data=self.osm_route_form(
                destination_mode="custom",
                destination_text="Apollo Hospitals, Chennai, India",
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Apollo Hospitals, Chennai, India", response.get_data(as_text=True))
        self.assertEqual(get.call_count, 3)
        self.assertIn("13.0827", get.call_args_list[2].args[0])
        history = self.history_rows()[0]
        self.assertEqual(history["destination"], "Apollo Hospitals, Chennai, India")
        self.assertEqual(history["duration_minutes"], 20)

    @patch("osm_routing.requests.get")
    def test_current_location_coordinates_skip_geocoder(self, get):
        get.return_value = FakeResponse(200, {
            "code": "Ok",
            "routes": [{
                "duration": 600,
                "distance": 2000,
                "geometry": {"coordinates": [[77.482, 12.921], [77.4847891, 12.9208444]]},
                "legs": [{"steps": [{"duration": 600, "distance": 2000, "name": "Road"}]}],
            }],
        })

        response = self.client.post(
            "/",
            data=self.osm_route_form(
                origin_text="Current location (12.921000, 77.482000)",
                origin_lat="12.921",
                origin_lon="77.482",
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(get.call_count, 1)
        self.assertTrue(
            self.history_rows()[0]["source"].startswith("Current location")
        )
        self.assertNotIn("12.921", self.history_rows()[0]["source"])
        self.assertIn("77.482,12.921", get.call_args.args[0])

    @patch("osm_routing.requests.get")
    def test_duplicate_osrm_geometry_is_removed_and_single_route_is_explained(
        self, get
    ):
        duplicate_route = self.sample_osrm_routes()["routes"][0]
        get.side_effect = [
            FakeResponse(200, self.sample_geocode()),
            FakeResponse(200, {
                "code": "Ok",
                "routes": [duplicate_route, dict(duplicate_route)],
            }),
        ]

        response = self.client.post("/", data=self.osm_route_form())
        content = response.get_data(as_text=True)

        self.assertIn("Only one distinct route is available", content)
        self.assertNotIn("Alternative 1", content)
        self.assertIn(
            "OSRM did not provide turn-by-turn maneuvers", content
        )
        self.assertNotIn("Read directions aloud", content)

    @patch("osm_routing.requests.get")
    def test_voice_directions_use_osrm_maneuver_data_only(self, get):
        route = self.sample_osrm_routes()["routes"][0]
        route["legs"][0]["steps"][0]["maneuver"] = {
            "type": "turn",
            "modifier": "left",
        }
        get.side_effect = [
            FakeResponse(200, self.sample_geocode()),
            FakeResponse(200, {"code": "Ok", "routes": [route]}),
        ]

        response = self.client.post("/", data=self.osm_route_form())
        content = response.get_data(as_text=True)

        self.assertIn("Turn left onto Main Road", content)
        self.assertIn("Read directions aloud", content)
        self.assertIn("Only one distinct route is available", content)

    @patch("osm_routing.requests.get")
    def test_invalid_geolocation_coordinates_are_rejected(self, get):
        response = self.client.post(
            "/",
            data=self.osm_route_form(
                origin_text="Current location",
                origin_lat="999",
                origin_lon="77.482",
            ),
        )

        self.assertIn("coordinates are invalid", response.get_data(as_text=True))
        get.assert_not_called()
        self.assertEqual(self.history_rows(), [])

    @patch("osm_routing.requests.get")
    def test_invalid_address_does_not_request_osrm_or_save_history(self, get):
        get.return_value = FakeResponse(200, [])

        response = self.client.post("/", data=self.osm_route_form())

        self.assertIn("Address not found", response.get_data(as_text=True))
        self.assertEqual(get.call_count, 1)
        self.assertEqual(self.history_rows(), [])

    @patch("app.geocode_location")
    def test_unmatched_custom_station_suggests_area_station_search(self, geocode):
        geocode.side_effect = web_app.RoutingServiceError(
            "Address not found. Enter a more complete address, city, landmark, or place name.",
            400,
        )
        response = self.client.post(
            "/",
            data=self.osm_route_form(
                station_mode="custom_station",
                station_text=(
                    "Fire Station Virudhunagar, HXV3+CHP, Sivagami Puram, "
                    "Virudhunagar, Tamil Nadu 626001, India"
                ),
                incident_text="Virudhunagar Bus Stand, Virudhunagar, Tamil Nadu, India",
                origin_text="",
            ),
        )

        content = response.get_data(as_text=True)
        self.assertIn("Could not locate the starting fire station", content)
        self.assertIn("Search OpenStreetMap by town or area", content)
        self.assertIn("Virudhunagar", content)
        self.assertEqual(self.history_rows(), [])

    @patch("osm_routing.requests.get")
    def test_worldwide_origin_is_not_restricted_to_kengeri(self, get):
        get.side_effect = [
            FakeResponse(
                200,
                [{
                    "lat": "28.6139",
                    "lon": "77.2090",
                    "display_name": "New Delhi, India",
                }],
            ),
            FakeResponse(200, {
                "code": "Ok",
                "routes": [{
                    "duration": 3600,
                    "distance": 50000,
                    "geometry": {"coordinates": [[77.2090, 28.6139], [77.50, 28.70]]},
                    "legs": [{"steps": [{"duration": 3600, "distance": 50000, "name": "Highway"}]}],
                }],
            }),
        ]

        response = self.client.post(
            "/", data=self.osm_route_form(origin_text="New Delhi, India")
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("New Delhi, India", response.get_data(as_text=True))
        self.assertEqual(self.history_rows()[0]["data_source"], "osm_osrm")
        self.assertEqual(
            get.call_args_list[0].kwargs["params"]["q"], "New Delhi, India"
        )
        self.assertNotIn("countrycodes", get.call_args_list[0].kwargs["params"])

    @patch("osm_routing.requests.get")
    def test_osrm_no_route_is_reported_without_saving_history(self, get):
        get.side_effect = [
            FakeResponse(200, self.sample_geocode()),
            FakeResponse(200, {"code": "NoRoute", "routes": []}),
        ]

        response = self.client.post("/", data=self.osm_route_form())

        self.assertIn("could not find a drivable route", response.get_data(as_text=True))
        self.assertEqual(self.history_rows(), [])

    @patch("osm_routing.requests.get")
    def test_public_geocoder_rate_limit_is_reported(self, get):
        get.return_value = FakeResponse(429, {})

        response = self.client.post("/", data=self.osm_route_form())

        self.assertIn("rate-limited", response.get_data(as_text=True))
        self.assertEqual(self.history_rows(), [])

    @patch("osm_routing.requests.get")
    def test_osrm_timeout_is_explicit_and_does_not_fall_back_to_demo(self, get):
        import requests

        get.side_effect = [
            FakeResponse(200, self.sample_geocode()),
            requests.Timeout(),
        ]

        response = self.client.post("/", data=self.osm_route_form())
        content = response.get_data(as_text=True)

        self.assertIn("OSRM route request timed out", content)
        self.assertNotIn("Shortest route", content)
        self.assertEqual(self.history_rows(), [])

    def test_missing_osm_location_and_unknown_mode_are_rejected(self):
        missing_origin = self.client.post(
            "/", data=self.osm_route_form(origin_text="")
        )
        unknown_mode = self.client.post(
            "/", data=self.osm_route_form(routing_mode="google")
        )

        self.assertIn(
            "destination fire incident address",
            missing_origin.get_data(as_text=True),
        )
        self.assertIn("valid routing mode", unknown_mode.get_data(as_text=True))
        self.assertEqual(self.history_rows(), [])

    @patch("app.get_osrm_routes")
    @patch("app.geocode_location")
    def test_dispatch_creation_uses_real_route_and_issues_separate_private_links(
        self, geocode, osrm
    ):
        geocode.side_effect = [
            {
                "lat": 12.921,
                "lon": 77.482,
                "display_name": "Dispatch origin, Bengaluru",
            },
            {
                "lat": 12.925,
                "lon": 77.485,
                "display_name": "Test Hospital, Bengaluru",
            },
        ]
        osrm.return_value = self.sample_osrm_routes()["routes"]

        response = self.client.post(
            "/dispatch",
            data={
                "ambulance_id": "AMB-42",
                "origin": "Dispatch origin",
                "destination": "Test Hospital",
                "priority": "Critical",
            },
        )

        content = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Fire response planned", content)
        self.assertIn("/trips/", content)
        self.assertIn("Private fire-unit link", content)
        self.assertIn("Private dispatcher link", content)
        self.assertEqual(geocode.call_count, 2)
        with web_app.database_connection() as connection:
            trip = connection.execute("SELECT * FROM trips").fetchone()
        self.assertEqual(trip["ambulance_id"], "AMB-42")
        self.assertEqual(trip["priority"], "Critical")
        self.assertEqual(trip["status"], "planned")
        self.assertNotIn(trip["driver_token_hash"], content)
        self.assertNotIn(trip["viewer_token_hash"], content)

    @patch("app.get_osrm_routes")
    @patch("app.geocode_location")
    def test_fire_dispatch_routes_from_selected_station_to_incident(
        self, geocode, osrm
    ):
        geocode.return_value = {
            "lat": 12.925,
            "lon": 77.495,
            "display_name": "Fire incident, Bengaluru",
        }
        osrm.return_value = self.sample_osrm_routes()["routes"]

        response = self.client.post(
            "/dispatch",
            data={
                "fire_unit_id": "FIRE-42",
                "fire_station": "Kengeri Fire Station",
                "fire_station_lat": "12.9179",
                "fire_station_lon": "77.4817",
                "incident": "Fire incident, Bengaluru",
                "severity": "Critical",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("FIRE-42", response.get_data(as_text=True))
        self.assertIn("Critical", response.get_data(as_text=True))
        self.assertEqual(geocode.call_count, 1)
        self.assertEqual(osrm.call_args.args[0]["lat"], 12.9179)
        self.assertEqual(osrm.call_args.args[0]["lon"], 77.4817)
        self.assertEqual(osrm.call_args.args[1]["display_name"], "Fire incident, Bengaluru")
        content = response.get_data(as_text=True)
        map_data = json.loads(
            content.split(
                'id="dispatch-map-data" type="application/json">', 1
            )[1].split("</script>", 1)[0]
        )
        self.assertEqual(map_data["station"]["lat"], 12.9179)
        self.assertEqual(map_data["station"]["lon"], 77.4817)
        self.assertEqual(map_data["incident"]["lat"], 12.925)
        self.assertEqual(map_data["incident"]["lon"], 77.495)
        self.assertEqual(map_data["route"]["geometry"][0], [77.482, 12.921])
        self.assertIn("12.0 km", content)
        self.assertIn("10 min", content)
        with web_app.database_connection() as connection:
            trip = connection.execute("SELECT * FROM trips").fetchone()
        self.assertEqual(trip["fire_unit_id"], "FIRE-42")
        self.assertEqual(trip["severity"], "Critical")
        self.assertEqual(trip["origin_name"], "Kengeri Fire Station")
        self.assertEqual(trip["destination_name"], "Fire incident, Bengaluru")

    def test_dispatch_page_renders_visible_openstreetmap_route_map(self):
        response = self.client.get("/dispatch")
        content = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="dispatch-route-map"', content)
        self.assertIn('class="dispatch-route-map"', content)
        self.assertIn("No calculated route yet.", content)
        self.assertIn("Route details and directions", content)
        self.assertIn(
            'https://tile.openstreetmap.org/{z}/{x}/{y}.png', content
        )
        self.assertIn("OpenStreetMap contributors", content)
        self.assertIn("leaflet@1.9.4/dist/leaflet.css", content)
        self.assertIn("leaflet@1.9.4/dist/leaflet.js", content)
        style_response = self.client.get("/static/style.css")
        styles = style_response.get_data(as_text=True)
        style_response.close()
        self.assertIn(".dispatch-route-map", styles)
        self.assertIn("min-height: 450px", styles)
        self.assertIn("width: 100%", styles)

    @patch("app.get_osrm_routes")
    @patch("app.geocode_location")
    def test_dispatch_creation_accepts_a_selected_osm_hospital_location(
        self, geocode, osrm
    ):
        geocode.return_value = {
            "lat": 12.921,
            "lon": 77.482,
            "display_name": "Dispatch origin, Bengaluru",
        }
        osrm.return_value = self.sample_osrm_routes()["routes"]
        response = self.client.post(
            "/dispatch",
            data={
                "ambulance_id": "AMB-8",
                "origin": "Dispatch origin",
                "destination": "OSM Hospital, Kengeri",
                "destination_lat": "12.925",
                "destination_lon": "77.485",
                "priority": "High",
            },
        )

        self.assertEqual(response.status_code, 200)
        geocode.assert_called_once()
        self.assertEqual(osrm.call_args.args[1]["lat"], 12.925)
        self.assertEqual(osrm.call_args.args[1]["lon"], 77.485)
        self.assertEqual(
            osrm.call_args.args[1]["display_name"], "OSM Hospital, Kengeri"
        )

    def test_trip_access_tokens_enforce_driver_and_dispatcher_roles(self):
        trip_id, driver_token, viewer_token = self.make_trip()
        endpoint = f"/api/trips/{trip_id}"
        self.assertEqual(self.client.get(endpoint).status_code, 401)
        self.assertEqual(
            self.client.get(
                f"/api/trips/{trip_id}/summary",
                headers={"Authorization": f"Bearer {driver_token}"},
            ).status_code,
            401,
        )
        self.assertEqual(
            self.client.post(
                f"/api/trips/{trip_id}/action",
                headers={"Authorization": f"Bearer {viewer_token}"},
                json={"action": "start"},
            ).status_code,
            401,
        )
        authorized = self.client.get(
            endpoint,
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        self.assertEqual(authorized.status_code, 200)
        self.assertEqual(authorized.json["fire_unit_id"], "AMB-TEST-1")
        self.assertEqual(authorized.json["severity"], "Critical")
        self.assertNotIn("ambulance_id", authorized.json)
        self.assertNotIn("priority", authorized.json)
        self.assertNotIn("driver_token_hash", authorized.json)
        self.assertEqual(authorized.headers["Cache-Control"], "no-store, private")
        self.assertEqual(authorized.headers["Referrer-Policy"], "no-referrer")

    def test_driver_and_dispatcher_pages_include_map_tile_configuration(self):
        trip_id, _, _ = self.make_trip()
        tile_url = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"

        for role in ("driver", "dispatcher"):
            with self.subTest(role=role):
                response = self.client.get(f"/trips/{trip_id}/{role}")
                content = response.get_data(as_text=True)
                self.assertEqual(response.status_code, 200)
                self.assertIn(
                    'id="trip-map-tile-config" type="application/json"',
                    content,
                )
                self.assertIn(tile_url, content)
                self.assertIn("OpenStreetMap contributors", content)

    def test_trip_lifecycle_records_gps_summary_and_clears_exact_location(self):
        trip_id, driver_token, viewer_token = self.make_trip()
        headers = {"Authorization": f"Bearer {driver_token}"}
        base = f"/api/trips/{trip_id}"
        started = self.client.post(
            f"{base}/action", headers=headers, json={"action": "start"}
        )
        self.assertEqual(started.status_code, 200)
        self.assertEqual(started.json["status"], "tracking")

        timestamp_ms = time.time() * 1000
        first = self.client.post(
            f"{base}/location",
            headers=headers,
            json={
                "latitude": 12.921,
                "longitude": 77.482,
                "accuracy": 8.5,
                "timestamp": timestamp_ms,
            },
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json["last_accuracy_m"], 8.5)
        self.assertAlmostEqual(first.json["last_lat"], 12.921)

        second = self.client.post(
            f"{base}/location",
            headers=headers,
            json={
                "latitude": 12.922,
                "longitude": 77.482,
                "accuracy": 7,
                "timestamp": timestamp_ms + 10_000,
            },
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json["location_update_count"], 2)
        self.assertGreater(second.json["actual_distance_m"], 100)

        summary = self.client.get(
            f"{base}/summary",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json["location_update_count"], 2)
        self.assertGreater(summary.json["actual_distance_m"], 100)
        self.assertIn("straight-line", summary.json["distance_source"])
        self.assertEqual(
            [event["event_type"] for event in summary.json["events"]],
            ["created", "tracking_started"],
        )
        denied_summary = self.client.get(
            f"{base}/summary",
            headers=headers,
        )
        self.assertEqual(denied_summary.status_code, 401)

        stopped = self.client.post(
            f"{base}/action", headers=headers, json={"action": "stop"}
        )
        self.assertEqual(stopped.json["status"], "stopped")
        self.assertIsNone(stopped.json["last_lat"])
        rejected = self.client.post(
            f"{base}/location",
            headers=headers,
            json={
                "latitude": 12.923,
                "longitude": 77.482,
                "accuracy": 5,
                "timestamp": time.time() * 1000,
            },
        )
        self.assertEqual(rejected.status_code, 422)
        self.assertIn("Start trip tracking", rejected.json["error"])

        completed = self.client.post(
            f"{base}/action", headers=headers, json={"action": "complete"}
        )
        self.assertEqual(completed.json["status"], "completed")
        self.assertIsNone(completed.json["last_lon"])
        self.assertIsNotNone(completed.json["completed_at"])
        persisted = get_trip(web_app.DATABASE_PATH, trip_id)
        self.assertEqual(persisted["location_update_count"], 2)
        self.assertIsNone(persisted["last_lat"])
        final_summary = self.client.get(
            f"{base}/summary",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        self.assertEqual(
            [event["event_type"] for event in final_summary.json["events"]],
            ["created", "tracking_started", "tracking_stopped", "completed"],
        )

    def test_trip_gps_validation_rejects_bad_ranges_stale_and_out_of_order(self):
        trip_id, driver_token, _ = self.make_trip()
        headers = {"Authorization": f"Bearer {driver_token}"}
        url = f"/api/trips/{trip_id}/location"
        self.client.post(
            f"/api/trips/{trip_id}/action",
            headers=headers,
            json={"action": "start"},
        )
        for payload in (
            {"latitude": 91, "longitude": 0, "accuracy": 5, "timestamp": time.time() * 1000},
            {"latitude": 0, "longitude": 181, "accuracy": 5, "timestamp": time.time() * 1000},
            {"latitude": 0, "longitude": 0, "accuracy": -1, "timestamp": time.time() * 1000},
            {"latitude": 0, "longitude": 0, "accuracy": 5, "timestamp": 1},
        ):
            response = self.client.post(url, headers=headers, json=payload)
            self.assertEqual(response.status_code, 422)
        self.assertIn("timestamp", self.client.post(
            url,
            headers=headers,
            json={"latitude": 0, "longitude": 0, "accuracy": 1, "timestamp": "bad"},
        ).json["error"])

    def test_dispatcher_socket_requires_viewer_token_and_receives_live_updates(self):
        trip_id, driver_token, viewer_token = self.make_trip()
        unauthorized_socket = web_app.socketio.test_client(web_app.app)
        denied = unauthorized_socket.emit(
            "subscribe_trip",
            {"trip_id": trip_id, "token": driver_token},
            callback=True,
        )
        self.assertFalse(denied["ok"])
        unauthorized_socket.disconnect()

        dispatcher_socket = web_app.socketio.test_client(web_app.app)
        authorized = dispatcher_socket.emit(
            "subscribe_trip",
            {"trip_id": trip_id, "token": viewer_token},
            callback=True,
        )
        self.assertTrue(authorized["ok"])
        headers = {"Authorization": f"Bearer {driver_token}"}
        self.client.post(
            f"/api/trips/{trip_id}/action",
            headers=headers,
            json={"action": "start"},
        )
        self.client.post(
            f"/api/trips/{trip_id}/location",
            headers=headers,
            json={
                "latitude": 12.921,
                "longitude": 77.482,
                "accuracy": 10,
                "timestamp": time.time() * 1000,
            },
        )
        events = dispatcher_socket.get_received()
        self.assertTrue(any(event["name"] == "trip_update" for event in events))
        dispatcher_socket.disconnect()

    @patch("osm_routing._wait_for_geocoder_slot")
    @patch("osm_routing.requests.get")
    def test_hospital_search_returns_only_public_osm_hospital_details(
        self, get, wait_for_slot
    ):
        get.return_value = FakeResponse(200, [
            {
                "type": "hospital",
                "lat": "12.921",
                "lon": "77.482",
                "display_name": "Test Hospital, Kengeri",
                "namedetails": {"name": "Test Hospital"},
                "address": {"city": "Bengaluru"},
                "extratags": {"phone": "000", "emergency": "yes"},
                "osm_type": "way",
                "osm_id": 123,
            },
            {
                "type": "school",
                "lat": "12.92",
                "lon": "77.48",
                "display_name": "Not a hospital",
            },
        ])

        response = self.client.get("/api/hospitals/search?q=Kengeri")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json["results"]), 1)
        hospital = response.json["results"][0]
        self.assertEqual(hospital["name"], "Test Hospital")
        self.assertEqual(hospital["public_details"], {"phone": "000", "emergency": "yes"})
        self.assertNotIn("beds", hospital["public_details"])
        self.assertNotIn("photo", hospital)
        self.assertTrue(hospital["osm_url"].endswith("/way/123"))
        self.assertEqual(get.call_args.kwargs["params"]["q"], "hospital Kengeri")
        wait_for_slot.assert_called_once()

    @patch("osm_routing._wait_for_geocoder_slot")
    @patch("osm_routing.requests.get")
    def test_hospital_search_uses_only_exactly_verified_hospital_photos(
        self, get, wait_for_slot
    ):
        get.return_value = FakeResponse(200, [
            {
                "type": "hospital",
                "lat": "12.921",
                "lon": "77.482",
                "display_name": "Apollo Hospitals, Bannerghatta Road, Bengaluru",
                "name": "Apollo Hospitals",
                "extratags": {},
            },
            {
                "type": "hospital",
                "lat": "12.922",
                "lon": "77.483",
                "display_name": "Test Hospital, Kengeri",
                "name": "Test Hospital",
                "extratags": {"wikimedia_commons": "File:Test hospital.jpg"},
            },
            {
                "type": "hospital",
                "lat": "12.923",
                "lon": "77.484",
                "display_name": "Other Hospital, Bengaluru",
                "name": "Other Hospital",
                "extratags": {},
            },
            {
                "type": "hospital",
                "lat": "12.924",
                "lon": "77.485",
                "display_name": "Apollo Hospital, Jayanagar, Bengaluru",
                "name": "Apollo Hospital",
                "extratags": {},
            },
        ])

        response = self.client.get("/api/hospitals/search?q=Bengaluru")

        self.assertEqual(response.status_code, 200)
        apollo, tagged, unpictured, other_apollo = response.json["results"]
        self.assertEqual(
            apollo["photo"]["url"],
            "/static/images/apollo-hospitals-bengaluru.jpg",
        )
        self.assertIn("CC BY-SA 4.0", apollo["photo"]["credit"])
        self.assertNotIn("photo", tagged)
        self.assertNotIn("photo", unpictured)
        self.assertNotIn("photo", other_apollo)
        wait_for_slot.assert_called_once()

    @patch("osm_routing._wait_for_geocoder_slot")
    def test_hospital_search_validates_query_and_handles_empty_results(
        self, wait_for_slot
    ):
        short = self.client.get("/api/hospitals/search?q=x")
        self.assertEqual(short.status_code, 400)
        wait_for_slot.assert_not_called()

        with patch(
            "osm_routing.requests.get", return_value=FakeResponse(200, [])
        ):
            empty = self.client.get("/api/hospitals/search?q=Nowhere")
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.json["results"], [])

    @patch("osm_routing._wait_for_geocoder_slot")
    @patch("osm_routing.requests.get")
    def test_fire_station_search_filters_openstreetmap_results(
        self, get, wait_for_slot
    ):
        get.return_value = FakeResponse(200, [
            {
                "type": "fire_station",
                "lat": "12.9179",
                "lon": "77.4817",
                "display_name": "Kengeri Fire Station, Bengaluru",
                "namedetails": {"name": "Kengeri Fire Station"},
                "extratags": {"phone": "0800000000"},
                "osm_type": "node",
                "osm_id": 456,
            },
            {
                "type": "hospital",
                "lat": "12.921",
                "lon": "77.482",
                "display_name": "Not a fire station",
            },
        ])

        response = self.client.get("/api/fire-stations/search?q=Kengeri")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json["results"]), 1)
        station = response.json["results"][0]
        self.assertEqual(station["id"], "osm-node-456")
        self.assertEqual(station["name"], "Kengeri Fire Station")
        self.assertEqual(station["public_details"], {"phone": "0800000000"})
        self.assertEqual(get.call_args.kwargs["params"]["q"], "fire station Kengeri")
        wait_for_slot.assert_called_once()

    @patch("app.geocode_location")
    def test_incident_geocode_endpoint_returns_coordinates_and_display_name(
        self, geocode
    ):
        geocode.return_value = {
            "lat": 12.925,
            "lon": 77.495,
            "display_name": "Kengeri Satellite Town, Bengaluru, India",
        }

        response = self.client.get(
            "/api/geocode?q=Kengeri%20Satellite%20Town%2C%20Bengaluru"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["location"]["lat"], 12.925)
        self.assertEqual(response.json["location"]["lon"], 77.495)
        geocode.assert_called_once_with(
            "Kengeri Satellite Town, Bengaluru", web_app.DATABASE_PATH
        )

    def test_incident_geocode_endpoint_rejects_empty_query(self):
        response = self.client.get("/api/geocode?q=%20")
        self.assertEqual(response.status_code, 400)
        self.assertIn("3 and 256 characters", response.json["error"])


if __name__ == "__main__":
    unittest.main()

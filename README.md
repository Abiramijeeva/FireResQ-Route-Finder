# FireResQ – Intelligent Fire Emergency Route Finder

FireResQ is the existing Flask route-planning project adapted for fire response.
It plans routes from a responding fire station to a fire incident, compares
alternatives, records searches in SQLite, and includes an optional
permission-based fire-unit location-sharing prototype.

**Version: 1.0.0**

> **Educational prototype only.** It is not a certified emergency dispatch
> system. OSRM routes are mapped-road estimates, not live traffic. The sample
> graph is simulated, and its distances are approximate display values.
> OpenStreetMap listings may be incomplete or outdated. Verify all locations
> and never rely on this application to handle a real emergency.

## Features

- **Dijkstra demo:** A six-node road graph uses travel time as the Dijkstra
  weight and Python's `heapq` min-heap priority queue. It displays up to three
  distinct loopless routes with estimated time and approximate sample-road
  distance.
- **Road conditions:** Close sample roads or add simulated delay minutes.
  These controls affect the demo graph only, not OSM/OSRM routes.
- **OSM / OSRM route planner:** Geocode an incident address, choose a fire
  station, compare mapped driving-route alternatives where available, and view
  distance, estimated travel time, ETA, map, and OSRM-provided voice maneuvers.
- **Fire station search:** Search public OpenStreetMap fire station listings
  from the dispatch form. Listings do not verify station availability.
- **Trip history and analytics:** Route searches and severity are stored in
  SQLite. Existing route history and trip records are retained; startup adds
  fire-unit and severity columns to the existing database as needed.
- **Optional location sharing:** A fire-unit operator can explicitly start
  browser GPS sharing with the authorized dispatcher. Socket.IO updates have
  a polling fallback. Only the latest accepted position is retained; this is
  not automatic or real-time vehicle telemetry.

## Run on Windows

Open PowerShell in the project directory and run:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Open <http://127.0.0.1:5000>. Keep the terminal open while using FireResQ;
press **Ctrl+C** to stop the server. The default database is
`instance/routes.db`.

## Configuration

Set these optional environment variables in PowerShell before starting:

```powershell
$env:DATABASE_PATH = "C:\path\to\routes.db"
$env:NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org"
$env:OSRM_BASE_URL = "https://router.project-osrm.org"
$env:PUBLIC_BASE_URL = "https://your-public-host"
```

`PUBLIC_BASE_URL` is only needed when generated private trip links must use a
public HTTPS origin. Defaults use the public Nominatim and OSRM demo services.

The home-page map uses the standard OpenStreetMap tile endpoint by default.
If that service is unavailable on your network, configure a tile provider that
permits your usage and set its required attribution and zoom limit before
starting Flask:

```powershell
$env:MAP_TILE_URL = "https://your-provider.example/{z}/{x}/{y}.png"
$env:MAP_TILE_ATTRIBUTION = "Provider attribution required by its usage policy"
$env:MAP_TILE_MAX_ZOOM = "19"
```

The app does not switch providers automatically. Keep attribution visible and
follow the configured provider's usage, caching, and request policies.

## Test the features

1. **Dijkstra and severity:** On the home page, leave **Demo network ·
   simulated** selected. Choose a fire station node and a fire incident node,
   set severity to Low, Medium, High, or Critical, and submit. Confirm route
   alternatives, shortest travel time, approximate distance, and ETA.
   The demo designation list shows all six graph nodes: station H, road
   junctions A-D, and incident P. The registered station list currently has
   one configured sample; use station search to look up additional OSM results.
2. **Alternate routes / closures:** In **Road Network**, close a sample road
   or add delay minutes and apply the changes. Search again in demo mode to
   see Dijkstra choose another route when possible. Restore original road
   conditions afterward. These simulated closures do not affect OSRM.
3. **Mapped roads:** Choose **OpenStreetMap + OSRM · road estimate**, enter the
   incident location, and select a responding fire station. Submit to see the
   route map, distance, estimated duration, ETA, and available alternatives.
   Public geocoding and routing require internet access. There is no live
   traffic feed.
4. **Fire dispatch map and station lookup:** Visit `/dispatch`. The route map
   displays OpenStreetMap tiles and the selected station; after you provide an
   incident and calculate a response, it shows the OSRM route, endpoint markers,
   distance, estimated time, and available directions. Search a station name or
   area and select **Use this fire station** to use its coordinates. If no route
   has been calculated, the page explains that rather than drawing a sample
   route.
5. **Optional GPS sharing:** After planning a dispatch, open the private
   fire-unit link on the operator device and the dispatcher link on the
   authorized dispatcher device. The operator must grant browser location
   permission and press **Start Trip**. Test Stop Tracking and Complete Trip.
   GPS generally requires HTTPS except on localhost. The app reports browser
   GPS updates; it does not claim live traffic or automatic tracking.
6. **Automated tests:** Run:

   ```powershell
   .\.venv\Scripts\python.exe -m unittest discover -s tests -v
   ```

## Data sources and limitations

- Leaflet displays standard OpenStreetMap tiles with attribution. Follow the
  [tile usage policy](https://operations.osmfoundation.org/policies/tiles/);
  do not bulk-download or prefetch tiles.
- Address and fire-station lookup use public
  [Nominatim](https://operations.osmfoundation.org/policies/nominatim/).
- Mapped driving routes use the public [OSRM demo service](https://project-osrm.org/).
  Its route data does not include current traffic or live road closures.
- The local Kengeri fire-station coordinate is a sample. Public OSM station
  records can be incomplete and should be independently verified.
- Trip links are bearer links. Anyone holding a link has its role-specific
  access. Tokens are stored as hashes in SQLite; keep links private.
- GPS distance is the straight-line distance between accepted position
  updates, not road distance. Breadcrumb tracks are not retained. Last GPS
  coordinates are cleared when tracking stops or completes and are purged
  after 24 hours.

### Dashboard photo credits

- Fire engine: “AC-130 fire engine - 1” by Alexander Novikov,
  [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/),
  [Wikimedia Commons source](https://commons.wikimedia.org/wiki/File:AC-130_fire_engine_-_1.jpg).
- Fire station: “Braunton (Devon, UK), Fire Station -- 2013 -- 00156” by
  Dietmar Rabich, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/),
  [Wikimedia Commons source](https://commons.wikimedia.org/wiki/File:Braunton_(Devon,_UK),_Fire_Station_--_2013_--_00156.jpg).
- Fire rescue: “Fire rescue training exercise (8540120)” by Staff Sgt. Koby
  Saunders / U.S. Air Force, public domain,
  [Wikimedia Commons source](https://commons.wikimedia.org/wiki/File:Fire_rescue_training_exercise_(8540120).jpg).
  This is a training exercise, not a live incident photograph.

Legacy ambulance and hospital photos remain in `static/images` for
compatibility but are not displayed by FireResQ. Their attribution is retained
here: “Ambulance in India” by Oleg Yunakov, CC BY-SA 4.0
([Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Ambulance_in_India.jpg));
Apollo Hospitals Bengaluru photo by Keerthishivanand, CC BY-SA 4.0
([Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Apollo_Hospitals_Bengaluru.jpg)).

For public deployment, use HTTPS, a production host configured for
Flask-SocketIO, persistent storage, and operational monitoring. Do not expose
Flask's development server directly to the public internet.

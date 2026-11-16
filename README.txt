FIRERESQ - INTELLIGENT FIRE EMERGENCY ROUTE FINDER
VERSION 1.0.0

FireResQ adapts the existing Flask route planner for fire response. It plans
routes from a responding fire station to a fire incident, compares route
alternatives, saves route history in SQLite, and includes an optional
permission-based fire-unit location-sharing prototype.

EDUCATIONAL PROTOTYPE ONLY
FireResQ is not a certified emergency dispatch system. OSRM routes are
mapped-road estimates, not live traffic. The sample graph is simulated and
its distances are approximate display values. OpenStreetMap listings may be
incomplete or outdated. Verify locations independently; do not rely on this
application to handle a real emergency.

FEATURES
- Dijkstra's algorithm and Python heapq min-heap priority queue find routes
  on a six-node sample road network. Travel time is the optimization weight.
  Up to three distinct loopless routes are displayed with estimated time,
  ETA, and approximate sample-road distance.
- Demo-only road closure and delay simulation changes route selection in the
  sample graph. It does not change OSRM routes.
- OpenStreetMap / OSRM route planning geocodes an incident location, starts
  from a selected fire station, and displays mapped-route alternatives,
  distance, estimated travel time, ETA, and an interactive Leaflet map.
- Public OpenStreetMap fire station search is available on the /dispatch
  page. Listings do not indicate station availability.
- Route history and severity are stored in SQLite. Existing records are
  retained. Database startup adds fire-unit and severity columns when needed.
- Optional browser GPS sharing begins only after the fire-unit operator
  explicitly grants permission and starts tracking. Socket.IO updates have
  periodic polling fallback. The latest accepted position is retained, not a
  GPS breadcrumb track.

RUN ON WINDOWS (POWERSHELL)
Run these commands from the project directory:

    py -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    .\.venv\Scripts\python.exe app.py

Open http://127.0.0.1:5000. Keep the terminal open while using the app and
press Ctrl+C to stop the server. SQLite defaults to instance/routes.db.

CONFIGURATION (OPTIONAL)
Set these PowerShell environment variables before starting the app:

    $env:DATABASE_PATH = "C:\path\to\routes.db"
    $env:NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org"
    $env:OSRM_BASE_URL = "https://router.project-osrm.org"
    $env:PUBLIC_BASE_URL = "https://your-public-host"

PUBLIC_BASE_URL is only needed when generated private trip links must use a
public HTTPS origin. Defaults use the public Nominatim and OSRM demo services.

The home-page map defaults to the standard OpenStreetMap tile endpoint. If it
is unavailable on your network, configure a provider that permits your usage:

    $env:MAP_TILE_URL = "https://your-provider.example/{z}/{x}/{y}.png"
    $env:MAP_TILE_ATTRIBUTION = "Provider attribution required by its policy"
    $env:MAP_TILE_MAX_ZOOM = "19"

The app does not switch providers automatically. Keep attribution visible and
follow the configured provider's usage, caching, and request policies.

FEATURE TESTING
1. Dijkstra / severity: Keep "Demo network - simulated" selected, choose a
   fire-station node and an incident node, select Low, Medium, High, or
   Critical severity, and submit. Review routes, estimated distance,
   travel time, and ETA. The designation list shows all six demo nodes:
   station H, road junctions A-D, and incident P. One station is configured
   locally; use station search to look up additional OSM results.
2. Alternate routes / closures: In "Road Network", close a sample road or add
   delay minutes. Apply and search again in demo mode. Dijkstra will avoid a
   closed road where an alternate route exists. Restore original conditions
   afterward. This simulation does not affect OSRM.
3. Mapped route: Choose "OpenStreetMap + OSRM - road estimate", enter the
   incident address, select a fire station, and submit. The map and route
   cards show mapped route, distance, duration, ETA, and available
   alternatives. An internet connection is required; there is no live traffic.
4. Fire station lookup: Open /dispatch, search an OSM station name or area,
   select "Use this fire station", and enter fire-unit ID, incident, and
   severity to calculate a station-to-incident route.
5. Optional location sharing: Open the private fire-unit link on the operator
   device and the dispatcher link on the authorized dispatcher device. The
   operator grants location permission and presses "Start Trip". Verify Stop
   Tracking and Complete Trip. Browser GPS generally requires HTTPS except
   on localhost.
6. Run automated tests:

    .\.venv\Scripts\python.exe -m unittest discover -s tests -v

DATA SOURCES AND LIMITATIONS
- Leaflet uses standard OpenStreetMap tiles with attribution. Follow
  https://operations.osmfoundation.org/policies/tiles/ and do not bulk
  download or prefetch tiles.
- Address and fire station lookup use public Nominatim:
  https://operations.osmfoundation.org/policies/nominatim/
- Mapped routes use the public OSRM demo service: https://project-osrm.org/.
  It does not provide current traffic or live road closures.
- The local Kengeri fire station coordinate is a sample and must be verified.
- Trip links are private bearer links. Anyone holding a link has its
  role-specific access. SQLite stores token hashes; protect the links.
- GPS distance is straight-line between accepted updates, not road distance.
  Breadcrumb tracks are not retained. The latest coordinates are cleared
  when tracking stops or completes and purged after 24 hours.
- Browser location is not automatic or continuous unless the unit operator
  opts in. The application is not a certified dispatch workflow.

Dashboard photo credits:
- Fire engine: "AC-130 fire engine - 1" by Alexander Novikov, CC BY-SA 4.0:
  https://commons.wikimedia.org/wiki/File:AC-130_fire_engine_-_1.jpg
- Fire station: "Braunton (Devon, UK), Fire Station -- 2013 -- 00156" by
  Dietmar Rabich, CC BY-SA 4.0:
  https://commons.wikimedia.org/wiki/File:Braunton_(Devon,_UK),_Fire_Station_--_2013_--_00156.jpg
- Fire rescue: "Fire rescue training exercise (8540120)" by Staff Sgt. Koby
  Saunders / U.S. Air Force, public domain:
  https://commons.wikimedia.org/wiki/File:Fire_rescue_training_exercise_(8540120).jpg
  This is a training exercise, not a live incident photograph.
CC BY-SA 4.0 license: https://creativecommons.org/licenses/by-sa/4.0/

Legacy ambulance and hospital photos remain in static/images for compatibility
but are not displayed by FireResQ. Attribution is retained here:
"Ambulance in India" by Oleg Yunakov, CC BY-SA 4.0:
https://commons.wikimedia.org/wiki/File:Ambulance_in_India.jpg
Apollo Hospitals Bengaluru photo by Keerthishivanand, CC BY-SA 4.0:
https://commons.wikimedia.org/wiki/File:Apollo_Hospitals_Bengaluru.jpg

Public deployment requires HTTPS, a production host configured for
Flask-SocketIO, persistent storage, and operational monitoring. Do not expose
Flask's development server directly to the public internet.

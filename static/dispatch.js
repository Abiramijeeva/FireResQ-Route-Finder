(() => {
    const dispatchMapElement = document.getElementById("dispatch-route-map");
    const dispatchMapStatus = document.getElementById("dispatch-map-status");
    const mapDataElement = document.getElementById("dispatch-map-data");
    const tileConfigElement = document.getElementById("dispatch-map-tile-config");
    const stationInput = document.getElementById("fire_station");
    const stationLatitude = document.getElementById("fire_station_lat");
    const stationLongitude = document.getElementById("fire_station_lon");
    const mapData = mapDataElement ? JSON.parse(mapDataElement.textContent) : null;
    const mapTileConfig = tileConfigElement
        ? JSON.parse(tileConfigElement.textContent)
        : null;
    let dispatchStationMarker = null;

    if (dispatchMapElement && dispatchMapStatus) {
        if (typeof L === "undefined") {
            dispatchMapStatus.textContent =
                "The map library did not load. Check your connection or browser extensions; route directions remain below.";
        } else if (typeof window.addOpenStreetMapBaseLayer !== "function") {
            dispatchMapStatus.textContent =
                "The OpenStreetMap tile layer could not load. Refresh the page or check your connection.";
        } else {
            const isValidPoint = point =>
                Array.isArray(point) &&
                point.length === 2 &&
                Number.isFinite(point[0]) &&
                Number.isFinite(point[1]) &&
                point[0] >= -90 &&
                point[0] <= 90 &&
                point[1] >= -180 &&
                point[1] <= 180;
            const locationPoint = location => {
                const latitude = Number(location?.lat);
                const longitude = Number(location?.lon);
                const point = [latitude, longitude];
                return isValidPoint(point) ? point : null;
            };
            const formStationPoint = () => {
                const point = [
                    Number(stationLatitude?.value),
                    Number(stationLongitude?.value),
                ];
                return stationLatitude?.value &&
                    stationLongitude?.value &&
                    isValidPoint(point)
                    ? point
                    : null;
            };

            try {
                const stationPoint = formStationPoint() ||
                    (mapData.route ? locationPoint(mapData.station) : null);
                const initialPoint = stationPoint || locationPoint(mapData.station);
                const map = L.map(dispatchMapElement).setView(initialPoint || [0, 0], initialPoint ? 13 : 2);
                window.addOpenStreetMapBaseLayer(map, mapTileConfig);

                if (stationPoint) {
                    dispatchStationMarker = L.marker(stationPoint).addTo(map);
                    dispatchStationMarker.bindPopup(mapData.station.name);
                }

                const incidentPoint = mapData.route
                    ? locationPoint(mapData.incident)
                    : null;
                const geometry = mapData.route?.geometry;
                const routePoints = Array.isArray(geometry)
                    ? geometry.map(point => {
                        if (!Array.isArray(point) || point.length !== 2) {
                            return null;
                        }
                        const longitude = Number(point[0]);
                        const latitude = Number(point[1]);
                        const leafletPoint = [latitude, longitude];
                        return isValidPoint(leafletPoint) ? leafletPoint : null;
                    })
                    : [];
                const hasValidRoute = routePoints.length >= 2 &&
                    routePoints.every(point => point !== null) &&
                    stationPoint &&
                    incidentPoint;

                if (mapData.route && !hasValidRoute) {
                    dispatchMapStatus.textContent =
                        "Route geometry is unavailable or invalid. No route line is displayed; check the station and incident locations and calculate again.";
                } else if (hasValidRoute) {
                    const incidentMarker = L.marker(incidentPoint).addTo(map);
                    incidentMarker.bindPopup(mapData.incident.name);
                    const routeLine = L.polyline(routePoints, {
                        color: "#c44536",
                        weight: 6,
                        opacity: 0.85,
                    }).addTo(map);
                    map.fitBounds(routeLine.getBounds().extend(stationPoint).extend(incidentPoint), {
                        padding: [28, 28],
                        maxZoom: 16,
                    });
                    dispatchMapStatus.textContent =
                        "Showing the selected fire station, incident, and calculated OSRM road route.";
                } else if (stationPoint) {
                    dispatchMapStatus.textContent =
                        "Station location shown. No calculated route yet; choose an incident and calculate the route.";
                } else {
                    dispatchMapStatus.textContent =
                        "No station coordinates are selected. Choose a fire station and calculate a route to display its locations.";
                }
                window.requestAnimationFrame(() => map.invalidateSize());
            } catch (error) {
                dispatchMapStatus.textContent =
                    `The dispatch map could not be initialized: ${error.message}`;
            }
        }
    }

    const searchButton = document.getElementById("fire-station-search-button");
    if (searchButton) {
        const queryInput = document.getElementById("fire-station-query");
        const resultContainer = document.getElementById("fire-station-results");
        const searchStatus = document.getElementById("fire-station-search-status");
        const mapElement = document.getElementById("fire-station-search-map");
        const stationInput = document.getElementById("fire_station");
        const stationLatitude = document.getElementById("fire_station_lat");
        const stationLongitude = document.getElementById("fire_station_lon");
        let stationMap = null;
        let stationMarkers = null;
        let baseMapInitialized = false;

        searchButton.addEventListener("click", async () => {
            const query = queryInput.value.trim();
            if (query.length < 2 || query.length > 120) {
                searchStatus.hidden = false;
                searchStatus.textContent = "Enter at least two characters for the fire station search.";
                resultContainer.replaceChildren();
                return;
            }
            searchButton.disabled = true;
            searchStatus.hidden = false;
            searchStatus.textContent = "Searching OpenStreetMap fire station listings…";
            resultContainer.replaceChildren();
            try {
                const response = await fetch(
                    `/api/fire-stations/search?q=${encodeURIComponent(query)}`,
                    {headers: {Accept: "application/json"}}
                );
                const payload = await response.json();
                if (!response.ok) {
                    throw new Error(payload.error || "Fire station search failed.");
                }
                if (!payload.results.length) {
                    searchStatus.textContent = "No fire station listings found. Try another area or enter the station address manually.";
                    return;
                }
                searchStatus.textContent = `${payload.results.length} public OSM fire station listing(s). Verify details independently.`;
                if (typeof L === "undefined") {
                    searchStatus.textContent += " The map library could not load.";
                } else {
                    mapElement.hidden = false;
                }
                if (typeof L !== "undefined" && !stationMap) {
                    stationMap = L.map(mapElement).setView(
                        [payload.results[0].lat, payload.results[0].lon],
                        12
                    );
                    stationMarkers = L.layerGroup().addTo(stationMap);
                }
                if (stationMap) {
                    mapElement.hidden = false;
                    stationMarkers.clearLayers();
                }
                const bounds = [];
                payload.results.forEach(station => {
                    let marker = null;
                    if (stationMap) {
                        marker = L.marker([station.lat, station.lon]).addTo(stationMarkers);
                        const popup = document.createElement("div");
                        popup.textContent = `${station.name} — ${station.display_name}`;
                        marker.bindPopup(popup);
                        bounds.push([station.lat, station.lon]);
                    }
                    const card = document.createElement("article");
                    card.className = "fire-station-result";
                    const name = document.createElement("strong");
                    name.textContent = station.name;
                    const address = document.createElement("p");
                    address.textContent = station.display_name;
                    card.append(name, address);
                    const details = Object.entries(station.public_details || {});
                    if (details.length) {
                        const publicDetails = document.createElement("p");
                        publicDetails.textContent = details
                            .map(([key, value]) => `${key}: ${value}`)
                            .join(" · ");
                        card.append(publicDetails);
                    }
                    const actions = document.createElement("div");
                    actions.className = "fire-station-result-actions";
                    const selectButton = document.createElement("button");
                    selectButton.type = "button";
                    selectButton.className = "secondary-button";
                    selectButton.textContent = "Use this fire station";
                    selectButton.addEventListener("click", () => {
                        stationInput.value = station.display_name;
                        stationLatitude.value = station.lat;
                        stationLongitude.value = station.lon;
                        if (stationMap && marker) {
                            stationMap.setView([station.lat, station.lon], 15);
                            marker.openPopup();
                        }
                    });
                    actions.append(selectButton);
                    if (station.osm_url) {
                        const mapLink = document.createElement("a");
                        mapLink.href = station.osm_url;
                        mapLink.target = "_blank";
                        mapLink.rel = "noopener noreferrer";
                        mapLink.textContent = "View OpenStreetMap record";
                        actions.append(mapLink);
                    }
                    card.append(actions);
                    resultContainer.append(card);
                });
                if (bounds.length) {
                    stationMap.fitBounds(bounds, {padding: [20, 20], maxZoom: 14});
                    window.setTimeout(() => stationMap.invalidateSize(), 0);
                }
                if (stationMap && !baseMapInitialized) {
                    window.addOpenStreetMapBaseLayer(stationMap, mapTileConfig);
                    baseMapInitialized = true;
                }
            } catch (error) {
                searchStatus.textContent = error.message || "Fire station search is temporarily unavailable.";
            } finally {
                searchButton.disabled = false;
            }
        });
    }

    if (stationInput) {
        stationInput.addEventListener("input", () => {
            stationLatitude.value = "";
            stationLongitude.value = "";
            if (dispatchStationMarker) {
                dispatchStationMarker.remove();
                dispatchStationMarker = null;
                dispatchMapStatus.textContent =
                    "The station address changed. No route is displayed until the new station location is calculated.";
            }
        });
    }

    document.querySelectorAll(".copy-link").forEach(button => {
        button.addEventListener("click", async () => {
            const input = document.getElementById(button.dataset.copy);
            try {
                await navigator.clipboard.writeText(input.value);
                button.textContent = "Copied";
                window.setTimeout(() => {
                    button.textContent = "Copy link";
                }, 1500);
            } catch {
                input.focus();
                input.select();
                document.execCommand("copy");
                button.textContent = "Link selected";
            }
        });
    });
})();

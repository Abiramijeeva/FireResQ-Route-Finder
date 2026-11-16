(() => {
    window.addOpenStreetMapBaseLayer = (map, config) => {
        if (!map) {
            throw new Error("A Leaflet map is required to load map tiles.");
        }
        if (!config || typeof config !== "object") {
            throw new Error("OpenStreetMap tile configuration is missing.");
        }
        if (
            typeof config.url !== "string" ||
            !/^https:\/\//i.test(config.url) ||
            !["z", "x", "y"].every(coordinate =>
                config.url.includes(`{${coordinate}}`)
            )
        ) {
            throw new Error(
                "OpenStreetMap tile URL is missing or invalid. Check MAP_TILE_URL."
            );
        }
        if (
            typeof config.attribution !== "string" ||
            !config.attribution.trim() ||
            !Number.isInteger(config.maxZoom) ||
            config.maxZoom < 0 ||
            config.maxZoom > 24
        ) {
            throw new Error("OpenStreetMap tile attribution or zoom configuration is invalid.");
        }

        const tileLayer = L.tileLayer(config.url, {
            attribution: config.attribution,
            maxZoom: config.maxZoom,
        });

        let noticeControl;
        let noticeElement;
        let loadTimeout;
        let loadedTiles = 0;
        let failedTiles = 0;

        function showTileMessage(message) {
            if (!noticeControl) {
                noticeControl = L.control({position: "topright"});
                noticeControl.onAdd = () => {
                    noticeElement = L.DomUtil.create("div", "map-tile-notice");
                    noticeElement.setAttribute("role", "alert");
                    return noticeElement;
                };
                noticeControl.addTo(map);
            }
            noticeElement.textContent = message;
            noticeElement.hidden = !message;
        }

        function clearLoadTimeout() {
            if (loadTimeout) {
                window.clearTimeout(loadTimeout);
                loadTimeout = undefined;
            }
        }

        tileLayer.on("loading", () => {
            clearLoadTimeout();
            loadedTiles = 0;
            failedTiles = 0;
            loadTimeout = window.setTimeout(() => {
                if (loadedTiles === 0) {
                    showTileMessage(
                        "No map tiles loaded. Check your connection, browser extensions, and configured tile provider."
                    );
                }
            }, 15000);
        });
        tileLayer.on("tileerror", () => {
            failedTiles += 1;
        });
        tileLayer.on("tileload", () => {
            loadedTiles += 1;
        });
        tileLayer.on("load", () => {
            clearLoadTimeout();
            if (failedTiles > 0) {
                showTileMessage(
                    loadedTiles === 0
                        ? "Map tiles are unavailable. Check your connection, browser extensions, and configured tile provider."
                        : "Some map tiles failed to load. Check your connection or configured tile provider."
                );
            } else {
                showTileMessage("");
            }
        });
        tileLayer.addTo(map);
        return tileLayer;
    };
})();

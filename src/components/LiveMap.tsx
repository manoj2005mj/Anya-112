import { MapContainer, TileLayer, Marker, Popup, useMap, Polyline } from 'react-leaflet';
import { useEffect } from 'react';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

const DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

L.Marker.prototype.options.icon = DefaultIcon;

// Custom icon for emergency facility (red)
const FacilityIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [30, 45],
  iconAnchor: [15, 45],
  className: 'facility-marker',
});

interface MapProps {
  location: string | null;
  coordinates?: [number, number];
  facilityCoordinates?: [number, number];
  facilityName?: string;
  routeGeometry?: number[][];
}

function MapUpdater({ center, zoom }: { center: [number, number]; zoom?: number }) {
  const map = useMap();
  useEffect(() => {
    map.flyTo(center, zoom ?? 14);
  }, [center, map, zoom]);
  return null;
}

function MapBounds({ points }: { points: [number, number][] }) {
  const map = useMap();
  useEffect(() => {
    if (points.length > 0) {
      map.fitBounds(points, { padding: [50, 50] });
    }
  }, [points, map]);
  return null;
}

const DEFAULT_CENTER: [number, number] = [28.6139, 77.209];

export default function LiveMap({
  location,
  coordinates,
  facilityCoordinates,
  facilityName,
  routeGeometry
}: MapProps) {
  const center = coordinates ?? DEFAULT_CENTER;

  // Prepare bounds for fitting both markers
  const boundsPoints: [number, number][] = [];
  if (coordinates) boundsPoints.push(coordinates);
  if (facilityCoordinates) boundsPoints.push(facilityCoordinates);

  return (
    <div className="h-full w-full rounded-xl overflow-hidden border border-zinc-200 shadow-lg relative z-0">
      <MapContainer
        center={center}
        zoom={13}
        style={{ height: '100%', width: '100%' }}
        zoomControl={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
        />

        {/* User/Incident Location Marker */}
        {coordinates && (
          <Marker position={coordinates}>
            <Popup>
              <div className="text-black">
                <strong>Incident Location</strong><br />
                {location}
              </div>
            </Popup>
          </Marker>
        )}

        {/* Emergency Facility Marker */}
        {facilityCoordinates && (
          <Marker position={facilityCoordinates} icon={FacilityIcon}>
            <Popup>
              <div className="text-black">
                <strong>Emergency Facility</strong><br />
                {facilityName || 'Responding Facility'}
              </div>
            </Popup>
          </Marker>
        )}

        {/* Route Line */}
        {routeGeometry && routeGeometry.length > 0 && (
          <Polyline
            positions={routeGeometry as [number, number][]}
            color="#3b82f6"
            weight={5}
            opacity={0.7}
            dashArray="10, 10"
          />
        )}

        {/* Fit bounds to show both markers */}
        {boundsPoints.length > 1 && <MapBounds points={boundsPoints} />}

        {/* Single marker update */}
        {coordinates && !facilityCoordinates && <MapUpdater center={coordinates} />}
      </MapContainer>

      {/* Overlay for "Live" status */}
      <div className="absolute top-4 right-4 z-[1000] bg-red-500/90 text-white text-xs font-bold px-3 py-1 rounded-full animate-pulse shadow-lg backdrop-blur-sm">
        LIVE FEED
      </div>
    </div>
  );
}

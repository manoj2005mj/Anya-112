import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
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

interface MapProps {
  location: string | null;
  coordinates?: [number, number];
}

function MapUpdater({ center }: { center: [number, number] }) {
  const map = useMap();
  useEffect(() => {
    map.flyTo(center, 14);
  }, [center, map]);
  return null;
}

const DEFAULT_CENTER: [number, number] = [28.6139, 77.209];

export default function LiveMap({ location, coordinates }: MapProps) {
  const center = coordinates ?? DEFAULT_CENTER;

  return (
    <div className="h-full w-full rounded-xl overflow-hidden border border-white/10 shadow-lg relative z-0">
      <MapContainer
        center={center}
        zoom={13}
        style={{ height: '100%', width: '100%' }}
        zoomControl={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />
        {coordinates && (
          <>
            <Marker position={coordinates}>
              <Popup>
                <div className="text-black">
                  <strong>Incident Location</strong><br/>
                  {location}
                </div>
              </Popup>
            </Marker>
            <MapUpdater center={coordinates} />
          </>
        )}
      </MapContainer>

      {/* Overlay for "Live" status */}
      <div className="absolute top-4 right-4 z-[1000] bg-red-500/90 text-white text-xs font-bold px-3 py-1 rounded-full animate-pulse shadow-lg backdrop-blur-sm">
        LIVE FEED
      </div>
    </div>
  );
}

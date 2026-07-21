import { MapContainer, TileLayer, Marker, useMapEvents, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useEffect } from 'react';

// Use an inline divIcon so no external marker images are loaded (CSP-friendly).
const markerIcon = L.divIcon({
  className: 'lenstrace-marker',
  html: '<div style="width:16px;height:16px;border-radius:50%;background:#4d8dff;border:2px solid #fff;box-shadow:0 0 0 4px rgba(77,141,255,0.3)"></div>',
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

interface Props {
  latitude: number | null;
  longitude: number | null;
  onPick: (lat: number, lon: number) => void;
}

function ClickHandler({ onPick }: { onPick: (lat: number, lon: number) => void }) {
  useMapEvents({
    click(e) {
      onPick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

function Recenter({ lat, lon }: { lat: number | null; lon: number | null }) {
  const map = useMap();
  useEffect(() => {
    if (lat != null && lon != null) map.setView([lat, lon], Math.max(map.getZoom(), 12));
  }, [lat, lon, map]);
  return null;
}

export function MapPicker({ latitude, longitude, onPick }: Props) {
  const center: [number, number] = [latitude ?? 20, longitude ?? 0];
  return (
    <div className="map-shell">
      <MapContainer center={center} zoom={latitude != null ? 12 : 2} scrollWheelZoom>
        <TileLayer
          attribution="&copy; OpenStreetMap contributors"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <ClickHandler onPick={onPick} />
        <Recenter lat={latitude} lon={longitude} />
        {latitude != null && longitude != null && (
          <Marker
            position={[latitude, longitude]}
            icon={markerIcon}
            draggable
            eventHandlers={{
              dragend: (e) => {
                const { lat, lng } = e.target.getLatLng();
                onPick(lat, lng);
              },
            }}
          />
        )}
      </MapContainer>
    </div>
  );
}

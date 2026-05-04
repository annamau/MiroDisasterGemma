import { geoEquirectangular } from 'd3'

/**
 * Build a d3-geoEquirectangular projection that auto-fits a set of geographic
 * points into a given viewBox. Returns a (lat, lon) -> [x, y] function.
 *
 * @param {Array<{lat: number, lon: number}>} points - all points to fit
 * @param {number} viewBoxWidth  - SVG viewBox width (default 1200)
 * @param {number} viewBoxHeight - SVG viewBox height (default 800)
 * @returns {(lat: number, lon: number) => [number, number]} project function
 */
export function makeProjection(points, viewBoxWidth = 1200, viewBoxHeight = 800) {
  if (!points || points.length === 0) {
    // Degenerate case: no points — return a passthrough that maps to center
    return () => [viewBoxWidth / 2, viewBoxHeight / 2]
  }

  // Add a tiny 5% padding to the bounding box to avoid degenerate fitSize
  // when the bbox is very small (e.g. a 10km Pompeii scenario).
  const lats = points.map((p) => p.lat)
  const lons = points.map((p) => p.lon)
  const latMin = Math.min(...lats)
  const latMax = Math.max(...lats)
  const lonMin = Math.min(...lons)
  const lonMax = Math.max(...lons)

  const latPad = Math.max((latMax - latMin) * 0.05, 0.001)
  const lonPad = Math.max((lonMax - lonMin) * 0.05, 0.001)

  // Build a GeoJSON MultiPoint that includes the padded corners so fitSize
  // accounts for the full extent (d3 uses [lon, lat] order).
  const geojson = {
    type: 'MultiPoint',
    coordinates: [
      [lonMin - lonPad, latMin - latPad],
      [lonMax + lonPad, latMax + latPad],
      ...points.map((p) => [p.lon, p.lat]),
    ],
  }

  const proj = geoEquirectangular().fitSize([viewBoxWidth, viewBoxHeight], geojson)

  return (lat, lon) => {
    const result = proj([lon, lat]) // d3-geo uses [lon, lat]
    return result ?? [viewBoxWidth / 2, viewBoxHeight / 2]
  }
}

// SPDX-License-Identifier: Apache-2.0
import { geoEquirectangular } from 'd3'

/**
 * Build a d3-geoEquirectangular projection that auto-fits a set of geographic
 * points into a given viewBox. Returns a (lat, lon) -> [x, y] function.
 *
 * The bbox is computed ONLY from the points passed in. If a hazard epicenter
 * sits offshore (Valencia DANA, anything Mediterranean), don't include it
 * here — pass only the city assets, then project the hazard separately and
 * clamp via `clampToBox()`. Otherwise the bbox stretches and the cities
 * cluster in a corner.
 *
 * @param {Array<{lat: number, lon: number}>} points - city assets to fit
 * @param {number} viewBoxWidth  - SVG viewBox width (default 1200)
 * @param {number} viewBoxHeight - SVG viewBox height (default 800)
 * @param {object} opts
 * @param {number} [opts.padding=0.08] fractional bbox padding (was 0.05;
 *   bumped to 0.08 so districts don't kiss the viewport edge)
 * @returns {(lat: number, lon: number) => [number, number]} project function
 */
export function makeProjection(
  points,
  viewBoxWidth = 1200,
  viewBoxHeight = 800,
  { padding = 0.08 } = {},
) {
  if (!points || points.length === 0) {
    return () => [viewBoxWidth / 2, viewBoxHeight / 2]
  }

  const lats = points.map(p => p.lat)
  const lons = points.map(p => p.lon)
  const latMin = Math.min(...lats)
  const latMax = Math.max(...lats)
  const lonMin = Math.min(...lons)
  const lonMax = Math.max(...lons)

  const latPad = Math.max((latMax - latMin) * padding, 0.001)
  const lonPad = Math.max((lonMax - lonMin) * padding, 0.001)

  const geojson = {
    type: 'MultiPoint',
    coordinates: [
      [lonMin - lonPad, latMin - latPad],
      [lonMax + lonPad, latMax + latPad],
      ...points.map(p => [p.lon, p.lat]),
    ],
  }

  const proj = geoEquirectangular().fitSize(
    [viewBoxWidth, viewBoxHeight],
    geojson,
  )

  return (lat, lon) => {
    const result = proj([lon, lat])
    return result ?? [viewBoxWidth / 2, viewBoxHeight / 2]
  }
}

/**
 * Clamp a projected point into a viewport with margin. Returns
 * `{x, y, clamped, theta}` where:
 *   - clamped = false if the point was inside the box
 *   - clamped = true if it was outside (and x,y are now on the edge),
 *     theta = angle (radians, 0=east, π/2=south) from box center to the
 *     real off-screen position. UI uses theta to draw an arrow.
 *
 * @param {[number,number]} pt - projected (x,y) before clamp
 * @param {number} w - viewBox width
 * @param {number} h - viewBox height
 * @param {number} [margin=24] inset margin
 */
export function clampToBox(pt, w, h, margin = 24) {
  const [x, y] = pt
  const cx = w / 2
  const cy = h / 2
  const inside =
    x >= margin && x <= w - margin && y >= margin && y <= h - margin
  if (inside) return { x, y, clamped: false, theta: 0 }

  const theta = Math.atan2(y - cy, x - cx)
  const clampedX = Math.max(margin, Math.min(w - margin, x))
  const clampedY = Math.max(margin, Math.min(h - margin, y))
  return { x: clampedX, y: clampedY, clamped: true, theta }
}

/**
 * Compute the median nearest-neighbor distance among a list of points
 * in projected (pixel) space. Used to size district pucks adaptively
 * so they don't overlap when districts are clustered.
 *
 * Returns a generous radius: half the median NN distance, capped to
 * `[minR, maxR]`. For sparse scenarios this returns `maxR`; for dense
 * ones it shrinks gracefully.
 *
 * @param {Array<[number,number]>} points - projected pixel coords
 * @param {number} [minR=20]
 * @param {number} [maxR=64]
 */
export function medianNearestRadius(points, minR = 20, maxR = 64) {
  if (!points || points.length < 2) return maxR
  const dists = []
  for (let i = 0; i < points.length; i++) {
    let nearest = Infinity
    for (let j = 0; j < points.length; j++) {
      if (i === j) continue
      const dx = points[i][0] - points[j][0]
      const dy = points[i][1] - points[j][1]
      const d = Math.sqrt(dx * dx + dy * dy)
      if (d < nearest) nearest = d
    }
    if (Number.isFinite(nearest)) dists.push(nearest)
  }
  if (dists.length === 0) return maxR
  dists.sort((a, b) => a - b)
  const median = dists[Math.floor(dists.length / 2)]
  // Half of NN distance prevents adjacent pucks from overlapping; -2px gap.
  const r = median / 2 - 2
  return Math.max(minR, Math.min(maxR, r))
}

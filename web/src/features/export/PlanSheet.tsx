/**
 * Fiche imprimable d'un plan (X1) : carte du tracé, profil, tableau des tronçons.
 * « Imprimer » ouvre la boîte d'impression du navigateur, qui enregistre en PDF.
 */
import { Link, useParams } from "react-router";
import {
  formatDistance,
  formatDuration,
  planView,
  profilePath,
  scaleBarMeters,
} from "./format";
import { planGeojsonUrl, usePlan, usePlanGeojson } from "./queries";
import type { LonLat, Route } from "@/shared/api/client";
import { colors } from "@/shared/theme";
import { Button } from "@/shared/ui";

const MAP_W = 640;
const MAP_H = 420;
const PROFILE_W = 640;
const PROFILE_H = 180;

interface Stop {
  id: string;
  name: string;
  order: number;
  position: LonLat;
}

function stopsOf(features: { id?: unknown; geometry: unknown; properties?: Record<string, unknown> }[]): Stop[] {
  // Les cibles sont les points de l'export ; ``kind`` les distingue de l'habitat.
  return features
    .filter((f) => {
      const kind = f.properties?.kind;
      return kind === "target" || (kind === undefined && (f.geometry as { type?: string })?.type === "Point");
    })
    .map((f, i) => ({
      id: String(f.id),
      name: String(f.properties?.name ?? f.id),
      order: Number(f.properties?.order ?? i + 1),
      position: (f.geometry as { coordinates: LonLat }).coordinates,
    }));
}

function RouteMap({ route, stops, habitat }: { route: Route; stops: Stop[]; habitat: LonLat }) {
  const line = route.geometry.coordinates as LonLat[];
  const view = planView([...line, habitat, ...stops.map((s) => s.position)], MAP_W, MAP_H);
  const bar = scaleBarMeters(view.scale);
  const pts = line.map((p) => view.project(p).map((v) => v.toFixed(1)).join(",")).join(" ");
  const [hx, hy] = view.project(habitat);
  return (
    <svg
      role="img"
      aria-label="Carte du tracé"
      viewBox={`0 0 ${MAP_W} ${MAP_H}`}
      className="w-full max-w-3xl rounded border border-[var(--border)] bg-white"
    >
      <polyline points={pts} fill="none" stroke={colors.route[route.variant]} strokeWidth={3} />
      <rect x={hx - 7} y={hy - 7} width={14} height={14} fill="#333" />
      <text x={hx + 10} y={hy + 4} fontSize={12}>
        Habitat
      </text>
      {stops.map((s) => {
        const [x, y] = view.project(s.position);
        return (
          <g key={s.id}>
            <circle cx={x} cy={y} r={9} fill={colors.info} />
            <text x={x} y={y + 4} fontSize={11} fill="white" textAnchor="middle">
              {s.order}
            </text>
            <text x={x + 12} y={y + 4} fontSize={12}>
              {s.name}
            </text>
          </g>
        );
      })}
      <g transform={`translate(16, ${MAP_H - 18})`}>
        <line x1={0} x2={bar * view.scale} y1={0} y2={0} stroke="#000" strokeWidth={3} />
        <text x={0} y={-6} fontSize={11}>
          {formatDistance(bar)}
        </text>
      </g>
      <text x={MAP_W - 16} y={24} fontSize={14} textAnchor="end">
        N ↑
      </text>
    </svg>
  );
}

function Profile({ route }: { route: Route }) {
  const p = profilePath(route.profile, PROFILE_W, PROFILE_H);
  if (!p) return <p>Profil d'altitude indisponible (pas de modèle de terrain).</p>;
  return (
    <svg
      role="img"
      aria-label="Profil d'altitude"
      viewBox={`0 0 ${PROFILE_W} ${PROFILE_H}`}
      className="w-full max-w-3xl rounded border border-[var(--border)] bg-white"
    >
      <path d={p.d} fill="none" stroke="#333" strokeWidth={2} />
      <text x={4} y={16} fontSize={11}>
        {Math.round(p.maxElevation)} m
      </text>
      <text x={4} y={PROFILE_H - 30} fontSize={11}>
        {Math.round(p.minElevation)} m
      </text>
      <text x={PROFILE_W - 4} y={PROFILE_H - 8} fontSize={11} textAnchor="end">
        {formatDistance(p.distance)}
      </text>
    </svg>
  );
}

export function PlanSheet() {
  const { planId = "" } = useParams();
  const plan = usePlan(planId);
  const geo = usePlanGeojson(planId);
  if (plan.isError || geo.isError) return <p className="p-6">Plan {planId} indisponible.</p>;
  if (!plan.data || !geo.data) return <p className="p-6">Chargement du plan…</p>;
  const route = plan.data.routes.find((r) => r.id === plan.data.selected_route_id) ?? plan.data.routes[0];
  if (!route) return <p className="p-6">Ce plan n'a pas d'itinéraire.</p>;
  const stops = stopsOf(geo.data.features ?? []);
  const name = (id: string | null | undefined) =>
    id ? (stops.find((s) => s.id === id)?.name ?? id) : "Habitat";
  const reasons = new Map(route.explanation.map((e) => [e.segment_index, e.reasons]));
  const t = route.totals;
  const rc = route.return_check;
  return (
    <div className="min-h-full bg-white text-black">
    <article className="mx-auto flex max-w-4xl flex-col gap-4 p-6">
      <nav className="flex flex-wrap gap-2 print:hidden">
        <Link to="/" className="underline">
          ← Retour à la carte
        </Link>
        <Button variant="primary" onClick={() => window.print()}>
          🖶 Imprimer ou enregistrer en PDF
        </Button>
        <a className="underline" href={planGeojsonUrl(planId)} download={`marswalk-${planId}.geojson`}>
          ⤓ GeoJSON
        </a>
      </nav>
      <header>
        <h1 className="text-2xl font-bold">Plan de sortie {plan.data.name ?? plan.data.id}</h1>
        <p>
          Site {plan.data.site_id} · variante {route.variant} · {stops.length} cibles
          {plan.data.departure_utc ? ` · départ ${plan.data.departure_utc}` : ""}
        </p>
      </header>
      <section aria-label="Totaux">
        <dl className="grid grid-cols-2 gap-x-6 gap-y-1 sm:grid-cols-4">
          <dt>Distance</dt>
          <dd>{formatDistance(t.distance_m)}</dd>
          <dt>Durée totale</dt>
          <dd>{formatDuration(t.duration_s)}</dd>
          <dt>Marche</dt>
          <dd>{formatDuration(t.walk_time_s)}</dd>
          <dt>Travail aux cibles</dt>
          <dd>{formatDuration(t.work_time_s)}</dd>
          <dt>Dénivelé</dt>
          <dd>
            +{Math.round(t.ascent_m)} m / −{Math.round(t.descent_m)} m
          </dd>
          <dt>Pente maximale</dt>
          <dd>{t.max_slope_deg.toFixed(1)}°</dd>
          <dt>Dose prévue</dt>
          <dd>{t.consumption.dose_usv.toFixed(1)} µSv</dd>
          <dt>Réserve au retour</dt>
          <dd>
            {rc.reserve_at_return_pct.toFixed(0)} % ({rc.limiting_consumable}, {rc.status})
          </dd>
        </dl>
      </section>
      <RouteMap route={route} stops={stops} habitat={plan.data.start as LonLat} />
      <Profile route={route} />
      <table className="w-full border-collapse text-sm [&_td]:py-1 [&_td]:pr-3 [&_th]:pr-3">
        <caption className="mb-1 text-left font-bold">Tronçons</caption>
        <thead>
          <tr className="border-b border-black text-left">
            <th>#</th>
            <th>De</th>
            <th>À</th>
            <th>Distance</th>
            <th>Marche</th>
            <th>Travail</th>
            <th>D+</th>
            <th>Pente max</th>
            <th>O₂</th>
            <th>Pourquoi ce tracé</th>
          </tr>
        </thead>
        <tbody>
          {route.segments.map((s) => (
            <tr key={s.index} className="border-b border-gray-300 align-top">
              <td>{s.index + 1}</td>
              <td>{name(s.from_target_id)}</td>
              <td>{name(s.to_target_id)}</td>
              <td>{formatDistance(s.distance_m)}</td>
              <td>{formatDuration(s.duration_s)}</td>
              <td>{s.work_time_s ? formatDuration(s.work_time_s) : "—"}</td>
              <td>{Math.round(s.ascent_m)} m</td>
              <td>{s.max_slope_deg.toFixed(1)}°</td>
              <td>{s.consumption.oxygen_kg.toFixed(3)} kg</td>
              <td>{(reasons.get(s.index) ?? []).join(" ; ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {(route.warnings ?? []).length > 0 && (
        <section aria-label="Avertissements">
          <h2 className="font-bold">Avertissements</h2>
          <ul className="list-disc pl-5">
            {(route.warnings ?? []).map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </section>
      )}
      <footer className="text-xs">Coordonnées en degrés planétocentriques est, Mars 2000 (IAU_2015:49900).</footer>
    </article>
    </div>
  );
}

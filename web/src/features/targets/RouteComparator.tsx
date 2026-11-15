/**
 * Comparateur des trois variantes d'itinéraire.
 * Les variantes sont affichées à égalité ; aucune n'est sélectionnée automatiquement.
 * Le choix passe par PATCH /api/plans/{id}.
 */
import type { Plan, Route } from "@/shared/api/client";
import { useShared } from "@/shared/store";
import { Button } from "@/shared/ui/Button";
import { colors } from "@/shared/theme";
import { useSelectRoute } from "./useTargets";

const VARIANT_LABEL: Record<string, string> = {
  safest: "Plus sûre",
  fastest: "Plus rapide",
  science: "Science",
};

const VARIANT_ICON: Record<string, string> = {
  safest: "🛡",
  fastest: "⚡",
  science: "🔬",
};

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h > 0 ? `${h} h ${m} min` : `${m} min`;
}

function formatDistance(meters: number): string {
  return meters >= 1000
    ? `${(meters / 1000).toFixed(2)} km`
    : `${Math.round(meters)} m`;
}

interface ReturnBadgeProps {
  route: Route;
}

function ReturnBadge({ route }: ReturnBadgeProps) {
  const rc = route.return_check;
  const color =
    rc.status === "ok"
      ? "text-[var(--text-ok)]"
      : rc.status === "marginal"
        ? "text-[var(--text-caution)]"
        : "text-[var(--text-danger)]";
  const icon =
    rc.status === "ok" ? "✓" : rc.status === "marginal" ? "▲" : "⛔";
  return (
    <span className={`text-xs font-semibold ${color}`} aria-label={`Retour : ${rc.status}`}>
      {icon} Retour {rc.reserve_at_return_pct.toFixed(0)}%
    </span>
  );
}

interface SegmentExplanationProps {
  route: Route;
}

function SegmentExplanations({ route }: SegmentExplanationProps) {
  if (!route.explanation.length) return null;
  return (
    <details className="mt-1">
      <summary className="cursor-pointer text-xs text-[var(--text-muted)] hover:text-[var(--text)]">
        Explication par tronçon ({route.explanation.length})
      </summary>
      <ul className="mt-1 space-y-0.5 text-xs">
        {route.explanation.map((ex) => (
          <li key={ex.segment_index} className="flex gap-1">
            <span className="text-[var(--text-muted)]">T{ex.segment_index + 1}</span>
            <span>{ex.reasons.join(" · ")}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}

interface RouteCardProps {
  route: Route;
  plan: Plan;
  isActive: boolean;
  onSelect: () => void;
}

function RouteCard({ route, plan, isActive, onSelect }: RouteCardProps) {
  const selectRoute = useSelectRoute();
  const setActiveRoute = useShared((s) => s.setActiveRoute);

  async function handleSelect() {
    await selectRoute.mutateAsync({ planId: plan.id, routeId: route.id });
    setActiveRoute(route.id);
    onSelect();
  }

  const colorKey = route.variant as keyof typeof colors.route;
  const routeColor = colors.route[colorKey] ?? colors.info;

  return (
    <div
      className={`rounded-lg border-2 p-3 transition-all ${
        isActive
          ? "border-[var(--color-info)] bg-[var(--surface-2)]"
          : "border-[var(--border)] bg-[var(--surface)]"
      }`}
      role="article"
      aria-label={`Variante ${VARIANT_LABEL[route.variant] ?? route.variant}`}
    >
      {/* En-tête */}
      <div className="mb-2 flex items-center gap-2">
        <span
          className="h-2 w-2 rounded-full flex-shrink-0"
          style={{ backgroundColor: routeColor }}
          aria-hidden="true"
        />
        <span className="font-semibold">
          {VARIANT_ICON[route.variant]} {VARIANT_LABEL[route.variant] ?? route.variant}
        </span>
        {isActive && (
          <span className="ml-auto rounded bg-[var(--color-info)] px-1 py-0.5 text-[10px] text-white">
            Choisie
          </span>
        )}
      </div>

      {/* Métriques */}
      <dl className="mb-2 grid grid-cols-2 gap-x-3 gap-y-0.5 text-xs">
        <dt className="text-[var(--text-muted)]">Distance</dt>
        <dd>{formatDistance(route.totals.distance_m)}</dd>
        <dt className="text-[var(--text-muted)]">Durée totale</dt>
        <dd>{formatDuration(route.totals.duration_s)}</dd>
        <dt className="text-[var(--text-muted)]">Dose rayonnement</dt>
        <dd>{route.totals.consumption.dose_usv.toFixed(0)} µSv</dd>
        <dt className="text-[var(--text-muted)]">Oxygène</dt>
        <dd>{route.totals.consumption.oxygen_kg.toFixed(2)} kg</dd>
        <dt className="text-[var(--text-muted)]">Cibles</dt>
        <dd>{route.segments.filter((s) => s.to_target_id).length}</dd>
      </dl>

      <ReturnBadge route={route} />

      {/* Warnings */}
      {route.warnings && route.warnings.length > 0 && (
        <ul className="mt-1 space-y-0.5">
          {route.warnings.map((w, i) => (
            <li key={i} className="flex items-start gap-1 text-xs text-[var(--text-caution)]">
              <span aria-hidden="true">▲</span>
              <span>{w}</span>
            </li>
          ))}
        </ul>
      )}

      <SegmentExplanations route={route} />

      {/* Point de non-retour */}
      {route.return_check.point_of_no_return && (
        <p className="mt-1 text-xs text-[var(--text-muted)]">
          Point de non-retour :{" "}
          {route.return_check.point_of_no_return_time_s !== null
            ? formatDuration(route.return_check.point_of_no_return_time_s ?? 0)
            : "—"}{" "}
          depuis le départ
        </p>
      )}

      {/* Si le retour n'est pas garanti */}
      {route.return_check.status !== "ok" &&
        route.return_check.targets_to_cut &&
        route.return_check.targets_to_cut.length > 0 && (
          <p className="mt-1 text-xs font-semibold text-[var(--text-danger)]">
            ⛔ Pour tenir la réserve, couper :{" "}
            {route.return_check.targets_to_cut.join(", ")}
          </p>
        )}

      {!isActive && (
        <Button
          variant="primary"
          className="mt-2 w-full text-xs"
          onClick={() => void handleSelect()}
          disabled={selectRoute.isPending}
          aria-label={`Choisir la variante ${VARIANT_LABEL[route.variant] ?? route.variant}`}
        >
          Choisir cette variante
        </Button>
      )}
    </div>
  );
}

interface Props {
  plan: Plan;
}

export function RouteComparator({ plan }: Props) {
  const activeRouteId = useShared((s) => s.activeRouteId);
  const setActiveRoute = useShared((s) => s.setActiveRoute);

  if (!plan.routes.length) {
    return (
      <p className="text-xs text-[var(--text-muted)]">Aucune variante calculée.</p>
    );
  }

  return (
    <div className="space-y-2" aria-label="Comparateur de variantes">
      <p className="text-xs text-[var(--text-muted)]">
        Comparez les variantes et choisissez celle qui convient. Aucune n'est
        imposée.
      </p>
      {plan.routes.map((route) => (
        <RouteCard
          key={route.id}
          route={route}
          plan={plan}
          isActive={activeRouteId === route.id}
          onSelect={() => setActiveRoute(route.id)}
        />
      ))}
    </div>
  );
}

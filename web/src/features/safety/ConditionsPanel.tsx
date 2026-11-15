/**
 * Panneau « Météo et météo spatiale » (EF-11) : conditions du moment, prévisions des
 * prochaines heures, état du Soleil, et rejeu d'un scénario pour la démonstration.
 */
import { useState } from "react";
import type { Conditions } from "@/shared/api/client";
import { Button, Panel } from "@/shared/ui";
import { useConditions, useForecast, useScenarioControl, useScenarios, useSettings } from "./queries";
import { doseRateLevel, dustLevel, formatNumber, formatUtc, type GaugeLevel } from "./thresholds";
import { LevelTag, levelMeta } from "./ui";

type SpaceWeatherLevel = NonNullable<Conditions["space_weather"]>["level"];

/** État du Soleil : niveau d'alerte, icône et texte. */
export const spaceWeather: Record<NonNullable<SpaceWeatherLevel>, { level: GaugeLevel; label: string }> = {
  quiet: { level: "ok", label: "Quiet" },
  watch: { level: "info", label: "Watch" },
  warning: { level: "caution", label: "Warning" },
  storm: { level: "danger", label: "Particle storm" },
};

const MODE_LABEL: Record<NonNullable<Conditions["mode"]>, string> = {
  historical: "Historical (MEDA, RAD)",
  scenario: "Replayed scenario",
  live: "Live (DONKI)",
  constant: "Constant values",
};

function Row({ label, value, level }: { label: string; value: string; level?: GaugeLevel }) {
  return (
    <tr data-row={label}>
      <th scope="row" className="py-0.5 pr-2 text-left font-normal">
        {label}
      </th>
      <td className="py-0.5 text-right tabular-nums font-semibold">{value}</td>
      <td className="py-0.5 pl-2 text-right">{level && <LevelTag level={level} />}</td>
    </tr>
  );
}

function ScenarioControl() {
  const scenarios = useScenarios();
  const control = useScenarioControl();
  const [id, setId] = useState("");
  const selected = id || scenarios.data?.[0]?.id || "";
  const running = control.data?.running && control.data.scenario_id === selected;
  if (!scenarios.data?.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-2 border-t border-[var(--border)] pt-2 text-sm">
      <label className="flex items-center gap-2">
        Replay
        <select
          className="rounded border border-[var(--border)] bg-[var(--surface-2)] px-1"
          value={selected}
          onChange={(e) => setId(e.target.value)}
        >
          {scenarios.data.map((s) => (
            <option key={s.id} value={s.id}>
              {s.title}
            </option>
          ))}
        </select>
      </label>
      <Button
        disabled={!selected || control.isPending}
        onClick={() => control.mutate({ scenarioId: selected, run: !running, speed: 10 })}
      >
        {running ? "■ Stop" : "▶ Play × 10"}
      </Button>
      {control.isError && <span>▲ {control.error.message}</span>}
    </div>
  );
}

export function ConditionsPanel() {
  const current = useConditions();
  const forecast = useForecast();
  const settings = useSettings();
  const maxTau = { max_dust_tau: settings.data?.max_dust_tau ?? 2 };
  const c = current.data;
  const sw = spaceWeather[c?.space_weather?.level ?? "quiet"];

  return (
    <Panel title="Weather & Space Weather">
      {!c ? (
        <p className="text-sm">{current.isError ? "○ Conditions unavailable" : "Loading…"}</p>
      ) : (
        <div className="flex flex-col gap-2">
          <div
            data-space-weather={c.space_weather?.level ?? "quiet"}
            className="flex items-center justify-between rounded-md border-l-4 bg-[var(--surface-2)] px-2 py-1"
            style={{ borderColor: levelMeta[sw.level].color }}
          >
            <span>
              <span className="text-xs text-[var(--text-muted)]">Sun</span>
              <br />
              <strong>{sw.label}</strong>
              {c.space_weather?.event && <span className="ml-2 text-sm">{c.space_weather.event}</span>}
            </span>
            <LevelTag level={sw.level} />
          </div>
          <table className="w-full text-sm">
            <tbody>
              <Row
                label="Dose rate"
                value={`${formatNumber(c.dose_rate_usv_h, 1)} µSv/h`}
                level={doseRateLevel(c.dose_rate_usv_h)}
              />
              <Row label="Opacity (τ)" value={formatNumber(c.dust_tau, 2)} level={dustLevel(c.dust_tau, maxTau)} />
              <Row label="Temperature" value={`${formatNumber(c.temperature_c)} °C`} />
              <Row label="Pressure" value={`${formatNumber(c.pressure_pa)} Pa`} />
              <Row label="Wind" value={`${formatNumber(c.wind_mps, 1)} m/s`} />
              <Row label="UV index" value={formatNumber(c.uv_index, 1)} />
            </tbody>
          </table>
          <p className="text-xs text-[var(--text-muted)]">
            {MODE_LABEL[c.mode ?? "constant"]}
            {c.source ? ` · ${c.source}` : ""}
            {c.sol != null ? ` · sol ${c.sol}, ${c.lmst} LMST` : ""} · {formatUtc(c.utc)}
            {c.cached_at && (
              <>
                <br />▲ Cached value from {new Date(c.cached_at).toLocaleString("en-US", { timeZone: "UTC" })} UTC
              </>
            )}
          </p>
        </div>
      )}
      {forecast.data && forecast.data.items.length > 0 && (
        <details className="mt-2 text-sm">
          <summary className="cursor-pointer">Forecast ({forecast.data.items.length} h)</summary>
          <table className="mt-1 w-full tabular-nums" aria-label="Forecast">
            <thead className="text-xs text-[var(--text-muted)]">
              <tr>
                <th className="text-left font-normal">Time</th>
                <th className="text-right font-normal">µSv/h</th>
                <th className="text-right font-normal">τ</th>
                <th className="text-right font-normal">°C</th>
                <th className="text-right font-normal">Sun</th>
              </tr>
            </thead>
            <tbody>
              {forecast.data.items.map((f) => {
                const rate = doseRateLevel(f.dose_rate_usv_h);
                const dust = dustLevel(f.dust_tau, maxTau);
                return (
                  <tr key={f.utc}>
                    <td>{f.lmst ? `${f.lmst.slice(0, 5)} LMST` : formatUtc(f.utc).slice(0, 5) + " UTC"}</td>
                    <td className="text-right">
                      {rate !== "ok" && <span aria-label={levelMeta[rate].label}>{levelMeta[rate].icon} </span>}
                      {formatNumber(f.dose_rate_usv_h, 0)}
                    </td>
                    <td className="text-right">
                      {dust !== "ok" && <span aria-label={levelMeta[dust].label}>{levelMeta[dust].icon} </span>}
                      {formatNumber(f.dust_tau, 1)}
                    </td>
                    <td className="text-right">{formatNumber(f.temperature_c)}</td>
                    <td className="text-right">{spaceWeather[f.space_weather?.level ?? "quiet"].label}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </details>
      )}
      <ScenarioControl />
    </Panel>
  );
}

/**
 * Réglage des seuils de sécurité (EF-08) : pente, réserve, poussière, dose, radio, lumière.
 * Enregistrer relit les zones dangereuses et les plans, qui dépendent de ces seuils.
 */
import { useEffect, useState, type FormEvent } from "react";
import type { SafetySettings } from "@/shared/api/client";
import { Button, Panel } from "@/shared/ui";
import { useSaveSettings, useSettings } from "./queries";
import { validateSettings } from "./thresholds";

type NumericKey =
  | "max_slope_deg"
  | "penalty_slope_deg"
  | "min_reserve_pct"
  | "max_dust_tau"
  | "max_dose_usv"
  | "min_illumination";

const FIELDS: { key: NumericKey; label: string; unit: string; step: number }[] = [
  { key: "max_slope_deg", label: "Forbidden slope beyond", unit: "°", step: 1 },
  { key: "penalty_slope_deg", label: "Penalized slope beyond", unit: "°", step: 1 },
  { key: "min_reserve_pct", label: "Minimum reserve on return", unit: "%", step: 1 },
  { key: "max_dust_tau", label: "Maximum opacity (τ)", unit: "", step: 0.1 },
  { key: "max_dose_usv", label: "Maximum EVA dose", unit: "µSv", step: 10 },
  { key: "min_illumination", label: "Minimum illumination", unit: "0–1", step: 0.05 },
];

export function ThresholdsPanel() {
  const settings = useSettings();
  const save = useSaveSettings();
  const [draft, setDraft] = useState<SafetySettings | null>(null);

  useEffect(() => {
    if (settings.data) setDraft(settings.data);
  }, [settings.data]);

  if (!draft) return null;
  const errors = validateSettings(draft);
  const invalid = Object.keys(errors).length > 0;
  const dirty = JSON.stringify(draft) !== JSON.stringify(settings.data);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!invalid) save.mutate(draft);
  };

  return (
    <Panel title="Safety Thresholds">
      <details>
        <summary className="cursor-pointer text-sm">Adjust thresholds (preset {draft.preset})</summary>
        <form className="mt-2 flex flex-col gap-2 text-sm" onSubmit={onSubmit} noValidate>
          {FIELDS.map(({ key, label, unit, step }) => (
            <label key={key} className="flex flex-col gap-0.5">
              <span className="flex items-center justify-between gap-2">
                {label}
                <span className="flex items-center gap-1">
                  <input
                    type="number"
                    name={key}
                    step={step}
                    value={Number.isNaN(draft[key]) ? "" : draft[key]}
                    aria-invalid={errors[key] ? true : undefined}
                    onChange={(e) => setDraft({ ...draft, [key]: e.target.valueAsNumber })}
                    className="w-20 rounded border border-[var(--border)] bg-[var(--surface-2)] px-1 text-right"
                  />
                  <span className="w-8 text-xs">{unit}</span>
                </span>
              </span>
              {errors[key] && <span className="text-xs">▲ {errors[key]}</span>}
            </label>
          ))}
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              name="require_radio"
              checked={draft.require_radio}
              onChange={(e) => setDraft({ ...draft, require_radio: e.target.checked })}
            />
            Radio coverage required
          </label>
          <div className="flex items-center gap-2">
            <Button type="submit" variant="primary" disabled={invalid || !dirty || save.isPending}>
              {save.isPending ? "Saving…" : "Save"}
            </Button>
            {dirty && (
              <Button onClick={() => settings.data && setDraft(settings.data)} disabled={save.isPending}>
                Cancel
              </Button>
            )}
            <span role="status">
              {save.isError ? `▲ ${save.error.message}` : save.isSuccess && !dirty ? "✓ Saved" : ""}
            </span>
          </div>
        </form>
      </details>
    </Panel>
  );
}

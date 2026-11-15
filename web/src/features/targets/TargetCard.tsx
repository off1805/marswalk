/**
 * Fiche d'une cible : objectif, mesure, temps de travail.
 * Permet aussi de supprimer la cible.
 */
import { useState } from "react";
import { useShared } from "@/shared/store";
import { Button } from "@/shared/ui/Button";
import type { Target } from "@/shared/api/client";
import { useUpdateTarget, useDeleteTarget } from "./useTargets";

interface Props {
  target: Target;
  onClose: () => void;
}

export function TargetCard({ target, onClose }: Props) {
  const selectTarget = useShared((s) => s.selectTarget);
  const updateTarget = useUpdateTarget();
  const deleteTarget = useDeleteTarget();

  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(target.name);
  const [objective, setObjective] = useState(target.objective ?? "");
  const [measurement, setMeasurement] = useState(target.measurement ?? "");
  const [workMin, setWorkMin] = useState(
    Math.round((target.work_time_s ?? 0) / 60),
  );

  const workH = Math.floor(workMin / 60);
  const workM = workMin % 60;

  async function save() {
    await updateTarget.mutateAsync({
      id: target.id,
      name,
      objective: objective || undefined,
      measurement: measurement || undefined,
      work_time_s: workMin * 60,
    });
    setEditing(false);
  }

  async function remove() {
    await deleteTarget.mutateAsync(target.id);
    selectTarget(null);
    onClose();
  }

  return (
    <div
      className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 text-sm"
      role="region"
      aria-label={`Target card: ${target.name}`}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        {editing ? (
          <input
            className="flex-1 rounded border border-[var(--border)] bg-[var(--surface-2)] px-2 py-1 text-sm"
            value={name}
            onChange={(e) => setName(e.target.value)}
            aria-label="Target name"
          />
        ) : (
          <strong className="flex-1 truncate">{target.name}</strong>
        )}
        <div className="flex gap-1">
          {editing ? (
            <>
              <Button
                variant="primary"
                onClick={() => void save()}
                disabled={updateTarget.isPending}
                aria-label="Save"
              >
                ✓
              </Button>
              <Button onClick={() => setEditing(false)} aria-label="Cancel">
                ✕
              </Button>
            </>
          ) : (
            <>
              <Button onClick={() => setEditing(true)} aria-label="Edit target">
                ✎
              </Button>
              <Button
                variant="danger"
                onClick={() => void remove()}
                disabled={deleteTarget.isPending}
                aria-label="Delete target"
              >
                🗑
              </Button>
            </>
          )}
          <Button onClick={onClose} aria-label="Close card">
            ×
          </Button>
        </div>
      </div>

      {/* Champs de la fiche */}
      <dl className="space-y-1.5 text-xs">
        <div>
          <dt className="font-semibold text-[var(--text-muted)]">Position</dt>
          <dd>
            {target.position[0].toFixed(5)}° E,{" "}
            {target.position[1].toFixed(5)}° N
          </dd>
        </div>

        {editing ? (
          <>
            <div>
              <label className="font-semibold text-[var(--text-muted)]">
                Scientific objective
              </label>
              <textarea
                className="mt-0.5 w-full rounded border border-[var(--border)] bg-[var(--surface-2)] px-2 py-1 text-xs"
                rows={2}
                value={objective}
                onChange={(e) => setObjective(e.target.value)}
                aria-label="Scientific objective"
              />
            </div>
            <div>
              <label className="font-semibold text-[var(--text-muted)]">
                Measurement
              </label>
              <input
                className="mt-0.5 w-full rounded border border-[var(--border)] bg-[var(--surface-2)] px-2 py-1 text-xs"
                value={measurement}
                onChange={(e) => setMeasurement(e.target.value)}
                aria-label="Measurement"
              />
            </div>
            <div>
              <label className="font-semibold text-[var(--text-muted)]">
                Work time (min)
              </label>
              <input
                type="number"
                min={0}
                step={5}
                className="mt-0.5 w-full rounded border border-[var(--border)] bg-[var(--surface-2)] px-2 py-1 text-xs"
                value={workMin}
                onChange={(e) => setWorkMin(Number(e.target.value))}
                aria-label="Work time in minutes"
              />
            </div>
          </>
        ) : (
          <>
            {objective && (
              <div>
                <dt className="font-semibold text-[var(--text-muted)]">
                  Objective
                </dt>
                <dd>{objective}</dd>
              </div>
            )}
            {measurement && (
              <div>
                <dt className="font-semibold text-[var(--text-muted)]">
                  Measurement
                </dt>
                <dd>{measurement}</dd>
              </div>
            )}
            <div>
              <dt className="font-semibold text-[var(--text-muted)]">
                Work time
              </dt>
              <dd>
                {workH > 0 ? `${workH} h ` : ""}
                {workM} min
              </dd>
            </div>
          </>
        )}
      </dl>
    </div>
  );
}

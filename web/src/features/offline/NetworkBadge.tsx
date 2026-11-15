/**
 * Badge indiquant l'état de la connexion réseau.
 *
 * Principe S : afficher l'état réseau est sa seule responsabilité.
 * Principe I : reçoit `status` en prop — ne lit pas le réseau lui-même.
 *
 * La couleur n'est jamais le seul indice (ENF-06) : icône + texte + couleur.
 */
import type { NetworkStatus } from "./types";

interface Props {
  status: NetworkStatus;
  /** Nombre d'opérations en attente de rejeu. */
  pendingCount: number;
}

export function NetworkBadge({ status, pendingCount }: Props) {
  const online = status === "online";

  return (
    <div
      className={`flex items-center gap-1.5 rounded-full border px-2 py-1 text-xs font-semibold ${
        online
          ? "border-[var(--color-ok)] text-[var(--text-ok)]"
          : "border-[var(--color-caution)] text-[var(--text-caution)]"
      }`}
      role="status"
      aria-live="polite"
      aria-label={online ? "En ligne" : "Hors ligne"}
      data-testid="network-badge"
    >
      {/* Icône (ENF-06 : pas de couleur seule) */}
      <span aria-hidden="true">{online ? "●" : "○"}</span>
      <span>{online ? "En ligne" : "Hors ligne"}</span>

      {/* Badge de file d'attente */}
      {!online && pendingCount > 0 && (
        <span
          className="ml-0.5 rounded-full bg-[var(--color-caution)] px-1 text-[10px] text-black"
          aria-label={`${pendingCount} opération${pendingCount > 1 ? "s" : ""} en attente`}
        >
          {pendingCount}
        </span>
      )}
    </div>
  );
}

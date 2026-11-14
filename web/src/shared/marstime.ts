/**
 * Temps martien (C1). BOUCHON de T00 : sol = jours terrestres écoulés.
 * Doit donner les mêmes résultats que marswalk_core.marstime.mars_time.
 */
export interface MarsTime {
  utc: string;
  msd: number;
  sol: number;
  lmst: string;
  lmst_hours: number;
}

const J2000_UNIX_DAYS = 10957.5;
const SOL_RATIO = 1.0274912517;

function hms(hours: number): string {
  const total = Math.round((((hours % 24) + 24) % 24) * 3600) % 86400;
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(Math.floor(total / 3600))}:${p(Math.floor((total % 3600) / 60))}:${p(total % 60)}`;
}

export function marsTime(utc: Date, lonEast: number, epochUtc: Date): MarsTime {
  const daysUnix = utc.getTime() / 86_400_000;
  const msd = (daysUnix - J2000_UNIX_DAYS) / SOL_RATIO + 44796.0 - 0.00096;
  const mtc = (((24 * msd) % 24) + 24) % 24;
  const lmstHours = (((mtc + lonEast / 15) % 24) + 24) % 24;
  const sol = Math.floor((utc.getTime() - epochUtc.getTime()) / 86_400_000) + 1;
  return { utc: utc.toISOString(), msd, sol, lmst: hms(lmstHours), lmst_hours: lmstHours };
}

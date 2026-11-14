/**
 * Temps martien — algorithme Mars24 complet (C1).
 *
 * Implémentation exacte de l'algorithme Mars24 de la NASA GISS, miroir de
 * ``marswalk_core.marstime`` (Python). Les deux implémentations produisent
 * les mêmes résultats sur les vecteurs de test partagés.
 *
 * Références :
 * - Allison, M. et McEwen, M. (2000). Planet. Space Sci. 48(2–3), 215–235.
 * - NASA GISS Mars24 Algorithm : https://www.giss.nasa.gov/tools/mars24/help/algorithm.html
 *
 * Convention longitude : on reçoit une longitude *Est* (convention R2 du projet) ;
 * la formule NASA GISS utilise des degrés Ouest → lon_west = −lon_east.
 *
 * L'interface publique est gelée : marsTime(utc, lonEast, epochUtc) → MarsTime.
 */

export interface MarsTime {
  utc: string;
  msd: number;
  sol: number;
  lmst: string;
  lmst_hours: number;
  ltst: string;
  ls_deg: number;
}

// ---------------------------------------------------------------------------
// Constantes
// ---------------------------------------------------------------------------

const JD_UNIX_EPOCH = 2_440_587.5;
const JD_J2000 = 2_451_545.0;
const SOL_DAYS = 1.0274912517;
const MST_REF_JD = 2_451_549.5;
const MST_EPOCH = 44796.0;
const MST_CORR = 0.0009626;

const M0 = 19.3871;
const M_RATE = 0.52402073;
const AFMS0 = 270.3871;
const AFMS_RATE = 0.524038496;
const NU_M_DRIFT = 3.0e-7;
const TT_MINUS_TAI = 32.184;

/** Table TAI − UTC (seconds). Format : [Unix timestamp de début, TAI-UTC]. */
const TAI_MINUS_UTC_TABLE: [number, number][] = [
  [0, 10],
  [63_072_000, 10],  // 1972-01-01
  [78_796_800, 11],  // 1972-07-01
  [94_694_400, 12],  // 1973-01-01
  [126_230_400, 13], // 1974-01-01
  [157_766_400, 14], // 1975-01-01
  [189_302_400, 15], // 1976-01-01
  [220_924_800, 16], // 1977-01-01
  [252_460_800, 17], // 1978-01-01
  [283_996_800, 18], // 1979-01-01
  [315_532_800, 19], // 1980-01-01
  [362_793_600, 20], // 1981-07-01
  [394_329_600, 21], // 1982-07-01
  [425_865_600, 22], // 1983-07-01
  [489_024_000, 23], // 1985-07-01
  [567_993_600, 24], // 1988-01-01
  [631_152_000, 25], // 1990-01-01
  [662_688_000, 26], // 1991-01-01
  [709_948_800, 27], // 1992-07-01
  [741_484_800, 28], // 1993-07-01
  [773_020_800, 29], // 1994-07-01
  [820_454_400, 30], // 1996-01-01
  [867_715_200, 31], // 1997-07-01
  [915_148_800, 32], // 1999-01-01
  [1_136_073_600, 33], // 2006-01-01
  [1_230_768_000, 34], // 2009-01-01
  [1_341_100_800, 35], // 2012-07-01
  [1_435_708_800, 36], // 2015-07-01
  [1_483_228_800, 37], // 2017-01-01 (dernier leap second, IERS Bulletin C 67)
];

/** Coefficients PBS (B-3) : [A_i, τ_i, φ_i] */
const PBS_TERMS: [number, number, number][] = [
  [0.0071, 2.2353, 49.409],
  [0.0057, 2.7543, 168.173],
  [0.0039, 1.1177, 191.837],
  [0.0037, 15.7866, 21.736],
  [0.0021, 2.1354, 15.704],
  [0.0020, 2.4694, 95.528],
  [0.0018, 32.8493, 49.095],
];

const DEG2RAD = Math.PI / 180;

// ---------------------------------------------------------------------------
// Fonctions auxiliaires privées (exportées pour les tests)
// ---------------------------------------------------------------------------

export function ttMinusUtc(unixSec: number): number {
  let taiUtc = 10;
  for (const [ts, val] of TAI_MINUS_UTC_TABLE) {
    if (unixSec >= ts) taiUtc = val;
    else break;
  }
  return taiUtc + TT_MINUS_TAI;
}

export function jdUt(utc: Date): number {
  return JD_UNIX_EPOCH + utc.getTime() / 86_400_000;
}

export function deltaJ2000Tt(utc: Date): number {
  const jdUT = jdUt(utc);
  const jdTT = jdUT + ttMinusUtc(utc.getTime() / 1000) / 86400;
  return jdTT - JD_J2000;
}

export function marsMeanAnomaly(dt: number): number {
  return ((M0 + M_RATE * dt) % 360 + 360) % 360;
}

export function afms(dt: number): number {
  return ((AFMS0 + AFMS_RATE * dt) % 360 + 360) % 360;
}

export function pbs(dt: number): number {
  const k = 0.985626 * dt;
  return PBS_TERMS.reduce(
    (sum, [a, tau, phi]) => sum + a * Math.cos(DEG2RAD * (k / tau + phi)),
    0,
  );
}

export function nuMinusM(dt: number, mDeg: number): number {
  const m = mDeg * DEG2RAD;
  return (
    (10.691 + NU_M_DRIFT * dt) * Math.sin(m) +
    0.623 * Math.sin(2 * m) +
    0.05 * Math.sin(3 * m) +
    0.005 * Math.sin(4 * m) +
    0.0005 * Math.sin(5 * m) +
    pbs(dt)
  );
}

export function ls(dt: number): number {
  const m = marsMeanAnomaly(dt);
  return ((afms(dt) + nuMinusM(dt, m)) % 360 + 360) % 360;
}

export function eotHours(lsDeg: number, nuMDeg: number): number {
  const lsr = lsDeg * DEG2RAD;
  const eotDeg =
    2.861 * Math.sin(2 * lsr) -
    0.071 * Math.sin(4 * lsr) +
    0.002 * Math.sin(6 * lsr) -
    nuMDeg;
  return eotDeg / 15;
}

export function mstHours(utc: Date): number {
  const jdUT = jdUt(utc);
  const jdTT = jdUT + ttMinusUtc(utc.getTime() / 1000) / 86400;
  return (24 * ((jdTT - MST_REF_JD) / SOL_DAYS + MST_EPOCH - MST_CORR)) % 24;
}

export function marsSolDate(utc: Date): number {
  const jdUT = jdUt(utc);
  const jdTT = jdUT + ttMinusUtc(utc.getTime() / 1000) / 86400;
  return (jdTT - MST_REF_JD) / SOL_DAYS + MST_EPOCH - MST_CORR;
}

function hms(hours: number): string {
  const total = Math.round((((hours % 24) + 24) % 24) * 3600) % 86400;
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(Math.floor(total / 3600))}:${p(Math.floor((total % 3600) / 60))}:${p(total % 60)}`;
}

function solOfMission(utc: Date, epochUtc: Date): number {
  const elapsed = (utc.getTime() - epochUtc.getTime()) / 1000;
  if (elapsed < 0) return 0;
  return Math.floor(elapsed / (86400 * SOL_DAYS)) + 1;
}

// ---------------------------------------------------------------------------
// Interface publique
// ---------------------------------------------------------------------------

/**
 * Date solaire martienne, sol de mission et heures solaires locale moyenne et vraie.
 *
 * @param utc       Instant UTC.
 * @param lonEast   Longitude de référence du site, degrés Est (convention R2).
 * @param epochUtc  Début du sol 1 de la mission simulée.
 *
 * @returns MarsTime avec msd, sol, lmst, lmst_hours, ltst, ls_deg.
 *
 * Précision : les cas NASA GISS sont retrouvés à mieux que 2 secondes LMST.
 */
export function marsTime(utc: Date, lonEast: number, epochUtc: Date): MarsTime {
  const dt = deltaJ2000Tt(utc);
  const mDeg = marsMeanAnomaly(dt);
  const nm = nuMinusM(dt, mDeg);
  const lsDeg = ls(dt);

  const msd = marsSolDate(utc);
  const mst = mstHours(utc);

  // LMST (C-3) : convention degrés Est → +lon_east / 15
  const lmstHours = ((mst + lonEast / 15) % 24 + 24) % 24;

  // EOT et LTST (C-4)
  const eot = eotHours(lsDeg, nm);
  const ltstHours = ((lmstHours + eot) % 24 + 24) % 24;

  const sol = solOfMission(utc, epochUtc);

  return {
    utc: utc.toISOString(),
    msd,
    sol,
    lmst: hms(lmstHours),
    lmst_hours: lmstHours,
    ltst: hms(ltstHours),
    ls_deg: Math.round(lsDeg * 10000) / 10000,
  };
}

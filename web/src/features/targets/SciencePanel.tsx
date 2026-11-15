/**
 * Panneau « Science du site » (écart E2, étape 5 du scénario) : pourquoi Jezero, et ce que les
 * données NASA disent des cibles. Le texte résume docs/science/jezero.md (tâche S1) ; garder
 * les deux alignés, numéros de sources compris.
 *
 * Le site fictif est une copie synthétique de Jezero : même science, terrain généré.
 */
import { Panel } from "@/shared/ui";
import { useSiteManifest } from "@/shared/hooks";

interface Source {
  n: number;
  label: string;
  url: string;
}

const SOURCES: Source[] = [
  { n: 3, label: "Mangold et al. 2021, Science", url: "https://doi.org/10.1126/science.abl4051" },
  { n: 4, label: "Ehlmann et al. 2008, Nature Geoscience", url: "https://doi.org/10.1038/ngeo207" },
  { n: 5, label: "Goudge et al. 2015, JGR Planets", url: "https://doi.org/10.1002/2014JE004782" },
  { n: 7, label: "Farley et al. 2022, Science", url: "https://doi.org/10.1126/science.abo2196" },
  {
    n: 9,
    label: "NASA JPL 2022, Wildcat Ridge",
    url: "https://www.jpl.nasa.gov/news/nasas-perseverance-rover-investigates-geologically-rich-mars-terrain/",
  },
  {
    n: 10,
    label: "NASA JPL 2022, Three Forks sample depot",
    url: "https://www.jpl.nasa.gov/news/nasas-perseverance-rover-to-begin-building-martian-sample-depot/",
  },
  { n: 13, label: "Coan 2021, NASA NTRS 20210000827", url: "https://ntrs.nasa.gov/citations/20210000827" },
];

interface Finding {
  title: string;
  text: string;
  /** Couche du manifeste qui montre l'indice sur la carte. */
  layer?: string;
  refs: number[];
}

const ORBIT: Finding[] = [
  {
    title: "Delta clays",
    text: "Mars Reconnaissance Orbiter sees Fe/Mg smectites in both deltas: a setting that favours the preservation of organic matter.",
    layer: "crism_minerals",
    refs: [4],
  },
  {
    title: "Carbonates and olivine",
    text: "CRISM spectra show magnesium carbonates and olivine in the western delta, carried in from the watershed.",
    layer: "crism_minerals",
    refs: [5],
  },
];

const ROVER: Finding[] = [
  {
    title: "A true delta",
    text: "Inclined beds laid down in a lake at the delta front and on Kodiak, with boulders brought in by floods.",
    layer: "hirise_vis",
    refs: [3],
  },
  {
    title: "Séítah, an olivine-rich rock",
    text: "An olivine-rich igneous cumulate, altered by CO₂-laden water that left carbonates behind.",
    refs: [7],
  },
  {
    title: "Organic matter",
    text: "Wildcat Ridge, a salty lake mudstone at the delta front, gave the strongest organic signals of the mission.",
    refs: [9],
  },
];

const TARGETS: { name: string; goal: string }[] = [
  { name: "Delta front", goal: "sulfate-bearing lake mudstones and organic matter" },
  { name: "Séítah", goal: "olivine cumulate and alteration carbonates" },
  { name: "Séítah–Máaz contact", goal: "emplacement order of the igneous units" },
  { name: "Kodiak", goal: "delta beds and flood boulders" },
];

function Refs({ refs }: { refs: number[] }) {
  return (
    <span className="text-[var(--text-muted)]">
      {" "}
      [{refs.map((n, i) => (
        <span key={n}>
          {i > 0 && ", "}
          <a href={`#science-src-${n}`} className="text-[var(--text-info)] underline">
            {n}
          </a>
        </span>
      ))}]
    </span>
  );
}

function Findings({ heading, items }: { heading: string; items: Finding[] }) {
  return (
    <>
      <h3 className="mt-2 text-xs font-bold">{heading}</h3>
      <ul className="mt-1 space-y-1">
        {items.map((f) => (
          <li key={f.title}>
            <strong>{f.title}.</strong> {f.text}
            {f.layer && <span className="text-[var(--text-muted)]"> Layer: {f.layer}.</span>}
            <Refs refs={f.refs} />
          </li>
        ))}
      </ul>
    </>
  );
}

export function SciencePanel() {
  const { data: manifest } = useSiteManifest();
  const synthetic = manifest?.site_id === "fictif";
  return (
    <Panel title="Site science">
      <div className="text-xs leading-snug">
        <p>
          <strong>Jezero</strong> is an ancient crater lake whose <strong>delta</strong> trapped
          clays, carbonates and organic matter. Perseverance has already collected and cached
          samples here: astronauts can pick up the work where the rover left off.
          <Refs refs={[3, 10]} />
        </p>
        {synthetic && (
          <p className="mt-1 text-[var(--text-muted)]">
            Demo site: synthetic terrain, Jezero science.
          </p>
        )}
        <Findings heading="Seen from orbit" items={ORBIT} />
        <Findings heading="Measured by Perseverance" items={ROVER} />
        <h3 className="mt-2 text-xs font-bold">Why a walking EVA</h3>
        <p className="mt-1">
          A 6 to 8 hour EVA covers about 2 km around the habitat: all four targets fall within
          that radius.
          <Refs refs={[13]} /> A geologist compares several outcrops and samples only the best
          ones (project assumption).
        </p>
        <details className="mt-2">
          <summary className="cursor-pointer font-bold">Suggested targets</summary>
          <ul className="mt-1 space-y-0.5">
            {TARGETS.map((t) => (
              <li key={t.name}>
                <strong>{t.name}</strong>: {t.goal}
              </li>
            ))}
          </ul>
        </details>
        <details className="mt-1">
          <summary className="cursor-pointer font-bold">Sources</summary>
          <ol className="mt-1 space-y-0.5">
            {SOURCES.map((s) => (
              <li key={s.n} id={`science-src-${s.n}`}>
                [{s.n}]{" "}
                <a href={s.url} target="_blank" rel="noreferrer" className="text-[var(--text-info)] underline">
                  {s.label}
                </a>
              </li>
            ))}
          </ol>
          <p className="mt-1 text-[var(--text-muted)]">Details: docs/science/jezero.md.</p>
        </details>
      </div>
    </Panel>
  );
}

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
    label: "NASA JPL 2022, dépôt de Three Forks",
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
    title: "Argiles du delta",
    text: "Mars Reconnaissance Orbiter voit des smectites Fe/Mg dans les deux deltas : un cadre favorable à la préservation de matière organique.",
    layer: "crism_minerals",
    refs: [4],
  },
  {
    title: "Carbonates et olivine",
    text: "Les spectres CRISM montrent carbonates magnésiens et olivine dans le delta occidental, venus du bassin versant.",
    layer: "crism_minerals",
    refs: [5],
  },
];

const ROVER: Finding[] = [
  {
    title: "Un vrai delta",
    text: "Couches inclinées déposées dans un lac au front du delta et sur Kodiak, blocs apportés par des crues.",
    layer: "hirise_vis",
    refs: [3],
  },
  {
    title: "Séítah, roche à olivine",
    text: "Cumulat igné riche en olivine, altéré par une eau chargée de CO₂ qui y a laissé des carbonates.",
    refs: [7],
  },
  {
    title: "Matière organique",
    text: "Wildcat Ridge, boue de lac salé au front du delta, a donné les signaux organiques les plus forts de la mission.",
    refs: [9],
  },
];

const TARGETS: { name: string; goal: string }[] = [
  { name: "Front du delta", goal: "boues lacustres à sulfates et matière organique" },
  { name: "Séítah", goal: "cumulat à olivine et carbonates d'altération" },
  { name: "Contact Séítah et Máaz", goal: "ordre de mise en place des unités ignées" },
  { name: "Kodiak", goal: "couches du delta et blocs de crue" },
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
            {f.layer && <span className="text-[var(--text-muted)]"> Couche : {f.layer}.</span>}
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
    <Panel title="Science du site">
      <div className="text-xs leading-snug">
        <p>
          <strong>Jezero</strong> est un ancien lac de cratère dont le <strong>delta</strong> a piégé
          argiles, carbonates et matière organique. Perseverance y a déjà prélevé et déposé des
          échantillons : des astronautes peuvent reprendre le travail là où le rover s'est arrêté.
          <Refs refs={[3, 10]} />
        </p>
        {synthetic && (
          <p className="mt-1 text-[var(--text-muted)]">
            Site fictif : terrain synthétique, science de Jezero.
          </p>
        )}
        <Findings heading="Vu depuis l'orbite" items={ORBIT} />
        <Findings heading="Mesuré par Perseverance" items={ROVER} />
        <h3 className="mt-2 text-xs font-bold">Pourquoi une sortie à pied</h3>
        <p className="mt-1">
          Une sortie de 6 à 8 h couvre environ 2 km autour de l'habitat : les quatre cibles tiennent
          dans ce rayon.
          <Refs refs={[13]} /> Un géologue compare plusieurs affleurements et ne prélève que les
          meilleurs (hypothèse du projet).
        </p>
        <details className="mt-2">
          <summary className="cursor-pointer font-bold">Cibles proposées</summary>
          <ul className="mt-1 space-y-0.5">
            {TARGETS.map((t) => (
              <li key={t.name}>
                <strong>{t.name}</strong> : {t.goal}
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
          <p className="mt-1 text-[var(--text-muted)]">Détail : docs/science/jezero.md.</p>
        </details>
      </div>
    </Panel>
  );
}

/** Carnet de sortie imprimable (X1) : chaque entrée en sol, heure locale et UTC. */
import { Link, useParams } from "react-router";
import { downloadJson, formatLonLat, KIND_LABELS, logbookToGeojson } from "./format";
import { useLogbook } from "./queries";
import { Button } from "@/shared/ui";

export function LogbookSheet() {
  const { evaId = "" } = useParams();
  const book = useLogbook(evaId);
  if (book.isError) return <p className="p-6">Logbook for {evaId} unavailable.</p>;
  if (!book.data) return <p className="p-6">Loading logbook…</p>;
  const { entries } = book.data;
  const observations = entries.filter((e) => e.kind === "observation").length;
  return (
    <div className="min-h-full bg-white text-black">
    <article className="mx-auto flex max-w-4xl flex-col gap-4 p-6">
      <nav className="flex flex-wrap gap-2 print:hidden">
        <Link to="/" className="underline">
          ← Back to map
        </Link>
        <Button variant="primary" onClick={() => window.print()}>
          🖶 Print or save as PDF
        </Button>
        <Button onClick={() => downloadJson(`marswalk-${evaId}-logbook.geojson`, logbookToGeojson(book.data))}>
          ⤓ GeoJSON
        </Button>
      </nav>
      <header>
        <h1 className="text-2xl font-bold">Field logbook · {evaId}</h1>
        <p>
          Site {book.data.site_id} · {entries.length} entries · {observations} observations
        </p>
      </header>
      <table className="w-full border-collapse text-sm [&_td]:py-1 [&_td]:pr-3 [&_th]:pr-3">
        <thead>
          <tr className="border-b border-black text-left">
            <th>Sol</th>
            <th>Local time</th>
            <th>UTC</th>
            <th>Type</th>
            <th>Note</th>
            <th>Position</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e, i) => (
            <tr key={`${e.utc}-${i}`} className="border-b border-gray-300 align-top">
              <td>{e.sol}</td>
              <td>{e.lmst}</td>
              <td>{e.utc.replace("T", " ").slice(0, 19)}</td>
              <td>{KIND_LABELS[e.kind]}</td>
              <td>{e.text}</td>
              <td>{formatLonLat(e.position)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </article>
    </div>
  );
}

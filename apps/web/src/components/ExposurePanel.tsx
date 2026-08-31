import type {AnalysisVersion} from "../types";

function currency(value: string): string {
  return new Intl.NumberFormat("en-US", {style: "currency", currency: "USD", maximumFractionDigits: 0}).format(Number(value));
}

export function ExposurePanel({analysis}: {analysis: AnalysisVersion | null}) {
  if (!analysis) return null;
  const predicted = analysis.recommendation?.predicted;
  return <section className="panel" aria-labelledby="exposure-heading">
    <p className="step">02 · Exposure</p>
    <h2 id="exposure-heading">Exposure and lineage</h2>
    {predicted ? <div className="metrics" aria-label="Server-calculated predicted exposure">
      <div><span>Uncovered demand</span><strong>{predicted.uncovered_part_demand.toLocaleString()} units</strong></div>
      <div><span>Revenue at risk</span><strong>{currency(predicted.revenue_at_risk)}</strong></div>
      <div><span>Margin at risk</span><strong>{currency(predicted.margin_at_risk)}</strong></div>
      <div><span>Response cost</span><strong>{currency(predicted.response_cost)}</strong></div>
    </div> : <p>No server-calculated exposure is available for the recommendation.</p>}
    {analysis.recommendation && <div className="lineage">
      <h3>Source data lineage</h3>
      <ul>{analysis.recommendation.source_data_lineage.map((source) => <li key={source}>{source}</li>)}</ul>
      <p>Calculation version: {analysis.material.calculation_version}</p>
    </div>}
  </section>;
}

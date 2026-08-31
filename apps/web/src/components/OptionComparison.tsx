import type {AnalysisVersion, ResponseOption} from "../types";
import {optionDisplayName} from "./optionLabels";

interface OptionComparisonProps {
  analysis: AnalysisVersion | null;
  selectedOption: ResponseOption | null;
  onSelect: (option: ResponseOption) => void;
}

export function OptionComparison({analysis, selectedOption, onSelect}: OptionComparisonProps) {
  if (!analysis) return null;
  return <section className="panel" aria-labelledby="options-heading">
    <p className="step">03 · Options</p>
    <h2 id="options-heading">Response option comparison</h2>
    <div className="option-grid">
      {analysis.response_options.map((option) => {
        const displayName = optionDisplayName(option);
        return <article aria-label={displayName} className={`option-card ${!option.executable ? "blocked" : ""}`} key={option.option_id}>
        <div className="card-labels">
          {option.option_id === analysis.ranking.recommended_option_id && <span className="badge accent">Recommended</span>}
          {!option.executable && <span className="badge danger">Blocked</span>}
        </div>
        <h3>{displayName}</h3>
        {option.predicted ? <dl className="compact-list">
          <div><dt>Uncovered demand</dt><dd>{option.predicted.uncovered_part_demand.toLocaleString()}</dd></div>
          <div><dt>Response cost</dt><dd>${Number(option.predicted.response_cost).toLocaleString()}</dd></div>
          <div><dt>Execution risk</dt><dd>{option.execution_risk}</dd></div>
        </dl> : <p>Predicted outcome unavailable while blocked.</p>}
        {option.blocking_codes.length > 0 && <ul className="blocking-codes">
          {option.blocking_codes.map((code) => <li key={code}>{code}</li>)}
        </ul>}
        <button
          type="button"
          disabled={!option.executable}
          aria-pressed={selectedOption?.option_id === option.option_id}
          onClick={() => onSelect(option)}
        >Select {displayName}</button>
      </article>;
      })}
    </div>
    <div className="trace">
      <h3>Elimination trace</h3>
      {analysis.ranking.stages.length === 0 ? <p>No options were eliminated by ranking stages.</p> : <ol>
        {analysis.ranking.stages.map((stage, index) => <li key={`${stage.comparator}-${index}`}>
          <strong>{stage.comparator.replaceAll("_", " ")}</strong>: threshold {stage.threshold}; eliminated {stage.eliminated_option_ids.join(", ") || "none"}
        </li>)}
      </ol>}
    </div>
  </section>;
}

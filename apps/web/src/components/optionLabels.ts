import type {ResponseOption} from "../types";

const labels: Record<ResponseOption["option_kind"], string> = {
  no_mitigation: "Do nothing — baseline", expedite: "Expedite the partial shipment",
  transfer: "Transfer from another plant", resequence: "Prioritize production for customer needs",
  alternate_source: "Use the alternate supplier", combined: "Combined response",
};
export function optionDisplayName(option: ResponseOption): string {
  return labels[option.option_kind] ?? option.name;
}

const actionSummaries: Record<ResponseOption["option_kind"], string> = {
  no_mitigation: "Keep the current plan without a mitigation response.",
  expedite: "Expedite the proposed shipment from the current supplier.",
  transfer: "Transfer available stock from another plant.",
  resequence: "Prioritize production for customer needs.",
  alternate_source: "Use the alternate supplier after its requirements are met.",
  combined: "Expedite the proposed shipment from the current supplier, transfer stock from another plant, and prioritize production for customer needs.",
};

export function optionActionSummary(option: ResponseOption): string {
  return actionSummaries[option.option_kind] ?? option.name;
}

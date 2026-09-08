import type {ResponseOption} from "../types";

const labels: Record<ResponseOption["option_kind"], string> = {
  no_mitigation: "Do nothing — baseline", expedite: "Expedite the partial shipment",
  transfer: "Transfer from another plant", resequence: "Prioritize production for customer needs",
  alternate_source: "Use the alternate supplier", combined: "Combined response",
};
export function optionDisplayName(option: ResponseOption): string {
  return labels[option.option_kind] ?? option.name;
}

import type {ResponseOption} from "../types";

export function optionDisplayName(option: ResponseOption): string {
  return option.option_kind === "combined" ? "Combined response" : option.name;
}

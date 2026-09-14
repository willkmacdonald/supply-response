export function usd(value: string): string {
  return new Intl.NumberFormat("en-US", {style: "currency", currency: "USD", maximumFractionDigits: 0}).format(Number(value));
}
export function time(value: string | null): string {
  return value ? new Intl.DateTimeFormat("en-US", {dateStyle: "medium", timeStyle: "short"}).format(new Date(value)) : "Not recorded";
}
export function commandKey(prefix: string): string {
  return `${prefix}-${globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`}`;
}

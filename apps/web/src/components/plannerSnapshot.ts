import type {SupportingRecordInput} from "./supportingRecord";
import type {Disruption} from "../types";
import {object, text, whole, positive, validDate, validMoney, nullableDate, parseSnapshotEnvelope} from "./snapshotValidation";

type Inventory = {inventory_id: string; part_id: string; plant_id: string; on_hand: number; quality_hold: number; protected_allocation: number};
type Production = {production_order_id: string; product_id: string; plant_id: string; quantity: number; due_date: string; component_demand: number | null; customer_order_id: string | null; customer_revenue: string | null};
type Customer = {customer_order_line_id: string; production_order_id: string | null; customer_id: string; product_id: string; plant_id: string; quantity: number; due_date: string; unit_revenue: string};
export type PlannerSnapshot = Readonly<{disruption: Disruption | null; inventory: Inventory[] | null; production: Production[] | null; customers: Customer[] | null}>;

function records<T>(v: unknown, parse: (value: unknown) => T | null, id: (value: T) => string): T[] | null {
  if (!Array.isArray(v)) return null;
  const result: T[] = [];
  for (const value of v) { const parsed = parse(value); if (parsed === null) return null; result.push(parsed); }
  return new Set(result.map(id)).size === result.length ? result : null;
}
function parseDisruption(v: unknown): Disruption | null {
  if (!object(v) || !text(v.disruption_id) || !text(v.supplier_id) || !text(v.po_line_id)
    || !text(v.part_id) || !text(v.plant_id) || !positive(v.original_quantity) || !validDate(v.original_due_date)
    || !whole(v.partial_quantity) || v.partial_quantity > v.original_quantity
    || !nullableDate(v.partial_due_date) || !nullableDate(v.recovery_date) || !text(v.source_ref)) return null;
  return {disruption_id: v.disruption_id, supplier_id: v.supplier_id, po_line_id: v.po_line_id, part_id: v.part_id, plant_id: v.plant_id, original_quantity: v.original_quantity, original_due_date: v.original_due_date, partial_quantity: v.partial_quantity, partial_due_date: v.partial_due_date, recovery_date: v.recovery_date, source_ref: v.source_ref};
}
function parseInventory(v: unknown): Inventory | null {
  if (!object(v) || !text(v.inventory_id) || !text(v.part_id) || !text(v.plant_id) || !whole(v.on_hand) || !whole(v.quality_hold) || !whole(v.protected_allocation)) return null;
  return {inventory_id: v.inventory_id, part_id: v.part_id, plant_id: v.plant_id, on_hand: v.on_hand, quality_hold: v.quality_hold, protected_allocation: v.protected_allocation};
}
function parseProduction(v: unknown): Production | null {
  if (!object(v) || !text(v.production_order_id) || !text(v.product_id) || !text(v.plant_id) || !positive(v.quantity) || !validDate(v.due_date) || !(v.component_demand === null || positive(v.component_demand)) || !(v.customer_order_id === null || text(v.customer_order_id)) || !(v.customer_revenue === null || validMoney(v.customer_revenue))) return null;
  return {production_order_id: v.production_order_id, product_id: v.product_id, plant_id: v.plant_id, quantity: v.quantity, due_date: v.due_date, component_demand: v.component_demand, customer_order_id: v.customer_order_id, customer_revenue: v.customer_revenue};
}
function parseCustomer(v: unknown): Customer | null {
  if (!object(v) || !text(v.customer_order_line_id) || !(v.production_order_id === null || text(v.production_order_id)) || !text(v.customer_id) || !text(v.product_id) || !text(v.plant_id) || !positive(v.quantity) || !validDate(v.due_date) || !validMoney(v.unit_revenue)) return null;
  return {customer_order_line_id: v.customer_order_line_id, production_order_id: v.production_order_id, customer_id: v.customer_id, product_id: v.product_id, plant_id: v.plant_id, quantity: v.quantity, due_date: v.due_date, unit_revenue: v.unit_revenue};
}
export function readPlannerSnapshot(input: SupportingRecordInput): PlannerSnapshot | null {
  const s = parseSnapshotEnvelope(input);
  return s ? {disruption: parseDisruption(s.disruption), inventory: records(s.inventory_positions, parseInventory, value => value.inventory_id), production: records(s.production_orders, parseProduction, value => value.production_order_id), customers: records(s.customer_orders, parseCustomer, value => value.customer_order_line_id)} : null;
}
export function customerLineBasis(snapshot: PlannerSnapshot | null, protectedIds: string[]): {total: number; missed: number} | null {
  const production = snapshot?.production; const customers = snapshot?.customers;
  if (!production?.length || !customers || production.length !== customers.length || new Set(protectedIds).size !== protectedIds.length) return null;
  const ids = production.map(order => order.customer_order_id);
  if (new Set(ids).size !== ids.length || ids.some(id => id === null) || protectedIds.some(id => !ids.includes(id))) return null;
  const cents = (value: string) => BigInt(value.replace(".", ""));
  const linked = production.every(order => { const customer = customers.find(line => line.customer_order_line_id === order.customer_order_id); return customer && customer.production_order_id === order.production_order_id && customer.product_id === order.product_id && customer.plant_id === order.plant_id && customer.quantity === order.quantity && customer.due_date === order.due_date && order.customer_revenue !== null && cents(order.customer_revenue) === BigInt(customer.quantity) * cents(customer.unit_revenue); });
  return linked ? {total: production.length, missed: production.length - protectedIds.length} : null;
}

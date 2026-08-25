import { currency } from '../api';
import type { ExposureResult } from '../types';

export default function ExposurePanel({ exposure }: { exposure: ExposureResult | null }) {
  if (!exposure) {
    return (
      <section className="panel">
        <h3>Exposure</h3>
        <p>The case has not been analyzed yet.</p>
      </section>
    );
  }

  return (
    <section className="panel">
      <h3>
        Exposure · {exposure.part_id} at {exposure.plant_id}
      </h3>
      <div className="metrics">
        <div className="metric">
          <span>Usable inventory</span>
          <strong>{exposure.usable_inventory.toLocaleString()}</strong>
        </div>
        <div className="metric">
          <span>First stockout</span>
          <strong>{exposure.first_stockout_date ?? 'none'}</strong>
        </div>
        <div className="metric">
          <span>Max shortage</span>
          <strong>{exposure.max_shortage_qty.toLocaleString()}</strong>
        </div>
        <div className="metric">
          <span>Revenue at risk</span>
          <strong>{currency(exposure.revenue_at_risk)}</strong>
        </div>
        <div className="metric">
          <span>Calculation version</span>
          <strong>{exposure.calculation_version}</strong>
        </div>
      </div>

      <h4>Affected production orders</h4>
      <table>
        <thead>
          <tr>
            <th>Production order</th>
            <th>Due</th>
            <th>Required</th>
            <th>Shortage</th>
            <th>Lost output</th>
          </tr>
        </thead>
        <tbody>
          {exposure.affected_production_orders.map((order) => (
            <tr key={order.production_order_id}>
              <td>{order.production_order_id}</td>
              <td>{order.due_date}</td>
              <td>{order.required_qty.toLocaleString()}</td>
              <td>{order.shortage_qty.toLocaleString()}</td>
              <td>{order.lost_output_qty.toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h4>Affected customer orders</h4>
      <table>
        <thead>
          <tr>
            <th>Customer order</th>
            <th>Customer</th>
            <th>Promised</th>
            <th>At risk</th>
            <th>Revenue at risk</th>
          </tr>
        </thead>
        <tbody>
          {exposure.affected_customer_orders.map((order) => (
            <tr key={order.customer_order_id}>
              <td>{order.customer_order_id}</td>
              <td>{order.customer_id}</td>
              <td>{order.promised_date}</td>
              <td>{order.at_risk_qty.toLocaleString()}</td>
              <td>{currency(order.revenue_at_risk)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h4>Assumptions</h4>
      <ul>
        {exposure.assumptions.map((assumption) => (
          <li key={assumption}>{assumption}</li>
        ))}
      </ul>
    </section>
  );
}

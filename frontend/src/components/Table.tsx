import type { ReactNode } from 'react';
import { type Entity, text } from '../api/client';
export function Table({ rows, columns, action }: { rows: Entity[]; columns: {key: string; label: string; render?: (row: Entity) => ReactNode}[]; action?: (row: Entity) => ReactNode }) {
  if (!rows.length) return <div className="empty">No records yet. Add your first record to get started.</div>;
  return <div className="table-scroll"><table><thead><tr>{columns.map(c => <th key={c.key}>{c.label}</th>)}{action && <th>Actions</th>}</tr></thead><tbody>{rows.map(row => <tr key={row.id}>{columns.map(c => <td key={c.key}>{c.render ? c.render(row) : text(row, c.key)}</td>)}{action && <td>{action(row)}</td>}</tr>)}</tbody></table></div>;
}

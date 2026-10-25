import { useState, type FormEvent } from 'react';
export type Field = { name: string; label: string; type?: string; optional?: boolean; options?: {value: string; label: string}[]; min?: string; maxLength?: number };
export function Editor({ title, fields, initial = {}, onSave, onClose }: {
  title: string; fields: Field[]; initial?: Record<string, unknown>; onSave: (values: Record<string, unknown>) => Promise<void>; onClose: () => void;
}) {
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(''); setBusy(true);
    const form = new FormData(event.currentTarget);
    const values: Record<string, unknown> = {};
    for (const field of fields) {
      const value = String(form.get(field.name) ?? '').trim();
      values[field.name] = field.type === 'checkbox' ? form.has(field.name) : value || (field.optional ? null : '');
    }
    try { await onSave(values); onClose(); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not save this record.'); }
    finally { setBusy(false); }
  }
  return <div className="modal-backdrop"><section role="dialog" aria-modal="true" aria-label={title} className="modal">
    <div className="section-heading"><h2>{title}</h2><button type="button" className="secondary" disabled={busy} onClick={onClose}>Close</button></div>
    <form onSubmit={submit} className="form-grid">
      {fields.map(field => <label key={field.name}>{field.label}
        {field.options ? <select name={field.name} required={!field.optional} defaultValue={String(initial[field.name] ?? '')}><option value="">Select…</option>{field.options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}</select>
          : field.type === 'checkbox' ? <input type="checkbox" name={field.name} defaultChecked={Boolean(initial[field.name])}/>
          : <input name={field.name} type={field.type || 'text'} required={!field.optional} defaultValue={String(initial[field.name] ?? '')} min={field.min} step={field.type === 'number' ? '0.01' : undefined} maxLength={field.maxLength ?? 160}/>}
      </label>)}
      {error && <p role="alert" className="error">{error}</p>}
      <button disabled={busy} type="submit">{busy ? 'Saving…' : 'Save record'}</button>
    </form>
  </section></div>;
}

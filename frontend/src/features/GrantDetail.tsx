import { useEffect, useState } from 'react';
import { allPages, api, text, type Entity } from '../api/client';
import { Editor, type Field } from '../components/Form';
import { Table } from '../components/Table';
import { money, subtract } from '../lib/money';
const amount = (name: string, label: string, min = '0'): Field => ({name, label, type:'number', min});
type Edit = {title: string; fields: Field[]; path: string; initial?: Entity; transform?: (v: Record<string,unknown>) => Record<string,unknown>};
export function GrantDetail({ id, onBack }: {id: string; onBack: () => void}) {
  const [grant, setGrant] = useState<Entity | null>(null);
  const [categories, setCategories] = useState<Entity[]>([]);
  const [expenses, setExpenses] = useState<Entity[]>([]);
  const [reports, setReports] = useState<Entity[]>([]);
  const [metrics, setMetrics] = useState<Entity[]>([]);
  const [edit, setEdit] = useState<Edit | null>(null);
  const [history, setHistory] = useState<Entity[] | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const root = `/grants/${id}`;
  async function load() {
    setLoading(true); setError('');
    try {
      const [g,c,e,r,m] = await Promise.all([api<Entity>(root),api<Entity[]>(`${root}/budget-categories`),allPages(`${root}/expenses`),api<Entity[]>(`${root}/reporting-deadlines`),api<Entity[]>(`${root}/impact-metrics`)]);
      setGrant(g); setCategories(c); setExpenses(e); setReports(r); setMetrics(m);
    } catch(e) { setError(e instanceof Error ? e.message : 'Could not load the grant.'); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, [id]);
  const categoryFields: Field[] = [{name:'name',label:'Category name'},amount('allocated_amount','Allocation')];
  const expenseFields: Field[] = [{name:'budget_category_id',label:'Budget category',options:categories.map(c => ({value:c.id,label:text(c,'name')}))},amount('amount','Amount','0.01'),{name:'expense_date',label:'Expense date',type:'date'},{name:'description',label:'Description',maxLength:2000},{name:'reference',label:'Reference',optional:true,maxLength:200}];
  const reportFields: Field[] = [{name:'title',label:'Report title'},{name:'due_date',label:'Due date',type:'date'},{name:'submitted',label:'Submitted',type:'checkbox'}];
  const metricFields: Field[] = [{name:'name',label:'Outcome name'},{name:'unit',label:'Unit (e.g. meals)'},amount('target_value','Target','0.01')];
  const currency = grant ? text(grant,'currency') : '';
  return <>
    <button className="secondary" onClick={onBack}>← All grants</button>
    {loading && <p role="status">Loading grant…</p>}
    {error && <div role="alert" className="error">{error} <button onClick={load}>Retry</button></div>}
    {grant && <><div className="section-heading"><div><p className="eyebrow">{text(grant,'donor_name')}</p><h1>{text(grant,'name')}</h1><p className="muted">{text(grant,'start_date')} – {text(grant,'end_date')}</p></div><span className="badge">{text(grant,'status')}</span></div>
    <div className="stats">{[['Award','award_amount'],['Allocated','allocated'],['Spent','spent']].map(([label,key]) => <div className="stat" key={key}><span>{label}</span><strong>{money(text(grant,key),currency)}</strong></div>)}<div className="stat"><span>Award remaining</span><strong>{money(subtract(text(grant,'award_amount'),text(grant,'spent')),currency)}</strong></div></div>
    <section className="panel"><div className="section-heading"><h2>Budget categories</h2><button disabled={grant.status === 'closed'} onClick={() => setEdit({title:'Allocate funds',fields:categoryFields,path:`${root}/budget-categories`})}>Add category</button></div><Table rows={categories} columns={[{key:'name',label:'Category'},{key:'allocated_amount',label:'Allocated',render:r => money(text(r,'allocated_amount'),currency)},{key:'spent',label:'Spent',render:r => money(text(r,'spent'),currency)},{key:'balance',label:'Available',render:r => money(subtract(text(r,'allocated_amount'),text(r,'spent')),currency)}]} action={r => <button className="link-button" disabled={grant.status === 'closed'} onClick={() => setEdit({title:'Edit allocation',fields:categoryFields,path:`/budget-categories/${r.id}`,initial:r})}>Edit</button>}/></section>
    <section className="panel"><div className="section-heading"><h2>Expenses</h2><button disabled={!categories.length || grant.status === 'closed'} onClick={() => setEdit({title:'Record expense',fields:expenseFields,path:`${root}/expenses`})}>Record expense</button></div><Table rows={expenses} columns={[{key:'expense_date',label:'Date'},{key:'category_name',label:'Category'},{key:'description',label:'Description'},{key:'amount',label:'Amount',render:r => money(text(r,'amount'),currency)}]} action={r => <button className="link-button" disabled={grant.status === 'closed'} onClick={() => setEdit({title:'Edit expense',fields:expenseFields.filter(f => f.name !== 'budget_category_id'),path:`/expenses/${r.id}`,initial:r,transform:v => ({...v,budget_category_id:r.budget_category_id})})}>Edit</button>}/></section>
    <section className="panel"><div className="section-heading"><h2>Reporting deadlines</h2><button onClick={() => setEdit({title:'Add deadline',fields:reportFields,path:`${root}/reporting-deadlines`})}>Add deadline</button></div><Table rows={reports} columns={[{key:'title',label:'Report'},{key:'due_date',label:'Due date'},{key:'status',label:'Status'}]} action={r => <button className="link-button" onClick={() => setEdit({title:'Update deadline',fields:reportFields,path:`/reporting-deadlines/${r.id}`,initial:{...r,submitted:Boolean(r.submitted_at)}})}>Edit / submit</button>}/></section>
    <section className="panel"><div className="section-heading"><h2>Impact tracking</h2><button onClick={() => setEdit({title:'Define outcome',fields:metricFields,path:`${root}/impact-metrics`})}>Add outcome</button></div><Table rows={metrics} columns={[{key:'name',label:'Outcome'},{key:'actual_value',label:'Delivered'},{key:'target_value',label:'Target'},{key:'unit',label:'Unit'}]} action={r => <div className="actions"><button className="link-button" onClick={() => setEdit({title:'Record impact',fields:[{name:'period_start',label:'Period start',type:'date'},{name:'period_end',label:'Period end',type:'date'},amount('actual_value','Delivered this period'),{name:'notes',label:'Notes',optional:true,maxLength:2000}],path:`/impact-metrics/${r.id}/updates`})}>Record</button><button className="link-button" onClick={() => setEdit({title:'Edit outcome',fields:metricFields,path:`/impact-metrics/${r.id}`,initial:r})}>Edit</button><button className="link-button" onClick={async () => { try { setHistory(await api<Entity[]>(`/impact-metrics/${r.id}/updates`)); } catch(e) { setError((e as Error).message); } }}>History</button></div>}/><p className="muted">Use non-overlapping periods for additive counts. Count each activity once.</p></section>
    {history && <section className="panel"><div className="section-heading"><h2>Impact history</h2><button className="secondary" onClick={() => setHistory(null)}>Close history</button></div><Table rows={history} columns={[{key:'period_start',label:'From'},{key:'period_end',label:'To'},{key:'actual_value',label:'Delivered'},{key:'notes',label:'Notes'}]}/></section>}
    </>}
    {edit && <Editor title={edit.title} fields={edit.fields} initial={edit.initial} onClose={() => setEdit(null)} onSave={async values => { await api(edit.path,edit.initial ? 'PATCH' : 'POST',edit.transform ? edit.transform(values) : values); setHistory(null); await load(); }}/>} 
  </>;
}

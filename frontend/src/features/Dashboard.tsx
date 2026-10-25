import { useEffect, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api, text, type Entity } from '../api/client';
import { money, subtract } from '../lib/money';
import { Table } from '../components/Table';
type Totals = { currency: string; awarded: string; allocated: string; spent: string; remaining: string };
type DashboardData = { grant_count: number; totals: Totals[]; grants: Entity[]; deadlines: Entity[]; impact: Entity[] };
export function Dashboard({ donors }: {donors: Entity[]}) {
  const [donor, setDonor] = useState('');
  const [data, setData] = useState<DashboardData | null>(null);
  const [currency, setCurrency] = useState('');
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  useEffect(() => { let active = true; setData(null); setError('');
    api<DashboardData>(`/dashboard${donor ? `?donor_id=${donor}` : ''}`).then(value => { if (active) { setData(value); setCurrency(value.totals[0]?.currency || ''); } }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [donor, retry]);
  const total = data?.totals.find(t => t.currency === currency);
  const alerts = data?.deadlines.filter(r => ['overdue', 'due_soon'].includes(text(r, 'status'))) || [];
  const charts = data?.grants.filter(g => g.currency === currency).map(g => ({ name: text(g, 'name'), Allocated: Number(g.allocated), Spent: Number(g.spent) })) || [];
  return <>
    <div className="section-heading"><div><p className="eyebrow">Your organization at a glance</p><h1>Funding overview</h1></div><div className="filters"><label>Donor<select value={donor} onChange={e => setDonor(e.target.value)}><option value="">All donors</option>{donors.map(d => <option key={d.id} value={d.id}>{text(d, 'name')}</option>)}</select></label><label>Currency<select value={currency} onChange={e => setCurrency(e.target.value)}><option value="" disabled>Select currency</option>{data?.totals.map(t => <option key={t.currency}>{t.currency}</option>)}</select></label></div></div>
    {error && <div className="error" role="alert">{error} <button onClick={() => setRetry(retry + 1)}>Retry</button></div>}
    {!data && !error && <p role="status">Loading dashboard…</p>}
    {data && <>
      <div className="stats">{[['Grants', String(data.grant_count)], ['Awarded', total ? money(total.awarded, currency) : '—'], ['Allocated', total ? money(total.allocated, currency) : '—'], ['Spent', total ? money(total.spent, currency) : '—'], ['Award remaining', total ? money(total.remaining, currency) : '—']].map(([label,value]) => <div className="stat" key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
      <section className="panel"><div className="section-heading"><h2>Budget & expenditure</h2><span className="badge">{currency || 'No grants yet'}</span></div>{charts.length ? <ResponsiveContainer width="100%" height={300}><BarChart data={charts}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="name"/><YAxis/><Tooltip/><Legend/><Bar dataKey="Allocated" fill="#95b4a5" radius={[4,4,0,0]}/><Bar dataKey="Spent" fill="#154734" radius={[4,4,0,0]}/></BarChart></ResponsiveContainer> : <p className="empty">Create a grant to see its funding here.</p>}<p className="muted">Chart values are approximate. Financial tables use exact decimal amounts.</p></section>
      <section className="panel"><h2>Reporting alerts <span className="badge">{alerts.length}</span></h2><Table rows={alerts} columns={[{key:'grant_name',label:'Grant'},{key:'title',label:'Report'},{key:'due_date',label:'Due date'},{key:'status',label:'Status',render:r => <span className={`badge ${r.status === 'overdue' ? 'warning' : ''}`}>{text(r,'status').replace('_',' ')}</span>}]}/></section>
      <section className="panel"><h2>Grant balances</h2><Table rows={data.grants.filter(g => g.currency === currency)} columns={[{key:'name',label:'Grant'},{key:'donor_name',label:'Donor'},{key:'award_amount',label:'Award',render:r => money(text(r,'award_amount'),currency)},{key:'allocated',label:'Unallocated',render:r => money(subtract(text(r,'award_amount'),text(r,'allocated')),currency)},{key:'spent',label:'Award remaining',render:r => money(subtract(text(r,'award_amount'),text(r,'spent')),currency)}]}/></section>
      <section className="panel"><h2>Impact outcomes</h2><Table rows={data.impact} columns={[{key:'grant_name',label:'Grant'},{key:'name',label:'Outcome'},{key:'actual_value',label:'Delivered'},{key:'target_value',label:'Target'},{key:'unit',label:'Unit'}]}/><p className="muted">Additive outcomes only. Count each activity once across reporting periods.</p></section>
    </>}
  </>;
}

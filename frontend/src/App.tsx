import { useEffect, useState, type FormEvent } from 'react';
import type { Session } from '@supabase/supabase-js';
import { supabase } from './lib/supabase';
import { api, allPages, text, type Entity } from './api/client';
import { Editor, type Field } from './components/Form';
import { Table } from './components/Table';
import { Dashboard } from './features/Dashboard';
import { GrantDetail } from './features/GrantDetail';
import { money } from './lib/money';

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [checking, setChecking] = useState(true);
  const [staff, setStaff] = useState<Record<string,string> | null>(null);
  const [page, setPage] = useState('dashboard');
  const [donors, setDonors] = useState<Entity[]>([]);
  const [grants, setGrants] = useState<Entity[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [loginBusy, setLoginBusy] = useState(false);
  const [editor, setEditor] = useState<{kind: 'donors' | 'grants'; row?: Entity} | null>(null);
  useEffect(() => {
    if (!supabase) { setChecking(false); return; }
    supabase.auth.getSession().then(({data,error}) => { if (error) setError(error.message); setSession(data.session); setChecking(false); });
    const { data } = supabase.auth.onAuthStateChange((_event,next) => { setSession(next); if (!next) { setStaff(null); setDonors([]); setGrants([]); setSelected(null); } });
    return () => data.subscription.unsubscribe();
  }, []);
  async function refresh() {
    setError(''); setLoading(true);
    try {
      const user = await api<Record<string,string>>('/me');
      const [d,g] = await Promise.all([allPages('/donors'),allPages('/grants')]);
      setStaff(user); setDonors(d); setGrants(g);
    } catch(e) { setError((e as Error).message); }
    finally { setLoading(false); }
  }
  useEffect(() => { if (session) void refresh(); }, [session?.access_token]);
  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(''); setLoginBusy(true);
    const data = new FormData(event.currentTarget);
    try {
      const result = await supabase!.auth.signInWithPassword({email:String(data.get('email')),password:String(data.get('password'))});
      if (result.error) setError(result.error.message);
    } catch { setError('Sign-in service is unavailable. Try again.'); }
    finally { setLoginBusy(false); }
  }
  const donorFields: Field[] = [{name:'name',label:'Donor name'},{name:'contact_email',label:'Contact email',type:'email',optional:true},{name:'is_active',label:'Active donor',type:'checkbox'}];
  const grantFields: Field[] = [{name:'name',label:'Grant name'},{name:'donor_id',label:'Donor',options:donors.map(d => ({value:d.id,label:text(d,'name')}))},{name:'award_amount',label:'Award amount',type:'number',min:'0.01'},{name:'currency',label:'Currency code (e.g. USD)',maxLength:3},{name:'start_date',label:'Start date',type:'date'},{name:'end_date',label:'End date',type:'date'},{name:'status',label:'Status',options:['draft','active','closed'].map(value => ({value,label:value}))}];
  if (!supabase) return <main className="setup panel"><p className="eyebrow">Grantwise</p><h1>Connect your workspace</h1><p>Copy frontend/.env.example to frontend/.env, add your Supabase URL and publishable key, and restart the development server.</p><p className="muted">See the README for database setup and staff provisioning. No sample data is shown as live data.</p></main>;
  if (checking) return <main className="setup" role="status">Checking session…</main>;
  if (!session) return <main className="login"><section className="login-story"><span className="brand">◈ Grantwise</span><h1>More clarity.<br/>More impact.</h1><p>Your funding, reporting, and outcomes.<br/>One shared place to keep them moving.</p></section><section className="login-form"><p className="eyebrow">Nonprofit workspace</p><h2>Welcome back</h2><p className="muted">Sign in with your staff account.</p><form className="form-grid" onSubmit={login}><label>Email<input name="email" type="email" autoComplete="username" required/></label><label>Password<input name="password" type="password" autoComplete="current-password" required/></label>{error && <p role="alert" className="error">{error}</p>}<button disabled={loginBusy}>{loginBusy ? 'Signing in…' : 'Sign in'}</button></form><p className="muted">Access is managed by your organization’s administrator.</p></section></main>;
  return <div className="app-shell"><aside><span className="brand">◈ Grantwise</span><p className="eyebrow">Nonprofit workspace</p><nav>{[['dashboard','Overview'],['grants','Grants'],['donors','Donors']].map(([key,label]) => <button key={key} className={page === key ? 'active' : ''} onClick={() => {setPage(key);setSelected(null);}}>{label}</button>)}</nav><div className="account"><strong>{staff?.display_name || 'Staff account'}</strong><span>{session.user.email}</span><button className="secondary" onClick={async () => { const {error} = await supabase!.auth.signOut(); if (error) setError(error.message); }}>Sign out</button></div></aside><main className="content">
    {error && <div role="alert" className="error">{error} <button onClick={refresh}>Retry</button></div>}
    {loading && <p role="status">Loading workspace…</p>}
    {staff && page === 'dashboard' && <Dashboard donors={donors}/>}
    {staff && page === 'grants' && selected && <GrantDetail key={selected} id={selected} onBack={() => {setSelected(null);void refresh();}}/>}
    {staff && (page === 'donors' || (page === 'grants' && !selected)) && <><div className="section-heading"><div><p className="eyebrow">Your funding relationships</p><h1>{page === 'donors' ? 'Donors' : 'Grants'}</h1></div><button disabled={page === 'grants' && !donors.length} onClick={() => setEditor({kind:page as 'donors'|'grants'})}>Add {page === 'donors' ? 'donor' : 'grant'}</button></div>{page === 'grants' && !donors.length && <p className="notice">Add a donor before creating your first grant.</p>}<section className="panel"><Table rows={page === 'donors' ? donors : grants} columns={page === 'donors' ? [{key:'name',label:'Name'},{key:'contact_email',label:'Email'},{key:'is_active',label:'Status',render:r => r.is_active ? 'Active' : 'Inactive'}] : [{key:'name',label:'Grant'},{key:'donor_name',label:'Donor'},{key:'award_amount',label:'Award',render:r => money(text(r,'award_amount'),text(r,'currency'))},{key:'end_date',label:'End date'},{key:'status',label:'Status'}]} action={r => <div className="actions">{page === 'grants' && <button className="link-button" onClick={() => setSelected(r.id)}>View</button>}<button className="link-button" onClick={() => setEditor({kind:page as 'donors'|'grants',row:r})}>Edit</button></div>}/></section></>}
    {editor && <Editor title={`${editor.row ? 'Edit' : 'Add'} ${editor.kind === 'donors' ? 'donor' : 'grant'}`} fields={editor.kind === 'donors' ? donorFields : grantFields} initial={editor.row || (editor.kind === 'donors' ? {is_active:true} : {status:'draft',currency:'USD'})} onClose={() => setEditor(null)} onSave={async values => { if (editor.kind === 'grants') values.currency = String(values.currency).toUpperCase(); await api(`/${editor.kind}${editor.row ? `/${editor.row.id}` : ''}`,editor.row ? 'PATCH' : 'POST',values); await refresh(); }}/>} 
  </main></div>;
}


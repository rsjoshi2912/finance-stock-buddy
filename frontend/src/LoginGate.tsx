import { useEffect, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { BarChart3, LockKeyhole } from 'lucide-react';
import { api, clearCredentials, remoteApi, setCredentials } from './api';

export default function LoginGate({ children }: { children: ReactNode }) {
  const [signedIn, setSignedIn] = useState(!remoteApi);
  const [user, setUser] = useState('ravi');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  function signOut() { clearCredentials(); setSignedIn(false); }
  useEffect(() => {
    window.addEventListener('journal:sign-out', signOut);
    return () => window.removeEventListener('journal:sign-out', signOut);
  }, []);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setCredentials(user, password);
    try { await api('session'); setPassword(''); setSignedIn(true); }
    catch (e) { clearCredentials(); setError(e instanceof Error ? e.message : 'Could not sign in.'); }
    finally { setBusy(false); }
  }
  if (signedIn) return <>{children}{remoteApi && <button className="sign-out" onClick={signOut}>Sign out</button>}</>;
  return <main className="login-page"><form className="login-card" onSubmit={submit}>
    <span className="brand-mark"><BarChart3 size={25}/></span>
    <h1>Your private journal.</h1><p>Sign in to see your calls and results.</p>
    <label>Name<input autoComplete="username" value={user} onChange={e => setUser(e.target.value)} required/></label>
    <label>Password<input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required/></label>
    {error && <p className="negative" role="alert">{error}</p>}
    <button className="button primary" disabled={busy}>{busy ? 'Signing in…' : 'Open my journal'}</button>
    <small><LockKeyhole size={13}/> Your password is not saved by this app.</small>
  </form></main>;
}

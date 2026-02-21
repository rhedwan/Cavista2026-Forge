'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { login, register, getError } from '../../lib/api';
import { setToken, setSessionUser } from '../../lib/session';
import Icon from '../../components/Icon';

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [specialty, setSpecialty] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const result = mode === 'login'
        ? await login(email, password)
        : await register({ email, password, full_name: fullName, specialty: specialty || undefined });
      setToken(result.access_token);
      setSessionUser(result.user);
      router.push('/');
    } catch (err) {
      setError(getError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center size-14 rounded-2xl bg-primary/10 mb-4">
            <Icon name="medical_services" className="text-primary text-3xl" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900">AidCare</h1>
          <p className="text-sm text-slate-500 mt-1">AI Clinical Copilot</p>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <div className="flex rounded-lg bg-slate-100 p-1 mb-6">
            <button
              onClick={() => setMode('login')}
              className={`flex-1 rounded-md py-2 text-sm font-medium transition ${
                mode === 'login' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500'
              }`}
            >
              Sign In
            </button>
            <button
              onClick={() => setMode('register')}
              className={`flex-1 rounded-md py-2 text-sm font-medium transition ${
                mode === 'register' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500'
              }`}
            >
              Register
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'register' && (
              <>
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1.5">Full Name</label>
                  <input type="text" required value={fullName} onChange={e => setFullName(e.target.value)}
                    className="w-full h-10 rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm focus:ring-2 focus:ring-primary focus:border-transparent"
                    placeholder="Dr. Ada Okafor" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1.5">Specialty</label>
                  <input type="text" value={specialty} onChange={e => setSpecialty(e.target.value)}
                    className="w-full h-10 rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm focus:ring-2 focus:ring-primary focus:border-transparent"
                    placeholder="General Medicine" />
                </div>
              </>
            )}
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1.5">Email</label>
              <input type="email" required value={email} onChange={e => setEmail(e.target.value)}
                className="w-full h-10 rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm focus:ring-2 focus:ring-primary focus:border-transparent"
                placeholder="doctor@hospital.ng" />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1.5">Password</label>
              <input type="password" required value={password} onChange={e => setPassword(e.target.value)}
                className="w-full h-10 rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm focus:ring-2 focus:ring-primary focus:border-transparent"
                placeholder="••••••••" minLength={6} />
            </div>
            {error && (
              <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">{error}</div>
            )}
            <button type="submit" disabled={loading}
              className="w-full h-10 rounded-lg bg-primary text-white text-sm font-medium hover:bg-primary-hover transition disabled:opacity-50 shadow-sm shadow-blue-200">
              {loading ? 'Please wait...' : mode === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

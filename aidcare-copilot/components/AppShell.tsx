'use client';

import { useEffect, useState, ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import Header from './Header';
import { getSessionUser } from '../lib/session';
import { AuthUser } from '../types';

export default function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const u = getSessionUser();
    if (!u) {
      router.push('/login');
      return;
    }
    setUser(u);
    setReady(true);
  }, [router]);

  if (!ready) return null;

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <Header user={user} />
      <div className="flex-1 flex flex-col">{children}</div>
    </div>
  );
}

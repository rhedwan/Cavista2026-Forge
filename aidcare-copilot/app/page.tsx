'use client';

import { useRouter } from 'next/navigation';
import AppShell from '../components/AppShell';
import Icon from '../components/Icon';
import { getSessionUser } from '../lib/session';

const CARDS = [
  { title: 'Triage', desc: 'Assess patient urgency in their language', icon: 'stethoscope', href: '/triage', color: '#10b981' },
  { title: 'Scribe', desc: 'Record consultation & auto-generate SOAP', icon: 'mic', href: '/scribe', color: '#2563eb' },
  { title: 'Patients', desc: 'View patient records and history', icon: 'group', href: '/patients', color: '#f59e0b' },
  { title: 'Handover', desc: 'Generate shift handover report', icon: 'swap_horiz', href: '/handover', color: '#ef4444' },
];

export default function DashboardPage() {
  const router = useRouter();
  const user = typeof window !== 'undefined' ? getSessionUser() : null;

  return (
    <AppShell>
      <main className="flex-1 p-6 lg:p-10 max-w-6xl mx-auto w-full">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-slate-900">
            Welcome back{user ? `, ${user.name.split(' ')[0]}` : ''}
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            {user?.hospital_name || 'AidCare'} {user?.ward_name ? `\u2022 ${user.ward_name}` : ''}
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {CARDS.map(card => (
            <button
              key={card.href}
              onClick={() => router.push(card.href)}
              className="bg-white rounded-xl border border-slate-200 p-5 text-left hover:shadow-md hover:border-slate-300 transition-all group"
            >
              <div
                className="size-10 rounded-lg flex items-center justify-center mb-4"
                style={{ background: `${card.color}15`, color: card.color }}
              >
                <Icon name={card.icon} className="text-2xl" />
              </div>
              <h3 className="text-base font-semibold text-slate-900 group-hover:text-primary transition-colors">{card.title}</h3>
              <p className="text-sm text-slate-500 mt-1">{card.desc}</p>
            </button>
          ))}
        </div>
      </main>
    </AppShell>
  );
}

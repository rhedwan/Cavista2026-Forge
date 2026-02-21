'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import Icon from './Icon';
import { getSessionUser, clearSession } from '../lib/session';
import { AuthUser } from '../types';

const NAV_LINKS = [
  { href: '/', label: 'Dashboard' },
  { href: '/triage', label: 'Triage' },
  { href: '/scribe', label: 'Scribe' },
  { href: '/patients', label: 'Patients' },
  { href: '/handover', label: 'Handover' },
];

export default function Header({ user }: { user: AuthUser | null }) {
  const pathname = usePathname();
  const router = useRouter();

  return (
    <header className="sticky top-0 z-50 flex items-center justify-between border-b border-slate-200 bg-white px-6 lg:px-10 py-3 shadow-sm">
      <div className="flex items-center gap-8">
        <Link href="/" className="flex items-center gap-3 text-primary">
          <div className="size-8 bg-primary/10 flex items-center justify-center rounded-lg">
            <Icon name="medical_services" className="text-primary text-xl" />
          </div>
          <h2 className="text-slate-900 text-xl font-bold leading-tight tracking-tight">AidCare</h2>
        </Link>

        <label className="hidden md:flex flex-col min-w-40 max-w-64">
          <div className="flex w-full items-stretch rounded-lg h-10 ring-1 ring-slate-200 focus-within:ring-2 focus-within:ring-primary">
            <div className="text-slate-500 flex bg-slate-50 items-center justify-center pl-4 rounded-l-lg">
              <Icon name="search" className="text-xl" />
            </div>
            <input
              className="w-full min-w-0 flex-1 rounded-lg bg-slate-50 focus:outline-none focus:ring-0 border-none h-full placeholder:text-slate-400 px-4 pl-2 text-sm"
              placeholder="Search Patients"
            />
          </div>
        </label>
      </div>

      <div className="flex flex-1 justify-end gap-8 items-center">
        <nav className="hidden lg:flex items-center gap-6">
          {NAV_LINKS.map((link) => {
            const active = pathname === link.href || (link.href !== '/' && pathname.startsWith(link.href));
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`text-sm font-medium leading-normal transition-colors ${
                  active ? 'text-primary' : 'text-slate-900 hover:text-primary'
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-4">
          <button className="relative flex items-center justify-center size-10 rounded-full hover:bg-slate-100 text-slate-600 transition-colors">
            <Icon name="notifications" />
            <span className="absolute top-2 right-2 size-2 bg-red-500 rounded-full border border-white" />
          </button>
          {user && (
            <button
              onClick={() => { clearSession(); router.push('/login'); }}
              className="flex items-center gap-2"
            >
              <div className="size-10 rounded-full bg-primary/10 flex items-center justify-center text-sm font-bold text-primary ring-2 ring-slate-100">
                {user.name.split(' ').map(n => n[0]).join('').slice(0, 2)}
              </div>
            </button>
          )}
        </div>
      </div>
    </header>
  );
}

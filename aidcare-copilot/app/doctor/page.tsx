'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { getDoctors } from '../../lib/api';
import { setSessionDoctor, setSessionShift, getSessionDoctor } from '../../lib/session';
import { startShift } from '../../lib/api';
import { Doctor } from '../../types';

export default function DoctorLoginPage() {
  const router = useRouter();
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [selected, setSelected] = useState<Doctor | null>(null);
  const [ward, setWard] = useState('');
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const existing = getSessionDoctor();
    if (existing) {
      router.replace('/doctor/scribe');
      return;
    }
    getDoctors()
      .then(({ doctors }) => setDoctors(doctors))
      .catch(() => setError('Could not load doctors. Is the backend running?'))
      .finally(() => setLoading(false));
  }, [router]);

  async function handleStart() {
    if (!selected) return;
    setStarting(true);
    setError('');
    try {
      const shift = await startShift(selected.doctor_id, ward || selected.ward);
      setSessionDoctor({ ...selected, ward: ward || selected.ward });
      setSessionShift({ shift_id: shift.shift_id, started_at: shift.started_at, ward: ward || selected.ward });
      router.push('/doctor/scribe');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to start shift');
      setStarting(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 bg-[#F8FAFC]">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-3">
            <div className="w-8 h-8 bg-[#0066CC] rounded-lg flex items-center justify-center">
              <span className="text-white text-sm font-bold">A</span>
            </div>
            <span className="text-xl font-bold text-gray-900">AidCare</span>
            <span className="text-xl font-light text-[#0066CC]">Copilot</span>
          </div>
          <p className="text-gray-500 text-sm">AI cognitive shield for doctors</p>
        </div>

        <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
          <h1 className="text-lg font-semibold text-gray-900 mb-1">Good morning, Doctor.</h1>
          <p className="text-sm text-gray-500 mb-5">Select your profile to begin your shift.</p>

          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="w-6 h-6 border-2 border-[#0066CC] border-t-transparent rounded-full spinner" />
            </div>
          ) : (
            <>
              <div className="space-y-2 mb-4">
                {doctors.filter(d => d.role === 'doctor').map(doc => (
                  <button
                    key={doc.doctor_id}
                    onClick={() => { setSelected(doc); setWard(doc.ward); }}
                    className={`w-full text-left p-3 rounded-xl border transition-all ${
                      selected?.doctor_id === doc.doctor_id
                        ? 'border-[#0066CC] bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                    }`}
                  >
                    <div className="font-medium text-gray-900 text-sm">{doc.name}</div>
                    <div className="text-xs text-gray-500 mt-0.5">{doc.specialty} · {doc.ward}</div>
                  </button>
                ))}
              </div>

              {selected && (
                <div className="mb-4">
                  <label className="text-xs font-medium text-gray-600 block mb-1">Ward (confirm or update)</label>
                  <input
                    type="text"
                    value={ward}
                    onChange={e => setWard(e.target.value)}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#0066CC]"
                    placeholder="e.g. Ward C, A&E, ICU"
                  />
                </div>
              )}

              {error && <p className="text-red-600 text-xs mb-3">{error}</p>}

              <button
                onClick={handleStart}
                disabled={!selected || starting}
                className="w-full bg-[#0066CC] text-white py-3 rounded-xl font-medium text-sm disabled:opacity-40 disabled:cursor-not-allowed hover:bg-[#0052a3] transition-colors"
              >
                {starting ? 'Starting shift...' : 'Start Shift →'}
              </button>
            </>
          )}
        </div>

        <div className="text-center mt-4">
          <button
            onClick={() => router.push('/admin')}
            className="text-sm text-gray-500 hover:text-[#0066CC] transition-colors"
          >
            I&apos;m an administrator →
          </button>
        </div>
      </div>
    </div>
  );
}

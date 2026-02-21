import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'AidCare Copilot',
  description: 'AI cognitive shield for Nigerian doctors. Auto-scribe, smart handovers, burnout prevention.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}

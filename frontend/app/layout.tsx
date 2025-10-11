import type { Metadata } from 'next';
import './globals.css';
import { Navigation } from '../components/Navigation';

export const metadata: Metadata = {
  title: 'Yog Financial 前端控制台',
  description: '财务自动化结算系统的最小前端界面'
};

export default function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen">
        <div className="mx-auto flex min-h-screen max-w-6xl flex-col p-6">
          <Navigation />
          <main className="mt-6 flex-1 rounded-lg bg-white p-6 shadow-sm">{children}</main>
          <footer className="mt-8 text-center text-sm text-slate-500">
            Yog Financial · 财务自动化结算系统 MVP
          </footer>
        </div>
      </body>
    </html>
  );
}

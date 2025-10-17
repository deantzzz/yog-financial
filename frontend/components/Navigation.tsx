'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const links = [
  { href: '/', label: '流程中心' },
  { href: '/facts', label: '事实浏览' },
  { href: '/policy', label: '口径快照' },
  { href: '/upload', label: '文件任务' },
  { href: '/calc', label: '计算结果' }
];

export function Navigation() {
  const pathname = usePathname();

  return (
    <nav className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white/90 p-4 shadow-sm backdrop-blur">
      <div className="flex flex-col">
        <span className="text-lg font-semibold text-primary">Yog Financial 控制台</span>
        <span className="text-xs text-slate-500">按流程推进上传、审查与计薪</span>
      </div>
      <ul className="flex flex-wrap items-center gap-2 text-sm">
        {links.map((link) => {
          const active = pathname === link.href || pathname.startsWith(`${link.href}/`);
          return (
            <li key={link.href}>
              <Link
                href={link.href}
                className={`rounded-full px-3 py-2 transition-colors ${
                  active ? 'bg-primary text-white shadow' : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                {link.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

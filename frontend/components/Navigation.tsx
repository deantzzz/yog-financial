'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const links = [
  { href: '/', label: '概览' },
  { href: '/upload', label: '文件上传' },
  { href: '/facts', label: '事实数据' },
  { href: '/policy', label: '口径快照' },
  { href: '/calc', label: '计算与导出' }
];

export function Navigation() {
  const pathname = usePathname();

  return (
    <nav className="flex flex-wrap items-center justify-between gap-4 rounded-lg bg-white p-4 shadow-sm">
      <div className="text-lg font-semibold text-primary">Yog Financial Console</div>
      <ul className="flex flex-wrap items-center gap-2 text-sm">
        {links.map((link) => {
          const active = pathname === link.href;
          return (
            <li key={link.href}>
              <Link
                href={link.href}
                className={`rounded-md px-3 py-2 transition-colors ${active ? 'bg-primary text-white' : 'text-slate-600 hover:bg-slate-100'}`}
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

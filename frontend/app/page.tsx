import Link from 'next/link';

const cards = [
  {
    title: '1. 上传与任务',
    description: '上传原始工时、工资表、名册等文件，查看解析状态并重试失败任务。',
    href: '/upload'
  },
  {
    title: '2. 事实数据浏览',
    description: '按人、指标过滤事实层记录，高亮低置信度条目并准备人工修正。',
    href: '/facts'
  },
  {
    title: '3. 口径快照',
    description: '检视每位员工当前生效的薪资口径、社保与个税参数。',
    href: '/policy'
  },
  {
    title: '4. 计算与导出',
    description: '触发工资计算，下载银行报盘与税局导入文件。',
    href: '/calc'
  }
];

export default function Home() {
  return (
    <section className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold text-slate-800">财务自动化结算系统控制台</h1>
        <p className="text-sm text-slate-600">
          该前端提供最小可用界面，用于演示如何与后端 FastAPI 服务交互。
        </p>
      </header>
      <div className="grid gap-4 sm:grid-cols-2">
        {cards.map((card) => (
          <Link key={card.href} href={card.href} className="group rounded-lg border border-slate-200 bg-slate-50 p-4 transition hover:border-primary">
            <h2 className="text-lg font-medium text-slate-800 group-hover:text-primary">{card.title}</h2>
            <p className="mt-2 text-sm text-slate-600">{card.description}</p>
            <span className="mt-4 inline-block text-sm text-primary">进入 →</span>
          </Link>
        ))}
      </div>
    </section>
  );
}

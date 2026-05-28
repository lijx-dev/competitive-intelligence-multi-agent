import { useMemo, useState } from 'react';
import {
  Activity,
  BookOpen,
  Home,
  LogOut,
  MessageCircle,
  PanelLeft,
  Play,
} from 'lucide-react';
import { api } from '../../api/client.js';
import { SystemDashboard } from '../../pages/SystemDashboard.jsx';
import { AgentWorkspace } from '../../pages/AgentWorkspace.jsx';
import { KnowledgeBasePage } from '../../pages/KnowledgeBasePage.jsx';
import { TraceabilityPage } from '../../pages/TraceabilityPage.jsx';
import { FeishuIntegrationPage } from '../../pages/FeishuIntegrationPage.jsx';

const pages = [
  { id: 'dashboard', label: '总览', desc: '系统状态与业务闭环', icon: Home, component: SystemDashboard },
  { id: 'workspace', label: '智能体工作台', desc: '发起竞品分析任务', icon: Play, component: AgentWorkspace },
  { id: 'knowledge', label: '知识库', desc: '竞品、报告、结构化沉淀', icon: BookOpen, component: KnowledgeBasePage },
  { id: 'trace', label: '可观测溯源', desc: '日志、任务图、调用用量', icon: Activity, component: TraceabilityPage },
  { id: 'feishu', label: '飞书闭环', desc: '推送测试与人工反馈', icon: MessageCircle, component: FeishuIntegrationPage },
];

export function SystemShell({ user, onLogout }) {
  const [activePage, setActivePage] = useState('dashboard');
  const [visitedPages, setVisitedPages] = useState(() => new Set(['dashboard']));
  const page = useMemo(() => pages.find((item) => item.id === activePage) || pages[0], [activePage]);

  const activatePage = (pageId) => {
    setActivePage(pageId);
    setVisitedPages((prev) => {
      if (prev.has(pageId)) return prev;
      const next = new Set(prev);
      next.add(pageId);
      return next;
    });
  };

  return (
    <main className="system-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span>竞智</span>
          <small>智能分析系统</small>
        </div>

        <nav className="side-nav" aria-label="系统导航">
          {pages.map((item) => {
            const Icon = item.icon;
            return (
              <button
                className={item.id === activePage ? 'active' : ''}
                key={item.id}
                type="button"
                onClick={() => activatePage(item.id)}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </aside>

      <section className="system-main">
        <header className="topbar">
          <div className="topbar-title">
            <PanelLeft size={20} />
            <div>
              <h1>{page.label}</h1>
              <p>{page.desc}</p>
            </div>
          </div>
          <div className="topbar-actions">
            <div className="user-chip">
              <strong>{user.name}</strong>
              <span>{user.role}</span>
            </div>
            <button className="ghost-button" type="button" onClick={onLogout}>
              <LogOut size={17} />
              退出
            </button>
          </div>
        </header>

        <div className="system-page-stack">
          {pages.map((item) => {
            if (!visitedPages.has(item.id)) return null;
            const PageComponent = item.component;
            return (
              <div
                className={`system-page ${item.id === activePage ? 'active' : ''}`}
                key={item.id}
                aria-hidden={item.id !== activePage}
              >
                <PageComponent />
              </div>
            );
          })}
        </div>
      </section>
    </main>
  );
}

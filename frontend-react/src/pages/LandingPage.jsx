import { useEffect, useRef, useState } from 'react';
import {
  ArrowRight,
  BarChart3,
  Bot,
  Brain,
  CheckCircle2,
  ChevronRight,
  Eye,
  EyeOff,
  FileSearch,
  Globe,
  Layers,
  Loader2,
  Lock,
  Mail,
  MessageSquare,
  Network,
  Search,
  ShieldCheck,
  Sparkles,
  Target,
  User,
  Workflow,
  Zap,
} from 'lucide-react';
import { api } from '../api/client.js';

/* ─────────────────────────────────────────────
   Hero 动态粒子背景
   ───────────────────────────────────────────── */
function ParticleBg() {
  const canvasRef = useRef(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let raf;
    let particles = [];
    const resize = () => {
      canvas.width = canvas.offsetWidth * devicePixelRatio;
      canvas.height = canvas.offsetHeight * devicePixelRatio;
      ctx.scale(devicePixelRatio, devicePixelRatio);
    };
    resize();
    window.addEventListener('resize', resize);

    for (let i = 0; i < 60; i++) {
      particles.push({
        x: Math.random() * canvas.offsetWidth,
        y: Math.random() * canvas.offsetHeight,
        r: Math.random() * 2 + 0.5,
        dx: (Math.random() - 0.5) * 0.4,
        dy: (Math.random() - 0.5) * 0.4,
        o: Math.random() * 0.5 + 0.1,
      });
    }

    const draw = () => {
      ctx.clearRect(0, 0, canvas.offsetWidth, canvas.offsetHeight);
      for (const p of particles) {
        p.x += p.dx;
        p.y += p.dy;
        if (p.x < 0 || p.x > canvas.offsetWidth) p.dx *= -1;
        if (p.y < 0 || p.y > canvas.offsetHeight) p.dy *= -1;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(99,144,255,${p.o})`;
        ctx.fill();
      }
      // 连线
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 120) {
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.strokeStyle = `rgba(99,144,255,${0.08 * (1 - dist / 120)})`;
            ctx.stroke();
          }
        }
      }
      raf = requestAnimationFrame(draw);
    };
    draw();
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', resize); };
  }, []);
  return <canvas ref={canvasRef} className="lp-particles" />;
}

/* ─────────────────────────────────────────────
   Intersection Observer 动画
   ───────────────────────────────────────────── */
function useFadeIn() {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) { el.classList.add('visible'); obs.disconnect(); }
    }, { threshold: 0.15 });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  return ref;
}

function FadeIn({ children, className = '', delay = 0 }) {
  const ref = useFadeIn();
  return (
    <div ref={ref} className={`fade-in-section ${className}`} style={{ transitionDelay: `${delay}ms` }}>
      {children}
    </div>
  );
}

/* ─────────────────────────────────────────────
   数据定义
   ───────────────────────────────────────────── */
const capabilities = [
  { icon: Network, title: '11 智能体协作', text: '监控·研究·调研·验证·对比·报告·质检·溯源·推送，全链路自动化编排', accent: '#3b82f6', bg: 'rgba(59,130,246,0.08)' },
  { icon: Brain, title: '豆包大模型驱动', text: '基于 Doubao-Seed-2.0-lite 深度推理，每个 Agent 独立 Prompt 策略', accent: '#8b5cf6', bg: 'rgba(139,92,246,0.08)' },
  { icon: Eye, title: '来源可追溯', text: '每条结论标注信息来源 URL，交叉验证置信度评分，杜绝 AI 幻觉', accent: '#10b981', bg: 'rgba(16,185,129,0.08)' },
  { icon: Target, title: '质量自修复', text: 'ReviewerAgent 评分 < 7 自动打回，Reflexion 循环定向修复至达标', accent: '#f59e0b', bg: 'rgba(245,158,11,0.08)' },
  { icon: BarChart3, title: '8 维度竞品矩阵', text: '产品·定价·用户·技术·市场·口碑·生态·服务，量化评分对比', accent: '#ec4899', bg: 'rgba(236,72,153,0.08)' },
  { icon: MessageSquare, title: '飞书闭环反馈', text: '报告卡片一键推送飞书群，团队在线反馈驱动 Agent 进化学习', accent: '#06b6d4', bg: 'rgba(6,182,212,0.08)' },
];

const dagFlow = [
  { id: 'monitor', label: '监控采集', icon: Search, module: '采集' },
  { id: 'alert', label: '变更告警', icon: Zap, module: '推送' },
  { id: 'research', label: '深度研究', icon: FileSearch, module: '采集' },
  { id: 'survey', label: '用户调研', icon: Bot, module: '采集' },
  { id: 'fact_check', label: '交叉验证', icon: ShieldCheck, module: '质量' },
  { id: 'compare', label: '对比分析', icon: BarChart3, module: '分析' },
  { id: 'battlecard', label: '对战卡', icon: Target, module: '报告' },
  { id: 'reviewer', label: '质量审查', icon: CheckCircle2, module: '质量' },
  { id: 'targeted_fix', label: '定向修复', icon: Workflow, module: '质量' },
  { id: 'citation', label: '来源溯源', icon: Globe, module: '质量' },
  { id: 'feishu', label: '飞书推送', icon: MessageSquare, module: '推送' },
];

const moduleColors = { '采集': '#3b82f6', '分析': '#10b981', '报告': '#8b5cf6', '质量': '#f59e0b', '推送': '#6b7280' };

const stats = [
  { number: '11', label: '专职智能体', suffix: '' },
  { number: '8', label: '对比维度', suffix: '' },
  { number: '100', label: '结论可溯源', suffix: '%' },
  { number: '3', label: '分钟出报告', suffix: 'min' },
];

const techStack = [
  { title: 'React 19 + Vite 7', desc: 'SSE 实时流式渲染\nDAG 状态可视化\n结构化结果卡片', tags: ['TypeScript', 'SSE Stream', 'CSS Grid'] },
  { title: 'FastAPI + LangGraph', desc: '12 节点 StateGraph 编排\n条件分支 + Reflexion 循环\n48 个 REST 端点', tags: ['Python', 'DAG', 'SQLite'] },
  { title: 'Doubao-Seed-2.0-lite', desc: '字节跳动豆包大模型\n结构化 JSON 输出\nToken 用量追踪审计', tags: ['LLM', 'Prompt', 'JSON Mode'] },
  { title: '全链路质量保障', desc: '4 维度评分体系\n交叉验证 + 来源溯源\nReflexion 自修复循环', tags: ['QA', 'Citation', 'Reflexion'] },
];

const useCases = [
  { title: '输入竞品名称', desc: '例如"快手电商"，自动采集公开信息', step: '01' },
  { title: 'Agent 协作分析', desc: '9个专业Agent + 3个功能节点（共12节点）协同执行，实时可视化进度', step: '02' },
  { title: '结构化报告输出', desc: '对比矩阵、对战卡、用户调研、来源验证', step: '03' },
  { title: '团队闭环反馈', desc: '飞书推送 → 人工确认/纠正 → 进化引擎学习', step: '04' },
];

const sceneImages = [
  {
    src: 'https://images.unsplash.com/photo-1552664730-d307ca884978?auto=format&fit=crop&w=1100&q=88',
    title: '市场团队研判',
    desc: '多角色共读竞品信号',
  },
  {
    src: 'https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=1100&q=88',
    title: '数据情报看板',
    desc: '指标、趋势和异常归因',
  },
  {
    src: 'https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1100&q=88',
    title: '增长与商业分析',
    desc: '拆解竞品策略变化',
  },
  {
    src: 'https://images.unsplash.com/photo-1556761175-b413da4baf72?auto=format&fit=crop&w=1100&q=88',
    title: '团队复盘协作',
    desc: '把分析结论转成行动',
  },
  {
    src: 'https://images.unsplash.com/photo-1542744173-8e7e53415bb0?auto=format&fit=crop&w=1100&q=88',
    title: '战略会议',
    desc: '围绕竞品报告形成决策',
  },
];

/* ─────────────────────────────────────────────
   计数动画 Hook
   ───────────────────────────────────────────── */
function AnimatedNumber({ value, suffix = '' }) {
  const [display, setDisplay] = useState(0);
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) {
        const target = parseInt(value, 10);
        let current = 0;
        const step = Math.max(1, Math.ceil(target / 30));
        const timer = setInterval(() => {
          current += step;
          if (current >= target) { current = target; clearInterval(timer); }
          setDisplay(current);
        }, 40);
        obs.disconnect();
      }
    }, { threshold: 0.5 });
    obs.observe(el);
    return () => obs.disconnect();
  }, [value]);
  return <span ref={ref}>{display}{suffix}</span>;
}

/* ══════════════════════════════════════════════
   主组件
   ══════════════════════════════════════════════ */

export function LandingPage({ onAuthenticated }) {
  const [view, setView] = useState('landing');

  if (view === 'login' || view === 'register') {
    return (
      <AuthScreen
        mode={view}
        onToggleMode={() => setView(view === 'login' ? 'register' : 'login')}
        onBack={() => setView('landing')}
        onAuthenticated={onAuthenticated}
      />
    );
  }

  return (
    <main className="lp">
      {/* ── 导航 ── */}
      <header className="lp-nav">
        <div className="lp-nav-inner">
          <a className="lp-brand" href="#top">
            <div className="lp-brand-icon"><Zap size={18} /></div>
            <span>竞智 CI</span>
          </a>
          <nav className="lp-links">
            <a href="#capabilities">核心能力</a>
            <a href="#workflow">协作流程</a>
            <a href="#tech">技术架构</a>
          </nav>
          <div className="lp-nav-actions">
            <button className="lp-btn-ghost" type="button" onClick={() => setView('login')}>登录</button>
            <button className="lp-btn-primary" type="button" onClick={() => setView('register')}>
              免费体验
              <ArrowRight size={15} />
            </button>
          </div>
        </div>
      </header>

      {/* ── Hero ── */}
      <section className="lp-hero" id="top">
        <ParticleBg />
        <div className="lp-hero-glow lp-hero-glow--1" />
        <div className="lp-hero-glow lp-hero-glow--2" />
        <div className="lp-hero-glow lp-hero-glow--3" />
        <div className="lp-scene-collage" aria-hidden="true">
          {sceneImages.map((image, index) => (
            <span
              className={`lp-scene-photo lp-scene-photo--${index + 1}`}
              key={image.src}
              style={{ backgroundImage: `url(${image.src})` }}
            />
          ))}
        </div>

        <div className="lp-hero-content">
          <div className="lp-hero-badge">
            <Sparkles size={14} />
            2026 字节跳动青训营 · AI 全栈赛道 · Agent Track
          </div>
          <h1 className="lp-hero-title">
            <span className="lp-gradient-text">AI 多智能体</span>
            <br />
            竞品情报分析系统
          </h1>
          <p className="lp-hero-desc">
            9个专业AI Agent + 3个功能辅助节点（共12节点）协同工作，自动完成竞品监控、深度研究、用户调研、
            对比分析、报告生成与质量审查 —— 每条结论可追溯、可验证
          </p>
          <div className="lp-hero-actions">
            <button className="lp-btn-hero" type="button" onClick={() => setView('register')}>
              <span>开始使用</span>
              <ArrowRight size={16} />
            </button>
            <button className="lp-btn-hero-outline" type="button" onClick={() => setView('login')}>
              已有账号，直接登录
            </button>
          </div>
        </div>

        <div className="lp-scene-strip" aria-label="竞品分析业务场景">
          {sceneImages.slice(0, 3).map((image) => (
            <figure key={image.title}>
              <img src={image.src} alt={image.title} />
              <figcaption>
                <strong>{image.title}</strong>
                <span>{image.desc}</span>
              </figcaption>
            </figure>
          ))}
        </div>
      </section>

      {/* ── 数据指标 ── */}
      <section className="lp-stats-bar">
        <div className="lp-stats-inner">
          {stats.map((s) => (
            <div className="lp-stat" key={s.label}>
              <strong><AnimatedNumber value={s.number} suffix={s.suffix} /></strong>
              <span>{s.label}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ── 能力矩阵 ── */}
      <section className="lp-section" id="capabilities">
        <FadeIn>
          <div className="lp-section-header">
            <span className="lp-kicker">核心能力</span>
            <h2>端到端的竞品情报自动化</h2>
            <p>从信息采集到报告输出，每一步都由专职 Agent 负责，结果结构化、可追溯、可验证</p>
          </div>
        </FadeIn>
        <div className="lp-cap-grid">
          {capabilities.map((item, i) => {
            const Icon = item.icon;
            return (
              <FadeIn delay={i * 80} key={item.title}>
                <article className="lp-cap-card">
                  <div className="lp-cap-icon" style={{ background: item.bg, color: item.accent }}>
                    <Icon size={22} />
                  </div>
                  <h3>{item.title}</h3>
                  <p>{item.text}</p>
                  <div className="lp-cap-arrow">
                    <ChevronRight size={16} />
                  </div>
                </article>
              </FadeIn>
            );
          })}
        </div>
      </section>

      {/* ── 使用流程 ── */}
      <section className="lp-section lp-section--dark" id="workflow">
        <FadeIn>
          <div className="lp-section-header">
            <span className="lp-kicker">使用流程</span>
            <h2>4 步完成竞品深度分析</h2>
            <p>输入名称 → Agent 协作 → 结构化报告 → 团队闭环</p>
          </div>
        </FadeIn>
        <div className="lp-steps-grid">
          {useCases.map((uc, i) => (
            <FadeIn delay={i * 100} key={uc.step}>
              <div className="lp-step-card">
                <span className="lp-step-num">{uc.step}</span>
                <h3>{uc.title}</h3>
                <p>{uc.desc}</p>
              </div>
            </FadeIn>
          ))}
        </div>
      </section>

      {/* ── DAG 拓扑 ── */}
      <section className="lp-section">
        <FadeIn>
          <div className="lp-section-header">
            <span className="lp-kicker">多智能体协作</span>
            <h2>LangGraph DAG — 11 节点编排</h2>
            <p>基于有向无环图的状态机，支持条件分支、并行执行和 Reflexion 自修复循环</p>
          </div>
        </FadeIn>
        <FadeIn>
          <div className="lp-dag-wrapper">
            {dagFlow.map((node, i) => {
              const Icon = node.icon;
              return (
                <div className="lp-dag-node" key={node.id}>
                  <div className="lp-dag-node-inner" style={{ '--node-color': moduleColors[node.module] }}>
                    <Icon size={16} />
                    <span>{node.label}</span>
                  </div>
                  {i < dagFlow.length - 1 && <div className="lp-dag-arrow"><ChevronRight size={14} /></div>}
                </div>
              );
            })}
          </div>
        </FadeIn>
      </section>

      {/* ── 技术架构 ── */}
      <section className="lp-section lp-section--alt" id="tech">
        <FadeIn>
          <div className="lp-section-header">
            <span className="lp-kicker">技术架构</span>
            <h2>全栈工程化实现</h2>
          </div>
        </FadeIn>
        <div className="lp-tech-grid">
          {techStack.map((item, i) => (
            <FadeIn delay={i * 100} key={item.title}>
              <div className="lp-tech-card">
                <h4>{item.title}</h4>
                <p>{item.desc}</p>
                <div className="lp-tech-tags">
                  {item.tags.map((t) => <span key={t}>{t}</span>)}
                </div>
              </div>
            </FadeIn>
          ))}
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="lp-cta">
        <div className="lp-cta-inner">
          <FadeIn>
            <h2>准备好开始你的 AI 竞品情报分析了吗？</h2>
            <p>输入竞品名称，多智能体立即开启信息采集、趋势研判、对比矩阵和结构化报告生成。</p>
            <div className="lp-cta-actions">
              <button className="lp-btn-hero" type="button" onClick={() => setView('register')}>
                <span>立即体验</span>
                <ArrowRight size={16} />
              </button>
            </div>
          </FadeIn>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="lp-footer">
        <div className="lp-footer-inner">
          <div className="lp-brand" style={{ color: 'rgba(255,255,255,0.7)' }}>
            <div className="lp-brand-icon"><Zap size={16} /></div>
            <span>竞智 CI</span>
          </div>
          <span>2026 字节跳动青训营 · AI 全栈赛道</span>
        </div>
      </footer>
    </main>
  );
}

/* ══════════════════════════════════════════════
   登录 / 注册 — 全屏双栏布局
   ══════════════════════════════════════════════ */

function AuthScreen({ mode, onToggleMode, onBack, onAuthenticated }) {
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState({ name: '', email: '', password: '' });

  const isRegister = mode === 'register';

  const update = (field, value) => {
    setForm((f) => ({ ...f, [field]: value }));
    setError('');
  };

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const payload = isRegister
        ? { name: form.name.trim(), email: form.email.trim(), password: form.password, role: '用户' }
        : { email: form.email.trim(), password: form.password };
      const result = isRegister ? await api.register(payload) : await api.login(payload);
      onAuthenticated(result);
    } catch (err) {
      setError(err.message || '请求失败，请检查网络连接');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="auth-screen">
      <div className="auth-brand-side">
        <div className="auth-brand-content">
          <div className="lp-brand" style={{ color: '#fff' }}>
            <div className="lp-brand-icon"><Zap size={18} /></div>
            <span>竞智 CI</span>
          </div>
          <h1>AI 多智能体<br />竞品情报分析系统</h1>
          <p>9个专业AI Agent + 3个功能辅助节点（共12节点）协同工作，从信息采集到结构化报告全流程自动化。</p>
          <div className="auth-brand-features">
            <div><CheckCircle2 size={16} /> 12 节点 DAG 实时编排</div>
            <div><CheckCircle2 size={16} /> 每条结论可追溯可验证</div>
            <div><CheckCircle2 size={16} /> Reflexion 质量自修复</div>
            <div><CheckCircle2 size={16} /> 飞书推送闭环反馈</div>
          </div>
        </div>
      </div>

      <div className="auth-form-side">
        <div className="auth-form-wrapper">
          <button className="auth-back-btn" type="button" onClick={onBack}>
            <ArrowRight size={16} style={{ transform: 'rotate(180deg)' }} />
            返回首页
          </button>
          <div className="auth-form-header">
            <h2>{isRegister ? '创建账号' : '欢迎回来'}</h2>
            <p>{isRegister ? '注册后即可发起 AI 竞品分析' : '登录继续你的竞品分析工作'}</p>
          </div>
          <form className="auth-form-body" onSubmit={submit}>
            {isRegister && (
              <div className="auth-field">
                <label htmlFor="auth-name">姓名</label>
                <div className="auth-input-wrap">
                  <User size={16} />
                  <input id="auth-name" autoComplete="name" required value={form.name} onChange={(e) => update('name', e.target.value)} placeholder="输入你的姓名" />
                </div>
              </div>
            )}
            <div className="auth-field">
              <label htmlFor="auth-email">邮箱</label>
              <div className="auth-input-wrap">
                <Mail size={16} />
                <input id="auth-email" autoComplete="email" required type="email" value={form.email} onChange={(e) => update('email', e.target.value)} placeholder="name@example.com" />
              </div>
            </div>
            <div className="auth-field">
              <label htmlFor="auth-pw">密码</label>
              <div className="auth-input-wrap">
                <Lock size={16} />
                <input id="auth-pw" autoComplete={isRegister ? 'new-password' : 'current-password'} minLength={6} required type={showPassword ? 'text' : 'password'} value={form.password} onChange={(e) => update('password', e.target.value)} placeholder="至少 6 位" />
                <button className="auth-eye" type="button" onClick={() => setShowPassword((v) => !v)} tabIndex={-1}>
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>
            {error && <p className="auth-error">{error}</p>}
            <button className="lp-btn-primary auth-submit" type="submit" disabled={loading}>
              {loading && <Loader2 className="spin" size={16} />}
              {isRegister ? '注册' : '登录'}
            </button>
            <p className="auth-switch">
              {isRegister ? '已有账号？' : '还没有账号？'}
              <button type="button" onClick={onToggleMode}>
                {isRegister ? '去登录' : '注册新账号'}
              </button>
            </p>
          </form>
        </div>
      </div>
    </main>
  );
}

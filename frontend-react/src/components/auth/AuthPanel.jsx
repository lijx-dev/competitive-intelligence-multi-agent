import { useState } from 'react';
import { Eye, EyeOff, Loader2, Lock, Mail, User, UserPlus } from 'lucide-react';
import { api } from '../../api/client.js';

export function AuthPanel({ initialMode = 'login', onAuthenticated }) {
  const [mode, setMode] = useState(initialMode);
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState({
    name: '',
    email: '',
    password: '',
    role: '分析师',
  });

  const isRegister = mode === 'register';

  const updateField = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }));
    setError('');
  };

  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError('');
    try {
      const payload = isRegister
        ? {
            name: form.name.trim(),
            email: form.email.trim(),
            password: form.password,
            role: form.role,
          }
        : {
            email: form.email.trim(),
            password: form.password,
          };
      const result = isRegister ? await api.register(payload) : await api.login(payload);
      onAuthenticated(result);
    } catch (err) {
      setError(err.message || '请求失败，请检查后端服务');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="auth-panel" aria-label="用户认证">
      <div className="auth-tabs">
        <button
          className={mode === 'login' ? 'active' : ''}
          type="button"
          onClick={() => setMode('login')}
        >
          登录
        </button>
        <button
          className={mode === 'register' ? 'active' : ''}
          type="button"
          onClick={() => setMode('register')}
        >
          注册
        </button>
      </div>

      <div className="auth-heading">
        <UserPlus size={22} />
        <div>
          <h2>{isRegister ? '创建分析账号' : '进入系统工作台'}</h2>
          <p>{isRegister ? '注册后即可发起智能体竞品分析' : '使用已注册邮箱继续工作'}</p>
        </div>
      </div>

      <form className="auth-form" onSubmit={submit}>
        {isRegister && (
          <label>
            <span>姓名</span>
            <div className="input-shell">
              <User size={18} />
              <input
                autoComplete="name"
                minLength={1}
                required
                value={form.name}
                onChange={(event) => updateField('name', event.target.value)}
                placeholder="请输入姓名"
              />
            </div>
          </label>
        )}

        <label>
          <span>邮箱</span>
          <div className="input-shell">
            <Mail size={18} />
            <input
              autoComplete="email"
              minLength={3}
              required
              type="email"
              value={form.email}
              onChange={(event) => updateField('email', event.target.value)}
              placeholder="name@company.com"
            />
          </div>
        </label>

        <label>
          <span>密码</span>
          <div className="input-shell">
            <Lock size={18} />
            <input
              autoComplete={isRegister ? 'new-password' : 'current-password'}
              minLength={6}
              required
              type={showPassword ? 'text' : 'password'}
              value={form.password}
              onChange={(event) => updateField('password', event.target.value)}
              placeholder="至少 6 位"
            />
            <button
              className="icon-button"
              type="button"
              onClick={() => setShowPassword((value) => !value)}
              aria-label={showPassword ? '隐藏密码' : '显示密码'}
            >
              {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>
        </label>

        {isRegister && (
          <label>
            <span>角色</span>
            <select value={form.role} onChange={(event) => updateField('role', event.target.value)}>
              <option value="分析师">分析师</option>
              <option value="产品经理">产品经理</option>
              <option value="质检负责人">质检负责人</option>
              <option value="管理员">管理员</option>
            </select>
          </label>
        )}

        {error && <p className="form-error">{error}</p>}

        <button className="primary-button full" type="submit" disabled={loading}>
          {loading ? <Loader2 className="spin" size={18} /> : <UserPlus size={18} />}
          {isRegister ? '注册并进入系统' : '登录系统'}
        </button>
      </form>
    </section>
  );
}

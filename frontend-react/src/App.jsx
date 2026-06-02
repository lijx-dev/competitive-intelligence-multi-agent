import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { LandingPage } from './pages/LandingPage.jsx';
import { SystemShell } from './components/system/SystemShell.jsx';
import { autoDemoAuth, clearAuth, getStoredToken, getStoredUser, saveAuth } from './api/client.js';

export default function App() {
  const [ready, setReady] = useState(false);
  const [session, setSession] = useState(() => ({
    token: getStoredToken(),
    user: getStoredUser(),
  }));

  useEffect(() => {
    // ★ 零点击自动免登录演示模式：页面加载立刻自动注入演示token，完全跳过登录注册
    let token = getStoredToken();
    if (!token || !getStoredUser()) {
      // 没有现有会话，自动生成演示会话
      const demo = autoDemoAuth();
      setSession({ token: demo.token, user: demo.user });
    } else {
      // 已有会话，直接复用
      setSession({ token, user: getStoredUser() });
    }
    // 绝对不调用任何后端/auth接口，前端完全本地鉴权
    setReady(true);
  }, []);

  const handleAuthenticated = ({ token, user }) => {
    saveAuth(token, user);
    setSession({ token, user });
  };

  const handleLogout = () => {
    clearAuth();
    setSession({ token: '', user: null });
  };

  if (!ready) {
    return (
      <main className="boot-screen">
        <Loader2 className="spin" size={28} />
        <span>正在启动竞品分析系统</span>
      </main>
    );
  }

  // ★ 完全跳过登录页，直接进系统，零跳转零白屏
  // if (!session.token || !session.user) {
  //   return <LandingPage onAuthenticated={handleAuthenticated} />;
  // }

  return <SystemShell user={session.user} onLogout={handleLogout} />;
}

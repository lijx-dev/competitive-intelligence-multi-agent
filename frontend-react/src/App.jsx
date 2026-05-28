import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { LandingPage } from './pages/LandingPage.jsx';
import { SystemShell } from './components/system/SystemShell.jsx';
import { api, clearAuth, getStoredToken, getStoredUser, saveAuth } from './api/client.js';

export default function App() {
  const [ready, setReady] = useState(false);
  const [session, setSession] = useState(() => ({
    token: getStoredToken(),
    user: getStoredUser(),
  }));

  useEffect(() => {
    const token = getStoredToken();
    if (!token) {
      setReady(true);
      return;
    }

    api
      .me(token)
      .then((payload) => {
        const user = payload?.user;
        if (user) {
          saveAuth(token, user);
          setSession({ token, user });
        } else {
          clearAuth();
          setSession({ token: '', user: null });
        }
      })
      .catch(() => {
        clearAuth();
        setSession({ token: '', user: null });
      })
      .finally(() => setReady(true));
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
        <span>正在连接竞品分析系统</span>
      </main>
    );
  }

  if (!session.token || !session.user) {
    return <LandingPage onAuthenticated={handleAuthenticated} />;
  }

  return <SystemShell user={session.user} onLogout={handleLogout} />;
}

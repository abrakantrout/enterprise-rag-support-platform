import React, { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { 
  LayoutDashboard, 
  FileText, 
  MessageSquare, 
  LogOut, 
  Shield,
  Activity,
  Globe
} from 'lucide-react';
import { api } from '../api/client';
import type { UserProfile } from '../api/client';

interface LayoutProps {
  children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isOnline, setIsOnline] = useState<boolean>(true);

  useEffect(() => {
    const storedUser = localStorage.getItem('current_user');
    if (storedUser) {
      setUser(JSON.parse(storedUser));
    } else {
      navigate('/login');
    }

    const checkStatus = async () => {
      const healthy = await api.checkHealth();
      setIsOnline(healthy);
    };
    checkStatus();
    const interval = setInterval(checkStatus, 15000);
    return () => clearInterval(interval);
  }, [navigate]);

  const handleSignOut = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('current_user');
    navigate('/login');
  };

  const navItems = [
    { name: 'Dashboard', path: '/', icon: LayoutDashboard },
    { name: 'Documents', path: '/documents', icon: FileText },
    { name: 'Chat Console', path: '/chat', icon: MessageSquare },
  ];

  // Extract initials for the profile avatar circle
  const getInitials = () => {
    if (!user) return '??';
    return `${user.first_name.charAt(0)}${user.last_name.charAt(0)}`.toUpperCase();
  };

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden font-sans">
      {/* Dark left sidebar */}
      <aside className="w-64 bg-slate-950 text-white flex flex-col justify-between shrink-0 shadow-xl border-r border-slate-800">
        <div>
          {/* Brand Header with purple/blue gradient */}
          <div className="p-6 border-b border-slate-900">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-gradient-to-tr from-violet-600 to-indigo-600 rounded-lg shadow-md">
                <Globe className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="text-lg font-bold tracking-tight bg-gradient-to-r from-violet-400 to-indigo-400 bg-clip-text text-transparent">
                  RAG Console
                </h1>
                <p className="text-[10px] text-slate-400 font-semibold tracking-wider uppercase mt-0.5">
                  AI Knowledge Assistant
                </p>
              </div>
            </div>
          </div>

          {/* Navigation Links with purple gradient active states */}
          <nav className="p-4 space-y-1.5">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center space-x-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all duration-200 group ${
                    isActive
                      ? 'bg-gradient-to-r from-violet-600 to-indigo-600 text-white shadow-md shadow-indigo-900/30 translate-x-1'
                      : 'text-slate-400 hover:bg-slate-900 hover:text-slate-100'
                  }`}
                >
                  <Icon className={`w-4 h-4 shrink-0 transition-colors ${
                    isActive ? 'text-white' : 'text-slate-500 group-hover:text-slate-300'
                  }`} />
                  <span>{item.name}</span>
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Bottom User Card Profile info */}
        <div className="p-4 border-t border-slate-900 space-y-4 bg-slate-900/30">
          {user && (
            <div className="flex items-center space-x-3 px-2">
              <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-violet-600 to-indigo-600 flex items-center justify-center font-bold text-sm text-white shadow-inner">
                {getInitials()}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-bold text-slate-200 truncate leading-none">
                  {user.first_name} {user.last_name}
                </p>
                <p className="text-[10px] text-slate-400 truncate mt-1">
                  {user.email}
                </p>
                <div className="flex items-center space-x-1 mt-1 text-[9px] font-semibold text-violet-400 uppercase tracking-wider">
                  <Shield className="w-2.5 h-2.5" />
                  <span>{user.role}</span>
                </div>
              </div>
            </div>
          )}

          <button
            onClick={handleSignOut}
            className="w-full flex items-center justify-center space-x-2 px-4 py-2.5 bg-slate-900 hover:bg-red-950/80 border border-slate-800 hover:border-red-900 rounded-xl text-xs font-bold text-slate-400 hover:text-red-200 transition-all duration-150 cursor-pointer"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Header with Breadcrumbs & status badge */}
        <header className="h-16 bg-white border-b border-slate-200/80 flex items-center justify-between px-8 shadow-sm">
          <div className="flex items-center space-x-2 text-sm font-medium">
            <span className="text-slate-400">RAG platform</span>
            <span className="text-slate-300">/</span>
            <span className="text-slate-800 font-bold">
              {location.pathname === '/' ? 'Dashboard' : location.pathname === '/documents' ? 'Document Library' : 'Grounded Agent Chat'}
            </span>
          </div>

          {/* Connection status badge */}
          <div className="flex items-center space-x-4">
            <div className={`flex items-center space-x-1.5 px-3 py-1 rounded-full border text-xs font-semibold ${
              isOnline 
                ? 'bg-emerald-50 border-emerald-100 text-emerald-700' 
                : 'bg-rose-50 border-rose-100 text-rose-700 animate-pulse'
            }`}>
              <Activity className={`w-3.5 h-3.5 ${isOnline ? 'text-emerald-500' : 'text-rose-500'}`} />
              <span>{isOnline ? 'System Online' : 'System Disconnected'}</span>
            </div>
          </div>
        </header>

        {/* Content panel */}
        <main className="flex-1 overflow-y-auto bg-slate-50/50 p-8">
          <div className="max-w-7xl mx-auto">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
};

'use client'

import Link from 'next/link'
import { useState, useEffect } from 'react'
import { Code2, Github, Menu, X, LayoutDashboard, MessageSquare, GitBranch, Bot, LogOut } from 'lucide-react'
import { api } from '@/lib/api'

export default function Navbar() {
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const [user, setUser] = useState<any>(null)

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const userData = await api.getMe()
        setUser(userData)
      } catch (err) {
        // Not logged in or token invalid
        setUser(null)
      }
    }
    fetchUser()
  }, [])

  const handleLogout = () => {
    api.logout()
    setUser(null)
    window.location.href = '/'
  }

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 border-b border-dark-700/50 bg-dark-900/80 backdrop-blur-xl">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2 group">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary-600 group-hover:bg-primary-500 transition-colors">
              <Code2 className="h-5 w-5 text-white" />
            </div>
            <span className="text-xl font-bold text-white">
              Code<span className="text-primary-400">Weave</span>
            </span>
          </Link>

          {/* Desktop Nav */}
          <div className="hidden md:flex items-center gap-1">
            <NavLink href="/dashboard" icon={<LayoutDashboard className="h-4 w-4" />}>
              Dashboard
            </NavLink>
            <NavLink href="/chat" icon={<MessageSquare className="h-4 w-4" />}>
              Chat
            </NavLink>
            <NavLink href="/repos" icon={<GitBranch className="h-4 w-4" />}>
              Repos
            </NavLink>
            <NavLink href="/agent" icon={<Bot className="h-4 w-4" />}>
              Agent
            </NavLink>
          </div>

          {/* Actions */}
          <div className="hidden md:flex items-center gap-3">
            {user ? (
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  {user.avatar_url ? (
                    <img src={user.avatar_url} alt="Avatar" className="w-8 h-8 rounded-full border border-dark-600" />
                  ) : (
                    <div className="w-8 h-8 rounded-full bg-dark-700 border border-dark-600"></div>
                  )}
                  <span className="text-sm font-medium text-white">{user.username}</span>
                </div>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-dark-300 hover:text-red-400 hover:bg-dark-800 transition-colors"
                >
                  <LogOut className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={async () => {
                  try {
                    const res = await api.getGithubLoginUrl();
                    window.location.href = res.auth_url;
                  } catch (e) {
                    console.error('Login failed', e);
                  }
                }}
                className="flex items-center gap-2 rounded-lg border border-dark-600 px-4 py-2 text-sm text-dark-200 hover:bg-dark-800 hover:border-dark-500 transition-all"
              >
                <Github className="h-4 w-4" />
                Sign in with GitHub
              </button>
            )}
          </div>

          {/* Mobile menu button */}
          <button
            className="md:hidden p-2 text-dark-300 hover:text-white"
            onClick={() => setIsMenuOpen(!isMenuOpen)}
          >
            {isMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
          </button>
        </div>

        {/* Mobile Nav */}
        {isMenuOpen && (
          <div className="md:hidden pb-4 pt-2 space-y-1">
            <MobileNavLink href="/dashboard">Dashboard</MobileNavLink>
            <MobileNavLink href="/chat">Chat</MobileNavLink>
            <MobileNavLink href="/repos">Repositories</MobileNavLink>
          </div>
        )}
      </div>
    </nav>
  )
}

function NavLink({ href, icon, children }: { href: string; icon?: React.ReactNode; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-dark-300 hover:bg-dark-800 hover:text-white transition-all"
    >
      {icon}
      {children}
    </Link>
  )
}

function MobileNavLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="block rounded-lg px-3 py-2 text-base text-dark-300 hover:bg-dark-800 hover:text-white transition-all"
    >
      {children}
    </Link>
  )
}

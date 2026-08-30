'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import Navbar from '@/components/Navbar'
import { GitBranch, MessageSquare, Database, Cpu, ArrowRight, CheckCircle2, Loader2, Bot } from 'lucide-react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Stats {
  total_repos: number
  ready_repos: number
  total_chunks: number
  ai_status: string
  redis_status: string
  embed_status: string
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const [reposRes, healthRes] = await Promise.all([
          fetch(`${API_URL}/api/repos`),
          fetch(`${API_URL}/health`),
        ])
        const repos = await reposRes.json()
        const health = await healthRes.json()
        const repoList = repos.repositories || []
        setStats({
          total_repos: repoList.length,
          ready_repos: repoList.filter((r: any) => r.ingestion_status === 'completed').length,
          total_chunks: repoList.reduce((s: number, r: any) => s + r.total_chunks, 0),
          ai_status: health.services?.llm || 'unknown',
          redis_status: health.services?.redis || 'unknown',
          embed_status: health.services?.embeddings || 'unknown',
        })
      } catch {}
      finally { setLoading(false) }
    }
    fetchStats()
  }, [])

  return (
    <>
      <Navbar />
      <main className="pt-20 px-4 pb-12 max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-1">Dashboard</h1>
          <p className="text-dark-400 text-sm">Platform overview and quick actions</p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard
            label="Connected Repos"
            value={loading ? '...' : String(stats?.total_repos ?? 0)}
            icon={<GitBranch className="h-5 w-5" />}
            sub={`${stats?.ready_repos ?? 0} ready`}
          />
          <StatCard
            label="Indexed Chunks"
            value={loading ? '...' : (stats?.total_chunks ?? 0).toLocaleString()}
            icon={<Database className="h-5 w-5" />}
            sub="vectors stored"
          />
          <StatCard
            label="AI Status"
            value={stats?.ai_status === 'configured' ? 'Online' : 'Not set'}
            icon={<Cpu className="h-5 w-5" />}
            sub={stats?.ai_status || '—'}
            highlight={stats?.ai_status === 'configured'}
          />
          <StatCard
            label="Embeddings"
            value={stats?.embed_status === 'ok' ? 'Ready' : 'Unavailable'}
            icon={<CheckCircle2 className="h-5 w-5" />}
            sub="all-MiniLM-L6-v2"
            highlight={stats?.embed_status === 'ok'}
          />
        </div>

        {/* Quick actions */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <QuickAction
            href="/repos"
            title="Manage Repositories"
            desc="Connect GitHub repos and trigger ingestion"
            icon={<GitBranch className="h-6 w-6 text-primary-400" />}
          />
          <QuickAction
            href="/chat"
            title="Chat with Codebase"
            desc="Ask questions about your repositories"
            icon={<MessageSquare className="h-6 w-6 text-purple-400" />}
          />
          <QuickAction
            href="/agent"
            title="Autonomous Agent"
            desc="Describe a bug and let AI fix it automatically"
            icon={<Bot className="h-6 w-6 text-green-400" />}
          />
        </div>
      </main>
    </>
  )
}

function StatCard({ label, value, icon, sub, highlight }: {
  label: string; value: string; icon: React.ReactNode; sub?: string; highlight?: boolean
}) {
  return (
    <div className="rounded-xl border border-dark-700 bg-dark-800/50 p-5">
      <div className={`mb-3 ${highlight ? 'text-green-400' : 'text-dark-400'}`}>{icon}</div>
      <p className="text-2xl font-bold text-white mb-0.5">{value}</p>
      <p className="text-sm text-dark-400">{label}</p>
      {sub && <p className="text-xs text-dark-500 mt-1">{sub}</p>}
    </div>
  )
}

function QuickAction({ href, title, desc, icon }: {
  href: string; title: string; desc: string; icon: React.ReactNode
}) {
  return (
    <Link
      href={href}
      className="group flex items-center gap-4 rounded-xl border border-dark-700 bg-dark-800/50 p-5 hover:border-primary-700 hover:bg-dark-800 transition-all"
    >
      <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-dark-900 border border-dark-700 group-hover:border-dark-600 transition-colors">
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-semibold text-white mb-0.5">{title}</p>
        <p className="text-sm text-dark-400 truncate">{desc}</p>
      </div>
      <ArrowRight className="h-5 w-5 text-dark-500 group-hover:text-primary-400 transition-colors shrink-0" />
    </Link>
  )
}

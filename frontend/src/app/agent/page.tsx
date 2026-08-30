'use client'

import { useState, useEffect } from 'react'
import Navbar from '@/components/Navbar'
import AgentPanel from '@/components/AgentPanel'
import { Bot, GitBranch, ChevronDown } from 'lucide-react'

interface Repo {
  id: number
  name: string
  full_name: string
  ingestion_status: string
  total_chunks: number
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function AgentPage() {
  const [repos, setRepos] = useState<Repo[]>([])
  const [selectedRepo, setSelectedRepo] = useState<Repo | null>(null)
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`${API_URL}/api/repos`)
      .then(r => r.json())
      .then(data => {
        const ready = (data.repositories || []).filter(
          (r: Repo) => r.ingestion_status === 'completed'
        )
        setRepos(ready)
        if (ready.length > 0) setSelectedRepo(ready[0])
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <>
      <Navbar />
      <main className="pt-20 px-4 pb-12 max-w-3xl mx-auto">
        {/* Header with repo selector */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-900/30 border border-purple-800/30">
              <Bot className="h-5 w-5 text-purple-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Autonomous Agent</h1>
              <p className="text-sm text-dark-400">AI-powered bug fixing with automatic PR creation</p>
            </div>
          </div>

          {/* Repo selector */}
          <div className="relative">
            <button
              onClick={() => setDropdownOpen(o => !o)}
              className="flex items-center gap-2 rounded-lg border border-dark-600 bg-dark-800 px-3 py-2 text-sm text-dark-200 hover:border-dark-500 hover:text-white transition-all"
            >
              <GitBranch className="h-3.5 w-3.5 text-primary-400" />
              {selectedRepo ? selectedRepo.full_name : loading ? 'Loading...' : 'Select repo'}
              <ChevronDown className="h-3.5 w-3.5 text-dark-400" />
            </button>

            {dropdownOpen && (
              <div className="absolute right-0 top-full mt-1 w-72 rounded-xl border border-dark-600 bg-dark-800 shadow-2xl z-50 overflow-hidden">
                {repos.length === 0 ? (
                  <div className="px-4 py-6 text-center text-sm text-dark-400">
                    No ingested repositories.
                  </div>
                ) : (
                  repos.map(repo => (
                    <button
                      key={repo.id}
                      onClick={() => { setSelectedRepo(repo); setDropdownOpen(false) }}
                      className="w-full flex items-center justify-between px-4 py-3 text-sm text-left hover:bg-dark-700 transition-colors"
                    >
                      <span className="text-dark-100 truncate">{repo.full_name}</span>
                      <span className="text-xs text-primary-400 shrink-0 ml-2">
                        {repo.total_chunks.toLocaleString()} chunks
                      </span>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>
        </div>

        {/* Agent panel */}
        {selectedRepo ? (
          <AgentPanel
            repositoryId={selectedRepo.id}
            repositoryName={selectedRepo.full_name}
          />
        ) : (
          <div className="rounded-2xl border border-dashed border-dark-600 p-16 text-center">
            <Bot className="mx-auto h-10 w-10 text-dark-600 mb-4" />
            <p className="text-dark-400">
              {loading ? 'Loading repositories...' : 'Connect and ingest a repository first.'}
            </p>
          </div>
        )}
      </main>
    </>
  )
}

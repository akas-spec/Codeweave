'use client'

import { useState, useEffect } from 'react'
import Navbar from '@/components/Navbar'
import ChatPanel from '@/components/ChatPanel'
import { MessageSquare, GitBranch, ChevronDown } from 'lucide-react'

interface Repo {
  id: number
  name: string
  full_name: string
  ingestion_status: string
  total_chunks: number
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function ChatPage() {
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
      <main className="flex flex-col h-screen pt-16">
        {/* Toolbar */}
        <div className="flex items-center gap-4 border-b border-dark-700 px-4 py-3 bg-dark-900/80 backdrop-blur">
          <div className="flex items-center gap-2 text-sm font-medium text-white">
            <MessageSquare className="h-4 w-4 text-primary-400" />
            Chat with Codebase
          </div>

          {/* Repo selector */}
          <div className="relative ml-auto">
            <button
              onClick={() => setDropdownOpen(o => !o)}
              className="flex items-center gap-2 rounded-lg border border-dark-600 bg-dark-800 px-3 py-2 text-sm text-dark-200 hover:border-dark-500 hover:text-white transition-all"
            >
              <GitBranch className="h-3.5 w-3.5 text-primary-400" />
              {selectedRepo ? selectedRepo.full_name : loading ? 'Loading...' : 'Select repository'}
              <ChevronDown className="h-3.5 w-3.5 text-dark-400" />
            </button>

            {dropdownOpen && (
              <div className="absolute right-0 top-full mt-1 w-72 rounded-xl border border-dark-600 bg-dark-800 shadow-2xl z-50 overflow-hidden">
                {repos.length === 0 ? (
                  <div className="px-4 py-6 text-center text-sm text-dark-400">
                    No ingested repositories yet.
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

        {/* Chat area */}
        <div className="flex-1 overflow-hidden">
          {selectedRepo ? (
            <ChatPanel
              repositoryId={selectedRepo.id}
              repositoryName={selectedRepo.full_name}
            />
          ) : (
            <div className="flex h-full items-center justify-center">
              <div className="text-center space-y-3">
                <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-dark-800 border border-dark-700">
                  <MessageSquare className="h-7 w-7 text-dark-500" />
                </div>
                <p className="text-dark-400 text-sm">
                  {loading ? 'Loading repositories...' : 'Connect and ingest a repository to start chatting.'}
                </p>
              </div>
            </div>
          )}
        </div>
      </main>
    </>
  )
}

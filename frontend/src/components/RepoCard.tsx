'use client'

import { useState } from 'react'
import { GitBranch, Code2, Globe, Trash2, RefreshCw, MessageSquare, CheckCircle2, Clock, AlertCircle, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import IngestionStatus from './IngestionStatus'

interface RepoCardProps {
  repo: {
    id: number
    name: string
    full_name: string
    github_url: string
    description?: string
    language?: string
    default_branch: string
    ingestion_status: string
    ingestion_progress: number
    total_chunks: number
  }
  onChatClick?: (repoId: number) => void
  onReIngest?: (repoId: number) => void
}

const STATUS_CONFIG = {
  pending:   { label: 'Pending',   color: 'text-dark-400',  bg: 'bg-dark-700',    icon: Clock },
  cloning:   { label: 'Cloning',   color: 'text-blue-400',  bg: 'bg-blue-900/30', icon: Loader2 },
  parsing:   { label: 'Parsing',   color: 'text-yellow-400',bg: 'bg-yellow-900/30',icon: Loader2 },
  embedding: { label: 'Embedding', color: 'text-purple-400',bg: 'bg-purple-900/30',icon: Loader2 },
  completed: { label: 'Ready',     color: 'text-green-400', bg: 'bg-green-900/30', icon: CheckCircle2 },
  failed:    { label: 'Failed',    color: 'text-red-400',   bg: 'bg-red-900/30',  icon: AlertCircle },
}

const LANGUAGE_COLORS: Record<string, string> = {
  Python: 'bg-blue-500',
  TypeScript: 'bg-blue-400',
  JavaScript: 'bg-yellow-400',
  Go: 'bg-cyan-400',
  Rust: 'bg-orange-500',
  Java: 'bg-red-500',
}

export default function RepoCard({ repo, onChatClick, onReIngest }: RepoCardProps) {
  const [showIngestion, setShowIngestion] = useState(
    ['cloning', 'parsing', 'embedding'].includes(repo.ingestion_status)
  )

  const statusCfg = STATUS_CONFIG[repo.ingestion_status as keyof typeof STATUS_CONFIG]
    || STATUS_CONFIG.pending
  const StatusIcon = statusCfg.icon
  const isIngesting = ['cloning', 'parsing', 'embedding'].includes(repo.ingestion_status)
  const isReady = repo.ingestion_status === 'completed'

  return (
    <div className="group relative rounded-xl border border-dark-700 bg-dark-800/50 p-5 hover:border-dark-600 hover:bg-dark-800 transition-all duration-200">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2 min-w-0">
          <Code2 className="h-4 w-4 text-primary-400 shrink-0" />
          <a
            href={repo.github_url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-semibold text-white hover:text-primary-300 truncate transition-colors"
          >
            {repo.full_name}
          </a>
        </div>

        {/* Status badge */}
        <div className={cn(
          'flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium shrink-0 ml-2',
          statusCfg.bg, statusCfg.color
        )}>
          <StatusIcon className={cn('h-3 w-3', isIngesting && 'animate-spin')} />
          {statusCfg.label}
        </div>
      </div>

      {/* Description */}
      {repo.description && (
        <p className="text-sm text-dark-400 mb-3 line-clamp-2">{repo.description}</p>
      )}

      {/* Meta */}
      <div className="flex items-center gap-3 text-xs text-dark-500 mb-4">
        {repo.language && (
          <span className="flex items-center gap-1.5">
            <span className={cn('h-2 w-2 rounded-full', LANGUAGE_COLORS[repo.language] || 'bg-dark-400')} />
            {repo.language}
          </span>
        )}
        <span className="flex items-center gap-1">
          <GitBranch className="h-3 w-3" />
          {repo.default_branch}
        </span>
        {isReady && (
          <span className="text-primary-400">
            {repo.total_chunks.toLocaleString()} chunks
          </span>
        )}
      </div>

      {/* Ingestion progress (live polling) */}
      {(isIngesting || showIngestion) && (
        <div className="mb-4 p-3 rounded-lg bg-dark-900/50 border border-dark-700">
          <IngestionStatus
            repositoryId={repo.id}
            initialStatus={repo.ingestion_status as any}
            onComplete={() => setShowIngestion(false)}
          />
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => onChatClick?.(repo.id)}
          disabled={!isReady}
          className={cn(
            'flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all',
            isReady
              ? 'bg-primary-600 text-white hover:bg-primary-500'
              : 'bg-dark-700 text-dark-500 cursor-not-allowed',
          )}
        >
          <MessageSquare className="h-3.5 w-3.5" />
          Chat
        </button>

        <button
          onClick={() => {
            onReIngest?.(repo.id)
            setShowIngestion(true)
          }}
          disabled={isIngesting}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium border border-dark-600 text-dark-300 hover:border-dark-500 hover:text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <RefreshCw className={cn('h-3.5 w-3.5', isIngesting && 'animate-spin')} />
          Re-index
        </button>

        <a
          href={repo.github_url}
          target="_blank"
          rel="noopener noreferrer"
          className="ml-auto flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs text-dark-400 hover:text-white transition-colors"
        >
          <Globe className="h-3.5 w-3.5" />
          GitHub
        </a>
      </div>
    </div>
  )
}

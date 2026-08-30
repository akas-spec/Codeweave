'use client'

import { useEffect, useState } from 'react'
import { CheckCircle2, XCircle, Loader2, GitBranch, Database, Cpu } from 'lucide-react'
import { cn } from '@/lib/utils'

type Status = 'pending' | 'cloning' | 'parsing' | 'embedding' | 'completed' | 'failed'

interface IngestionStatusProps {
  repositoryId: number
  initialStatus?: Status
  onComplete?: () => void
}

const STEPS = [
  { key: 'cloning',   label: 'Cloning repository',   icon: GitBranch },
  { key: 'parsing',   label: 'Parsing & chunking',    icon: Database },
  { key: 'embedding', label: 'Generating embeddings', icon: Cpu },
  { key: 'completed', label: 'Complete',               icon: CheckCircle2 },
] as const

const STATUS_ORDER: Record<Status, number> = {
  pending:   0,
  cloning:   1,
  parsing:   2,
  embedding: 3,
  completed: 4,
  failed:    -1,
}

export default function IngestionStatus({
  repositoryId,
  initialStatus = 'pending',
  onComplete,
}: IngestionStatusProps) {
  const [status, setStatus] = useState<Status>(initialStatus)
  const [progress, setProgress] = useState(0)
  const [totalChunks, setTotalChunks] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [polling, setPolling] = useState(true)

  useEffect(() => {
    if (!polling) return

    const poll = async () => {
      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL}/api/repos/${repositoryId}/status`
        )
        if (!res.ok) return
        const data = await res.json()
        setStatus(data.status)
        setProgress(data.progress)
        setTotalChunks(data.total_chunks)
        if (data.error) setError(data.error)
        if (data.status === 'completed' || data.status === 'failed') {
          setPolling(false)
          if (data.status === 'completed') onComplete?.()
        }
      } catch {
        // Silently fail — keep polling
      }
    }

    poll()
    const interval = setInterval(poll, 2000)
    return () => clearInterval(interval)
  }, [repositoryId, polling, onComplete])

  const activeStep = STATUS_ORDER[status]

  if (status === 'completed') {
    return (
      <div className="flex items-center gap-2 text-sm text-green-400">
        <CheckCircle2 className="h-4 w-4" />
        <span>Ingestion complete — {totalChunks.toLocaleString()} chunks indexed</span>
      </div>
    )
  }

  if (status === 'failed') {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-sm text-red-400">
          <XCircle className="h-4 w-4" />
          <span>Ingestion failed</span>
        </div>
        {error && <p className="text-xs text-red-300/70 font-mono">{error}</p>}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* Progress bar */}
      <div className="w-full bg-dark-700 rounded-full h-1.5 overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-primary-500 to-purple-500 transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Steps */}
      <div className="flex items-center gap-1">
        {STEPS.map((step, i) => {
          const stepNum = i + 1
          const Icon = step.icon
          const isDone = activeStep > stepNum
          const isActive = activeStep === stepNum
          return (
            <div key={step.key} className="flex items-center gap-1">
              <div className={cn(
                'flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium transition-colors',
                isDone && 'text-green-400',
                isActive && 'text-primary-300 bg-primary-900/30',
                !isDone && !isActive && 'text-dark-500',
              )}>
                {isActive
                  ? <Loader2 className="h-3 w-3 animate-spin" />
                  : isDone
                    ? <CheckCircle2 className="h-3 w-3" />
                    : <Icon className="h-3 w-3" />
                }
                <span className="hidden sm:inline">{step.label}</span>
              </div>
              {i < STEPS.length - 1 && (
                <div className={cn('h-px w-4 bg-dark-600', isDone && 'bg-green-700')} />
              )}
            </div>
          )
        })}
      </div>

      <p className="text-xs text-dark-400">{progress}% complete</p>
    </div>
  )
}

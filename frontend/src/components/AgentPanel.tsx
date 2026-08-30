'use client'

import { useState, useEffect, useCallback } from 'react'
import { Bot, Play, Loader2, AlertTriangle } from 'lucide-react'
import { cn } from '@/lib/utils'
import PRPreview from './PRPreview'

interface AgentPanelProps {
  repositoryId: number
  repositoryName: string
}

interface AgentJob {
  job_id: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'max_iterations_reached'
  message: string
  iterations: number
  tool_calls: Array<{
    tool: string
    input: Record<string, any>
    output?: string
    success: boolean
  }>
  patch?: string | null
  pr_url?: string | null
  test_output?: string | null
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function AgentPanel({ repositoryId, repositoryName }: AgentPanelProps) {
  const [issueDescription, setIssueDescription] = useState('')
  const [filePath, setFilePath] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [activeJob, setActiveJob] = useState<AgentJob | null>(null)
  const [polling, setPolling] = useState(false)

  // Poll for job status
  useEffect(() => {
    if (!polling || !activeJob?.job_id) return

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_URL}/api/agent/status/${activeJob.job_id}`)
        if (!res.ok) return
        const data: AgentJob = await res.json()
        setActiveJob(data)
        if (data.status !== 'running' && data.status !== 'pending') {
          setPolling(false)
        }
      } catch {}
    }, 3000)

    return () => clearInterval(interval)
  }, [polling, activeJob?.job_id])

  const handleSubmit = useCallback(async () => {
    if (!issueDescription.trim()) return
    setIsSubmitting(true)
    setError('')

    try {
      const res = await fetch(`${API_URL}/api/agent/fix`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          repository_id: repositoryId,
          issue_description: issueDescription,
          file_path: filePath || null,
        }),
      })

      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Failed to start agent')

      setActiveJob(data)
      setPolling(true)
      setIssueDescription('')
      setFilePath('')
    } catch (e: any) {
      setError(e.message)
    } finally {
      setIsSubmitting(false)
    }
  }, [issueDescription, filePath, repositoryId])

  return (
    <div className="space-y-6">
      {/* Input form */}
      <div className="rounded-xl border border-dark-700 bg-dark-800/50 p-5">
        <div className="flex items-center gap-2 mb-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-900/30">
            <Bot className="h-4 w-4 text-purple-400" />
          </div>
          <div>
            <h3 className="font-semibold text-white text-sm">Autonomous Agent</h3>
            <p className="text-xs text-dark-400">Describe an issue and let AI fix it automatically</p>
          </div>
        </div>

        <div className="space-y-3">
          <div>
            <label className="text-xs text-dark-400 mb-1.5 block">Issue Description</label>
            <textarea
              value={issueDescription}
              onChange={e => setIssueDescription(e.target.value)}
              placeholder="e.g., The login function doesn't handle expired tokens correctly. It should return a 401 with a clear error message instead of a 500."
              rows={3}
              className="w-full rounded-xl border border-dark-600 bg-dark-900 px-4 py-3 text-sm text-white placeholder-dark-500 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500/30 transition-colors resize-none"
            />
          </div>

          <div>
            <label className="text-xs text-dark-400 mb-1.5 block">File Path Hint (optional)</label>
            <input
              type="text"
              value={filePath}
              onChange={e => setFilePath(e.target.value)}
              placeholder="e.g., src/auth/login.py"
              className="w-full rounded-xl border border-dark-600 bg-dark-900 px-4 py-2.5 text-sm text-white placeholder-dark-500 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500/30 transition-colors"
            />
          </div>

          {error && (
            <div className="flex items-center gap-2 rounded-lg bg-red-900/20 border border-red-800/30 px-3 py-2 text-sm text-red-400">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          )}

          <button
            onClick={handleSubmit}
            disabled={isSubmitting || !issueDescription.trim()}
            className={cn(
              'flex items-center justify-center gap-2 w-full rounded-xl py-2.5 text-sm font-medium transition-all',
              isSubmitting || !issueDescription.trim()
                ? 'bg-dark-700 text-dark-500 cursor-not-allowed'
                : 'bg-gradient-to-r from-purple-600 to-primary-600 text-white hover:from-purple-500 hover:to-primary-500',
            )}
          >
            {isSubmitting ? (
              <><Loader2 className="h-4 w-4 animate-spin" /> Starting agent...</>
            ) : (
              <><Play className="h-4 w-4" /> Start Autonomous Fix</>
            )}
          </button>
        </div>

        {/* Warning */}
        <p className="text-xs text-dark-500 mt-3 text-center">
          The agent will search code, apply patches, run tests, and can create PRs. Always review changes before merging.
        </p>
      </div>

      {/* Active/completed job result */}
      {activeJob && (
        <PRPreview
          title={`Fix: ${issueDescription.slice(0, 60) || activeJob.message.slice(0, 60)}...`}
          prUrl={activeJob.pr_url}
          status={activeJob.status}
          summary={activeJob.message}
          patch={activeJob.patch}
          iterations={activeJob.iterations}
          toolCalls={activeJob.tool_calls}
        />
      )}

      {/* Polling indicator */}
      {polling && (
        <div className="flex items-center justify-center gap-2 text-sm text-dark-400">
          <Loader2 className="h-4 w-4 animate-spin" />
          Agent is working... polling every 3s
        </div>
      )}
    </div>
  )
}

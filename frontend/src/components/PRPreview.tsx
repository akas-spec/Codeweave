'use client'

import { useState } from 'react'
import { GitPullRequest, ExternalLink, CheckCircle2, XCircle, ChevronDown, ChevronUp, Copy, Check } from 'lucide-react'
import { cn } from '@/lib/utils'

interface PRPreviewProps {
  title?: string
  prUrl?: string | null
  status: 'completed' | 'failed' | 'running' | 'pending' | 'max_iterations_reached'
  summary?: string
  patch?: string | null
  iterations?: number
  toolCalls?: Array<{
    tool: string
    input: Record<string, any>
    output?: string
    success: boolean
  }>
}

export default function PRPreview({
  title,
  prUrl,
  status,
  summary,
  patch,
  iterations = 0,
  toolCalls = [],
}: PRPreviewProps) {
  const [showDiff, setShowDiff] = useState(false)
  const [showToolCalls, setShowToolCalls] = useState(false)
  const [copied, setCopied] = useState(false)

  const statusConfig = {
    completed: { label: 'Fix Applied', color: 'text-green-400', bg: 'bg-green-900/30', icon: CheckCircle2 },
    failed: { label: 'Failed', color: 'text-red-400', bg: 'bg-red-900/30', icon: XCircle },
    running: { label: 'In Progress', color: 'text-blue-400', bg: 'bg-blue-900/30', icon: GitPullRequest },
    pending: { label: 'Pending', color: 'text-dark-400', bg: 'bg-dark-700', icon: GitPullRequest },
    max_iterations_reached: { label: 'Limit Reached', color: 'text-yellow-400', bg: 'bg-yellow-900/30', icon: XCircle },
  }

  const cfg = statusConfig[status] || statusConfig.pending
  const StatusIcon = cfg.icon

  const copyPatch = () => {
    if (patch) {
      navigator.clipboard.writeText(patch)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div className="rounded-xl border border-dark-700 bg-dark-800/50 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-dark-700">
        <div className="flex items-center gap-3">
          <div className={cn('flex h-9 w-9 items-center justify-center rounded-lg', cfg.bg)}>
            <StatusIcon className={cn('h-5 w-5', cfg.color)} />
          </div>
          <div>
            <h3 className="font-semibold text-white text-sm">
              {title || 'Autonomous Fix'}
            </h3>
            <p className="text-xs text-dark-400">
              {iterations} iterations · {toolCalls.length} tool calls
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className={cn(
            'flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium',
            cfg.bg, cfg.color
          )}>
            <StatusIcon className="h-3 w-3" />
            {cfg.label}
          </span>
          {prUrl && (
            <a
              href={prUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 rounded-lg bg-primary-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-primary-500 transition-colors"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              View PR
            </a>
          )}
        </div>
      </div>

      {/* Summary */}
      {summary && (
        <div className="px-4 py-3 border-b border-dark-700">
          <p className="text-sm text-dark-200 leading-relaxed">{summary}</p>
        </div>
      )}

      {/* Tool calls accordion */}
      {toolCalls.length > 0 && (
        <div className="border-b border-dark-700">
          <button
            onClick={() => setShowToolCalls(o => !o)}
            className="w-full flex items-center justify-between px-4 py-3 text-xs text-dark-400 hover:text-dark-200 hover:bg-dark-800 transition-colors"
          >
            <span>Agent Actions ({toolCalls.length})</span>
            {showToolCalls ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          </button>
          {showToolCalls && (
            <div className="px-4 pb-3 space-y-2">
              {toolCalls.map((tc, i) => (
                <div key={i} className="flex items-start gap-2 rounded-lg bg-dark-900/50 p-2.5">
                  <span className={cn(
                    'mt-0.5 h-1.5 w-1.5 rounded-full shrink-0',
                    tc.success ? 'bg-green-400' : 'bg-red-400'
                  )} />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-mono text-primary-300">
                      {tc.tool}({Object.entries(tc.input).map(([k, v]) => `${k}=${JSON.stringify(v).slice(0, 50)}`).join(', ')})
                    </p>
                    {tc.output && (
                      <p className="text-xs text-dark-500 mt-1 line-clamp-2 font-mono">
                        {tc.output}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Diff/patch accordion */}
      {patch && (
        <div>
          <button
            onClick={() => setShowDiff(o => !o)}
            className="w-full flex items-center justify-between px-4 py-3 text-xs text-dark-400 hover:text-dark-200 hover:bg-dark-800 transition-colors"
          >
            <span>Diff</span>
            <div className="flex items-center gap-2">
              <button onClick={(e) => { e.stopPropagation(); copyPatch() }} className="hover:text-white transition-colors">
                {copied ? <Check className="h-3 w-3 text-green-400" /> : <Copy className="h-3 w-3" />}
              </button>
              {showDiff ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            </div>
          </button>
          {showDiff && (
            <pre className="px-4 pb-4 overflow-x-auto text-xs font-mono leading-relaxed">
              {patch.split('\n').map((line, i) => (
                <div
                  key={i}
                  className={cn(
                    line.startsWith('+') && !line.startsWith('+++') && 'text-green-400 bg-green-900/10',
                    line.startsWith('-') && !line.startsWith('---') && 'text-red-400 bg-red-900/10',
                    line.startsWith('@@') && 'text-blue-400',
                  )}
                >
                  {line}
                </div>
              ))}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}

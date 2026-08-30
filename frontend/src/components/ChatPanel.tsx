'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { Send, Loader2, Code2, ChevronDown, ChevronUp, Copy, Check } from 'lucide-react'
import { cn } from '@/lib/utils'

interface SourceChunk {
  source: string
  score: number
}

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: SourceChunk[]
  loading?: boolean
}

interface ChatPanelProps {
  repositoryId: number
  repositoryName: string
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function CodeBlock({ code, language }: { code: string; language?: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <div className="relative my-2 rounded-lg bg-dark-950 border border-dark-700 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-dark-700 bg-dark-900">
        <span className="text-xs text-dark-400">{language || 'code'}</span>
        <button onClick={copy} className="text-dark-400 hover:text-white transition-colors">
          {copied ? <Check className="h-3.5 w-3.5 text-green-400" /> : <Copy className="h-3.5 w-3.5" />}
        </button>
      </div>
      <pre className="p-4 overflow-x-auto text-sm font-mono text-dark-100">
        <code>{code}</code>
      </pre>
    </div>
  )
}

function MessageContent({ content }: { content: string }) {
  // Simple markdown-ish rendering: handle code blocks
  const parts = content.split(/(```[\s\S]*?```)/g)
  return (
    <div className="space-y-2">
      {parts.map((part, i) => {
        if (part.startsWith('```')) {
          const lines = part.slice(3, -3).split('\n')
          const lang = lines[0]
          const code = lines.slice(1).join('\n')
          return <CodeBlock key={i} code={code} language={lang} />
        }
        // Render inline code with backticks
        const inlineParts = part.split(/(`[^`]+`)/g)
        return (
          <p key={i} className="leading-relaxed whitespace-pre-wrap">
            {inlineParts.map((ip, j) =>
              ip.startsWith('`') && ip.endsWith('`')
                ? <code key={j} className="bg-dark-700 px-1.5 py-0.5 rounded text-xs font-mono text-primary-300">{ip.slice(1, -1)}</code>
                : ip
            )}
          </p>
        )
      })}
    </div>
  )
}

function SourcesPanel({ sources }: { sources: SourceChunk[] }) {
  const [open, setOpen] = useState(false)
  if (!sources.length) return null
  return (
    <div className="mt-3 rounded-lg border border-dark-700 overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-3 py-2 text-xs text-dark-400 hover:text-dark-200 bg-dark-800/50 hover:bg-dark-800 transition-colors"
      >
        <span className="flex items-center gap-1.5">
          <Code2 className="h-3 w-3" />
          {sources.length} source{sources.length !== 1 ? 's' : ''}
        </span>
        {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
      </button>
      {open && (
        <div className="divide-y divide-dark-700">
          {sources.map((s, i) => (
            <div key={i} className="px-3 py-2 bg-dark-900/50">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono text-primary-300 truncate">{s.source}</span>
                <span className="text-xs text-dark-500 shrink-0 ml-2">{Math.round(s.score * 100)}% match</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'
  return (
    <div className={cn('flex gap-3', isUser && 'flex-row-reverse')}>
      {/* Avatar */}
      <div className={cn(
        'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-xs font-bold',
        isUser ? 'bg-primary-600 text-white' : 'bg-dark-700 text-dark-200',
      )}>
        {isUser ? 'You' : 'CW'}
      </div>

      {/* Content */}
      <div className={cn(
        'max-w-[80%] rounded-xl px-4 py-3 text-sm',
        isUser
          ? 'bg-primary-600/20 border border-primary-600/30 text-white'
          : 'bg-dark-800 border border-dark-700 text-dark-100',
      )}>
        {message.loading ? (
          <div className="flex items-center gap-2 text-dark-400">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>Thinking...</span>
          </div>
        ) : (
          <>
            <MessageContent content={message.content} />
            {message.sources && <SourcesPanel sources={message.sources} />}
          </>
        )}
      </div>
    </div>
  )
}

export default function ChatPanel({ repositoryId, repositoryName }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([{
    id: 'welcome',
    role: 'assistant',
    content: `Hi! I'm ready to answer questions about **${repositoryName}**. Ask me anything — architecture decisions, how functions work, bug locations, and more.`,
  }])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = useCallback(async () => {
    const question = input.trim()
    if (!question || isStreaming) return

    const userMsgId = Date.now().toString()
    const asstMsgId = (Date.now() + 1).toString()

    setInput('')
    setIsStreaming(true)

    // Add user message
    setMessages(prev => [
      ...prev,
      { id: userMsgId, role: 'user', content: question },
      { id: asstMsgId, role: 'assistant', content: '', loading: true },
    ])

    abortRef.current = new AbortController()
    let assistantContent = ''
    let sources: SourceChunk[] = []

    try {
      const res = await fetch(`${API_URL}/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, repository_id: repositoryId }),
        signal: abortRef.current.signal,
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('event: sources')) continue
          if (line.startsWith('event: done')) continue
          if (line.startsWith('event: error')) continue

          if (line.startsWith('data: ')) {
            const data = line.slice(6)
            if (!data || data === '{}') continue

            // Check if it's a sources JSON array
            if (data.startsWith('[')) {
              try {
                sources = JSON.parse(data)
              } catch {}
              continue
            }

            // Regular token — unescape \n
            const token = data.replace(/\\n/g, '\n')
            assistantContent += token
            setMessages(prev => prev.map(m =>
              m.id === asstMsgId
                ? { ...m, content: assistantContent, loading: false }
                : m
            ))
          }
        }
      }

      // Set final sources
      setMessages(prev => prev.map(m =>
        m.id === asstMsgId
          ? { ...m, content: assistantContent, loading: false, sources }
          : m
      ))
    } catch (err: any) {
      if (err.name === 'AbortError') return
      setMessages(prev => prev.map(m =>
        m.id === asstMsgId
          ? { ...m, content: `Error: ${err.message}`, loading: false }
          : m
      ))
    } finally {
      setIsStreaming(false)
    }
  }, [input, isStreaming, repositoryId])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map(msg => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-dark-700 p-4">
        <div className="flex gap-2 items-end">
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about the codebase... (Enter to send, Shift+Enter for newline)"
            rows={1}
            className="flex-1 resize-none rounded-xl border border-dark-600 bg-dark-800 px-4 py-3 text-sm text-white placeholder-dark-500 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500/30 transition-colors min-h-[48px] max-h-[200px]"
            style={{ height: 'auto' }}
            onInput={e => {
              const t = e.currentTarget
              t.style.height = 'auto'
              t.style.height = Math.min(t.scrollHeight, 200) + 'px'
            }}
            disabled={isStreaming}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || isStreaming}
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-primary-600 text-white hover:bg-primary-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {isStreaming
              ? <Loader2 className="h-5 w-5 animate-spin" />
              : <Send className="h-5 w-5" />
            }
          </button>
        </div>
        <p className="text-xs text-dark-500 mt-2 text-center">
          AI responses are grounded in your codebase. Always review before acting.
        </p>
      </div>
    </div>
  )
}

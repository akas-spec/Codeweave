'use client'

import { useEffect, useState, Suspense, useRef } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { api } from '@/lib/api'

function AuthCallbackContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [error, setError] = useState<string | null>(null)
  const processedCode = useRef<string | null>(null)

  useEffect(() => {
    const code = searchParams.get('code')
    if (!code) {
      setError('No authorization code found in URL')
      return
    }
    
    if (processedCode.current === code) return
    processedCode.current = code

    const completeLogin = async () => {
      try {
        const res = await api.githubCallback(code)
        if (res.access_token) {
          api.setToken(res.access_token)
          window.location.replace('/dashboard')
        } else {
          setError('Invalid token response from server')
        }
      } catch (err: any) {
        setError(err.message || 'Failed to complete login')
      }
    }

    completeLogin()
  }, [searchParams, router])

  return (
    <div className="p-8 max-w-md w-full bg-dark-800 rounded-xl border border-dark-700 text-center shadow-xl">
      {error ? (
        <div>
          <h2 className="text-xl font-bold text-red-400 mb-4">Login Failed</h2>
          <p className="text-dark-300 mb-6">{error}</p>
          <button
            onClick={() => router.push('/')}
            className="w-full py-2 px-4 bg-primary-600 text-white rounded-lg hover:bg-primary-500 transition-colors"
          >
            Back to Home
          </button>
        </div>
      ) : (
        <div>
          <h2 className="text-xl font-bold text-white mb-4">Completing Login...</h2>
          <div className="w-8 h-8 border-4 border-primary-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
        </div>
      )}
    </div>
  )
}

export default function AuthCallback() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-dark-900">
      <Suspense fallback={
        <div className="p-8 max-w-md w-full bg-dark-800 rounded-xl border border-dark-700 text-center shadow-xl">
          <h2 className="text-xl font-bold text-white mb-4">Loading...</h2>
          <div className="w-8 h-8 border-4 border-primary-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
        </div>
      }>
        <AuthCallbackContent />
      </Suspense>
    </div>
  )
}

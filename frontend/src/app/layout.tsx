import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'CodeWeave — AI-Powered Code Engineering',
  description: 'AI-powered autonomous code engineering platform. Connect your GitHub repos, ask questions, find bugs, and auto-fix issues with pull requests.',
  keywords: ['AI', 'code engineering', 'GitHub', 'RAG', 'autonomous coding', 'CodeWeave'],
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-dark-900 text-dark-50 antialiased">
        {children}
      </body>
    </html>
  )
}

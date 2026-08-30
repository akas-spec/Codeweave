"use client";
import Navbar from '@/components/Navbar'
import { Github, MessageSquare, Bug, GitPullRequest, Cpu } from 'lucide-react'

export default function Home() {
  return (
    <div className="min-h-screen relative overflow-hidden bg-dark-900">
      {/* Background pattern */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px]"></div>
      
      {/* Glow effects */}
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-primary-600/20 blur-[120px] pointer-events-none"></div>
      <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-purple-600/20 blur-[120px] pointer-events-none"></div>

      <Navbar />

      <main className="relative pt-32 pb-16 sm:pt-40 sm:pb-24 lg:pb-32 px-4 mx-auto max-w-7xl text-center">
        <div className="space-y-8 animate-fade-in-up">
          <h1 className="text-5xl sm:text-7xl font-extrabold tracking-tight text-white mb-6">
            <span className="gradient-text">AI-Powered</span> Code Engineering
          </h1>
          <p className="max-w-2xl mx-auto text-xl text-dark-300 sm:text-2xl">
            Connect your GitHub repos. Ask questions. Find bugs. Auto-fix with PRs.
          </p>
          <div className="flex justify-center mt-10">
            <button 
              type="button"
              onClick={async () => {
                const { api } = await import('@/lib/api');
                try {
                  const res = await api.getGithubLoginUrl();
                  window.location.href = res.auth_url;
                } catch (e) {
                  console.error('Login failed', e);
                }
              }}
              className="group relative flex items-center gap-3 rounded-full bg-primary-600 px-8 py-4 text-lg font-semibold text-white shadow-lg transition-all hover:bg-primary-500 hover:-translate-y-1 hover:shadow-primary-500/25"
            >
              <Github className="h-6 w-6" />
              Get Started with GitHub
              <div className="absolute inset-0 -z-10 rounded-full bg-primary-400 opacity-0 blur-xl transition-opacity group-hover:opacity-30"></div>
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className="mt-20 grid grid-cols-1 sm:grid-cols-3 gap-8 border-y border-dark-800 py-8 max-w-4xl mx-auto">
          <div className="text-center">
            <p className="text-4xl font-bold text-white mb-2">1M</p>
            <p className="text-sm text-dark-400 font-medium uppercase tracking-wider">Token Context</p>
          </div>
          <div className="text-center border-t sm:border-t-0 sm:border-l border-dark-800 pt-8 sm:pt-0">
            <p className="text-4xl font-bold text-white mb-2">$0</p>
            <p className="text-sm text-dark-400 font-medium uppercase tracking-wider">Development Cost</p>
          </div>
          <div className="text-center border-t sm:border-t-0 sm:border-l border-dark-800 pt-8 sm:pt-0">
            <p className="text-4xl font-bold text-white mb-2">384</p>
            <p className="text-sm text-dark-400 font-medium uppercase tracking-wider">Dim Embeddings</p>
          </div>
        </div>

        {/* Features */}
        <div className="mt-32 text-left">
          <h2 className="text-3xl font-bold text-white mb-12 text-center">Supercharge your workflow</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 lg:gap-8">
            <FeatureCard
              icon={<MessageSquare className="h-8 w-8 text-primary-400" />}
              title="RAG-Powered Q&A"
              description="Ask questions about your codebase, get answers grounded in your actual code."
            />
            <FeatureCard
              icon={<Bug className="h-8 w-8 text-purple-400" />}
              title="Autonomous Bug Fixing"
              description="Detect issues, plan fixes, generate patches, and run tests automatically."
            />
            <FeatureCard
              icon={<GitPullRequest className="h-8 w-8 text-green-400" />}
              title="Pull Request Generation"
              description="Auto-create branches, apply changes, and open PRs for review."
            />
            <FeatureCard
              icon={<Cpu className="h-8 w-8 text-blue-400" />}
              title="Provider-Agnostic LLM"
              description="Switch between free Nemotron, local models, or paid APIs without code changes."
            />
          </div>
        </div>
      </main>

      <style dangerouslySetInnerHTML={{__html: `
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-in-up {
          animation: fadeInUp 0.8s ease-out forwards;
        }
      `}} />
    </div>
  )
}

function FeatureCard({ icon, title, description }: { icon: React.ReactNode, title: string, description: string }) {
  return (
    <div className="group relative rounded-2xl border border-dark-700 bg-dark-800/50 p-8 backdrop-blur-sm transition-all hover:-translate-y-1 hover:bg-dark-800 hover:border-dark-600 overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-primary-600/5 to-transparent opacity-0 transition-opacity group-hover:opacity-100"></div>
      <div className="relative z-10">
        <div className="mb-4 inline-block rounded-xl bg-dark-900/50 p-3 shadow-sm ring-1 ring-dark-700">
          {icon}
        </div>
        <h3 className="mb-3 text-xl font-bold text-white">{title}</h3>
        <p className="text-dark-300 leading-relaxed">{description}</p>
      </div>
    </div>
  )
}

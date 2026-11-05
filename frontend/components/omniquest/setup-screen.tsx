'use client'

import { useState } from 'react'
import { AlertCircle, Hexagon, Layers, Loader2, Sparkles, Trophy, Zap } from 'lucide-react'
import { generateGame } from '@/lib/api'
import type { PublicQuestion } from '@/lib/quiz-data'

const SUGGESTED_TOPICS = ['Data Structures', 'Web Fundamentals', 'Astronomy']

interface SetupScreenProps {
  onStart: (params: {
    sessionId: string
    topic: string
    gauntlet: PublicQuestion[]
    fallbackMessage?: string
  }) => void
}

export function SetupScreen({ onStart }: SetupScreenProps) {
  const [topic, setTopic] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const trimmedTopic = topic.trim()

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!trimmedTopic || isLoading) return

    setIsLoading(true)
    setError(null)

    try {
      const response = await generateGame(trimmedTopic)
      if (!response.gauntlet || response.gauntlet.length === 0) {
        throw new Error('Received an empty gauntlet from the server.')
      }

      onStart({
        sessionId: response.session_id,
        topic: response.topic,
        gauntlet: response.gauntlet,
        fallbackMessage: response.is_fallback ? (response.message ?? 'API unavailable, loaded sample round.') : undefined,
      })
    } catch (err: unknown) {
      setIsLoading(false)
      const message =
        err instanceof Error
          ? err.message
          : 'Failed to generate gauntlet. Please verify the backend is running and try again.'
      setError(message)
    }
  }

  return (
    <main className="bg-grid relative flex min-h-dvh items-center justify-center overflow-hidden px-4 py-12">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-1/2 size-[36rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary/10 blur-3xl"
      />

      <div className="relative w-full max-w-2xl">
        <header className="mb-10 flex flex-col items-center gap-4 text-center">
          <div className="flex items-center gap-2">
            <Hexagon className="size-8 text-primary" aria-hidden="true" />
            <span className="text-2xl font-bold tracking-tight">OmniQuest v0</span>
          </div>
          <span className="rounded-full border border-primary/40 bg-primary/10 px-3 py-1 font-mono text-xs uppercase tracking-widest text-primary">
            AI Learning Gauntlet
          </span>
        </header>

        <form
          onSubmit={handleSubmit}
          className="rounded-2xl border border-border bg-card/80 p-6 shadow-2xl backdrop-blur md:p-10"
        >
          <label
            htmlFor="topic"
            className="block text-balance text-center text-3xl font-bold tracking-tight md:text-4xl"
          >
            What do you want to master today?
          </label>
          <p className="mt-3 text-pretty text-center text-muted-foreground">
            Enter a topic and climb the gauntlet. Answer fast to earn more Insight Points.
          </p>

          <div className="mt-8">
            <input
              id="topic"
              type="text"
              value={topic}
              onChange={(event) => {
                setTopic(event.target.value)
                if (error) setError(null)
              }}
              placeholder="Enter a topic..."
              autoComplete="off"
              disabled={isLoading}
              className="w-full rounded-xl border border-input bg-background/60 px-5 py-4 text-lg text-foreground placeholder:text-muted-foreground transition-colors focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-60"
            />
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span className="text-sm text-muted-foreground">Try:</span>
              {SUGGESTED_TOPICS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => {
                    setTopic(suggestion)
                    if (error) setError(null)
                  }}
                  disabled={isLoading}
                  className="rounded-full border border-border bg-secondary px-3 py-1 text-sm text-secondary-foreground transition-colors hover:border-primary/60 hover:text-primary disabled:opacity-60"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>

          {error && (
            <div
              role="alert"
              className="mt-6 flex items-start gap-3 rounded-xl border border-destructive/50 bg-destructive/15 p-4 text-sm text-destructive"
            >
              <AlertCircle className="size-5 shrink-0" aria-hidden="true" />
              <div className="flex-1 text-left">
                <p className="font-semibold">Unable to initialize gauntlet</p>
                <p className="mt-0.5 text-xs text-destructive/90">{error}</p>
              </div>
            </div>
          )}

          <button
            type="submit"
            disabled={!trimmedTopic || isLoading}
            className="mt-8 flex w-full items-center justify-center gap-3 rounded-xl bg-primary px-6 py-4 text-lg font-bold uppercase tracking-wide text-primary-foreground shadow-[0_6px_0_0_var(--primary-edge),0_0_40px_-8px_var(--primary)] transition-all enabled:hover:-translate-y-0.5 enabled:hover:shadow-[0_8px_0_0_var(--primary-edge),0_0_56px_-6px_var(--primary)] enabled:active:translate-y-1.5 enabled:active:shadow-[0_0_0_0_var(--primary-edge)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-card disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isLoading ? (
              <>
                <Loader2 className="size-5 animate-spin" aria-hidden="true" />
                Generating gauntlet...
              </>
            ) : (
              <>
                <Zap className="size-5" aria-hidden="true" />
                Initialize Gauntlet
              </>
            )}
          </button>
          <p className="sr-only" aria-live="polite">
            {isLoading ? `Generating gauntlet for ${trimmedTopic}` : ''}
          </p>
        </form>

        <ul className="mt-8 grid grid-cols-3 gap-3 text-center">
          <FeatureStat icon={Layers} value="20" label="Stage ladder" />
          <FeatureStat icon={Trophy} value="4" label="Tiers" />
          <FeatureStat icon={Sparkles} value="3" label="Power-ups" />
        </ul>
      </div>
    </main>
  )
}

function FeatureStat({
  icon: Icon,
  value,
  label,
}: {
  icon: React.ComponentType<{ className?: string; 'aria-hidden'?: boolean }>
  value: string
  label: string
}) {
  return (
    <li className="rounded-xl border border-border bg-card/60 px-3 py-4">
      <Icon className="mx-auto size-5 text-primary" aria-hidden />
      <p className="mt-2 font-mono text-xl font-bold">{value}</p>
      <p className="text-xs text-muted-foreground">{label}</p>
    </li>
  )
}

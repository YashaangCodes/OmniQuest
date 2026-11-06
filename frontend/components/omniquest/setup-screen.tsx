'use client'

import { useEffect, useRef, useState } from 'react'
import {
  AlertCircle,
  BookOpen,
  Clock,
  Hexagon,
  Layers,
  Loader2,
  Sparkles,
  Trophy,
  X,
  Zap,
} from 'lucide-react'
import { generateGame } from '@/lib/api'
import type { PublicQuestion } from '@/lib/quiz-data'

const SUGGESTED_TOPICS = ['Data Structures', 'Web Fundamentals', 'Astronomy']
const SUGGESTED_LEVELS = ['10th Grade', 'Beginner', 'Expert', 'Pop Culture']

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
  const [targetLevel, setTargetLevel] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [showColdStartWarning, setShowColdStartWarning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isHowToPlayOpen, setIsHowToPlayOpen] = useState(false)

  const coldStartTimerRef = useRef<number | null>(null)

  useEffect(() => {
    return () => {
      if (coldStartTimerRef.current !== null) {
        window.clearTimeout(coldStartTimerRef.current)
      }
    }
  }, [])

  // Close How to Play modal on Escape key press
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape' && isHowToPlayOpen) {
        setIsHowToPlayOpen(false)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isHowToPlayOpen])

  const trimmedTopic = topic.trim()

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!trimmedTopic || isLoading) return

    setIsLoading(true)
    setError(null)
    setShowColdStartWarning(false)

    // Cold-start warning timer: trigger after 5 seconds of loading
    coldStartTimerRef.current = window.setTimeout(() => {
      setShowColdStartWarning(true)
    }, 5000)

    try {
      const levelToSend = targetLevel.trim() || 'General'
      const response = await generateGame(trimmedTopic, levelToSend)

      if (coldStartTimerRef.current !== null) {
        window.clearTimeout(coldStartTimerRef.current)
        coldStartTimerRef.current = null
      }
      setShowColdStartWarning(false)

      if (!response.gauntlet || response.gauntlet.length === 0) {
        throw new Error('Received an empty gauntlet from the server.')
      }

      onStart({
        sessionId: response.session_id,
        topic: response.topic,
        gauntlet: response.gauntlet,
        fallbackMessage: response.is_fallback
          ? (response.message ?? 'API unavailable, loaded sample round.')
          : undefined,
      })
    } catch (err: unknown) {
      if (coldStartTimerRef.current !== null) {
        window.clearTimeout(coldStartTimerRef.current)
        coldStartTimerRef.current = null
      }
      setShowColdStartWarning(false)
      setIsLoading(false)

      const message =
        err instanceof Error
          ? err.message
          : 'Failed to generate gauntlet. Please verify the backend is running and try again.'
      setError(message)
    }
  }

  return (
    <main className="bg-grid relative flex min-h-dvh items-center justify-center overflow-x-hidden px-4 py-10 md:py-16">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-1/2 size-[36rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary/10 blur-3xl"
      />

      <div className="relative w-full max-w-2xl">
        <header className="mb-8 flex flex-col items-center gap-3 text-center">
          <div className="flex items-center gap-2">
            <Hexagon className="size-8 text-primary" aria-hidden="true" />
            <span className="text-2xl font-bold tracking-tight">OmniQuest v0.5</span>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-2">
            <span className="rounded-full border border-primary/40 bg-primary/10 px-3 py-1 font-mono text-xs uppercase tracking-widest text-primary">
              AI Learning Gauntlet
            </span>
            <button
              type="button"
              onClick={() => setIsHowToPlayOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-secondary/80 px-3 py-1 text-xs font-medium text-foreground transition-all hover:border-primary/60 hover:bg-secondary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              <BookOpen className="size-3.5" aria-hidden="true" />
              <span>How to Play</span>
            </button>
          </div>
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
          <p className="mt-3 text-pretty text-center text-sm text-muted-foreground md:text-base">
            Enter a topic and target level to climb the 20-stage gauntlet. Answer fast to earn more
            Insight Points.
          </p>

          <div className="mt-8 space-y-6">
            {/* Topic Input */}
            <div>
              <label
                htmlFor="topic"
                className="block text-xs font-semibold uppercase tracking-wider text-foreground/90"
              >
                Topic <span className="text-destructive">*</span>
              </label>
              <input
                id="topic"
                type="text"
                value={topic}
                onChange={(event) => {
                  setTopic(event.target.value)
                  if (error) setError(null)
                }}
                maxLength={50}
                placeholder="e.g. Data Structures, Quantum Computing, Pop Art..."
                autoComplete="off"
                disabled={isLoading}
                className="mt-2 w-full rounded-xl border border-input bg-background/60 px-4 py-3.5 text-base text-foreground placeholder:text-muted-foreground transition-colors focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-60 md:text-lg"
              />
              <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                <span className="text-xs text-muted-foreground">Try topic:</span>
                {SUGGESTED_TOPICS.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => {
                      setTopic(suggestion)
                      if (error) setError(null)
                    }}
                    disabled={isLoading}
                    className="rounded-full border border-border bg-secondary px-2.5 py-0.5 text-xs text-secondary-foreground transition-colors hover:border-primary/60 hover:text-primary disabled:opacity-60"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>

            {/* Target Level / Context Input */}
            <div>
              <div className="flex items-center justify-between">
                <label
                  htmlFor="target-level"
                  className="block text-xs font-semibold uppercase tracking-wider text-foreground/90"
                >
                  Target Level / Context
                </label>
                <span className="text-xs text-muted-foreground">Default: General</span>
              </div>
              <input
                id="target-level"
                type="text"
                value={targetLevel}
                onChange={(event) => {
                  setTargetLevel(event.target.value)
                  if (error) setError(null)
                }}
                maxLength={50}
                placeholder="e.g. 10th Grade, Expert, Pop Culture (optional)"
                autoComplete="off"
                disabled={isLoading}
                className="mt-2 w-full rounded-xl border border-input bg-background/60 px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground transition-colors focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-60 md:text-base"
              />
              <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                <span className="text-xs text-muted-foreground">Examples:</span>
                {SUGGESTED_LEVELS.map((level) => (
                  <button
                    key={level}
                    type="button"
                    onClick={() => {
                      setTargetLevel(level)
                      if (error) setError(null)
                    }}
                    disabled={isLoading}
                    className="rounded-full border border-border bg-secondary px-2.5 py-0.5 text-xs text-secondary-foreground transition-colors hover:border-primary/60 hover:text-primary disabled:opacity-60"
                  >
                    {level}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Cold Start Warning */}
          {isLoading && showColdStartWarning && (
            <div
              role="status"
              aria-live="polite"
              className="mt-6 flex items-start gap-3 rounded-xl border border-amber-500/40 bg-amber-500/15 p-4 text-sm text-amber-200 animate-in fade-in"
            >
              <Clock className="size-5 shrink-0 text-amber-400 animate-pulse" aria-hidden="true" />
              <div className="flex-1 text-left">
                <p className="font-semibold text-amber-300">Server Cold Start</p>
                <p className="mt-0.5 text-xs text-amber-200/90 leading-relaxed">
                  Waking up the server... this might take 40-50 seconds on the first run.
                </p>
              </div>
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div
              role="alert"
              className="mt-6 flex items-start gap-3 rounded-xl border border-destructive/50 bg-destructive/15 p-4 text-sm text-destructive animate-in fade-in"
            >
              <AlertCircle className="size-5 shrink-0 text-destructive" aria-hidden="true" />
              <div className="flex-1 text-left">
                <p className="font-semibold">Unable to initialize gauntlet</p>
                <p className="mt-0.5 text-xs text-destructive/90 leading-relaxed">{error}</p>
              </div>
            </div>
          )}

          <button
            type="submit"
            disabled={!trimmedTopic || isLoading}
            className="mt-8 flex w-full items-center justify-center gap-3 rounded-xl bg-primary px-6 py-4 text-base font-bold uppercase tracking-wide text-primary-foreground shadow-[0_6px_0_0_var(--primary-edge),0_0_40px_-8px_var(--primary)] transition-all enabled:hover:-translate-y-0.5 enabled:hover:shadow-[0_8px_0_0_var(--primary-edge),0_0_56px_-6px_var(--primary)] enabled:active:translate-y-1.5 enabled:active:shadow-[0_0_0_0_var(--primary-edge)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-card disabled:cursor-not-allowed disabled:opacity-50 md:text-lg"
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

      {/* How to Play Modal */}
      {isHowToPlayOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="how-to-play-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4 backdrop-blur-md animate-in fade-in duration-150"
          onClick={(e) => {
            if (e.target === e.currentTarget) setIsHowToPlayOpen(false)
          }}
        >
          <div className="relative flex max-h-[88dvh] w-full max-w-2xl flex-col rounded-2xl border border-border bg-card p-6 shadow-2xl md:p-8">
            <div className="flex items-center justify-between border-b border-border pb-4">
              <div className="flex items-center gap-2">
                <BookOpen className="size-5 text-primary" aria-hidden="true" />
                <h2 id="how-to-play-title" className="text-xl font-bold tracking-tight text-foreground">
                  How to Play OmniQuest
                </h2>
              </div>
              <button
                type="button"
                onClick={() => setIsHowToPlayOpen(false)}
                className="rounded-lg p-1.5 text-muted-foreground hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                aria-label="Close How to Play modal"
              >
                <X className="size-5" aria-hidden="true" />
              </button>
            </div>

            <div className="flex-1 space-y-6 overflow-y-auto py-5 pr-1 text-sm text-muted-foreground">
              {/* 20-Stage Structure */}
              <section>
                <h3 className="flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-wider text-foreground">
                  <Layers className="size-4 text-primary" aria-hidden="true" />
                  1. The 20-Stage Gauntlet
                </h3>
                <p className="mt-1.5 leading-relaxed">
                  OmniQuest generates a bespoke 20-question challenge on your chosen topic and target level.
                  Questions progress sequentially from Stage 1 through Stage 20 with increasing depth and complexity.
                </p>
              </section>

              {/* 4 Difficulty Tiers */}
              <section>
                <h3 className="flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-wider text-foreground">
                  <Trophy className="size-4 text-tier-1" aria-hidden="true" />
                  2. Four Difficulty Tiers
                </h3>
                <ul className="mt-2 space-y-1.5 text-xs">
                  <li className="flex items-start gap-2">
                    <span className="font-bold text-tier-1">Tier 1 (Stages 1–5):</span>
                    <span>Foundational definitions and core recall.</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="font-bold text-tier-2">Tier 2 (Stages 6–10):</span>
                    <span>Conceptual connections, relationships, and mechanisms.</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="font-bold text-tier-3">Tier 3 (Stages 11–15):</span>
                    <span>Applied scenarios, edge cases, and problem-solving.</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="font-bold text-tier-4">Tier 4 (Stages 16–20):</span>
                    <span>Multi-step reasoning culminating in a Golden Challenge at Stage 20.</span>
                  </li>
                </ul>
              </section>

              {/* Insight Points & Progression */}
              <section>
                <h3 className="flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-wider text-foreground">
                  <Sparkles className="size-4 text-primary" aria-hidden="true" />
                  3. Insight Points (IP) & Tier Gates
                </h3>
                <p className="mt-1.5 leading-relaxed">
                  Each stage gives you a 20-second timer. Correct answers award{' '}
                  <span className="font-bold text-foreground">100 base IP</span> plus{' '}
                  <span className="font-bold text-primary">5 bonus IP per remaining second</span> (up to 200 IP total).
                </p>
                <p className="mt-1.5 leading-relaxed">
                  <span className="font-semibold text-destructive">Tier Gate Checkpoints:</span> At Stages 5, 10, and 15,
                  you must accumulate at least <span className="font-mono font-bold text-foreground">300 IP</span> within
                  that tier to clear the gate. Failing to meet the threshold ends your run immediately.
                </p>
              </section>

              {/* Answer Selection & Manual Progression */}
              <section>
                <h3 className="flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-wider text-foreground">
                  <Zap className="size-4 text-primary" aria-hidden="true" />
                  4. Answer Selection & Manual Progression
                </h3>
                <p className="mt-1.5 leading-relaxed">
                  When you select an answer, your submission is locked and the timer immediately stops.
                  The server validates your response and provides the verified correct answer and explanation.
                </p>
                <p className="mt-1.5 leading-relaxed">
                  Take all the time you need to study the explanation. You advance only when you click the prominent{' '}
                  <span className="font-bold text-primary">Next Stage</span> button.
                </p>
              </section>

              {/* Power-Ups */}
              <section>
                <h3 className="flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-wider text-foreground">
                  <Sparkles className="size-4 text-tier-2" aria-hidden="true" />
                  5. Power-Ups
                </h3>
                <p className="mt-1.5 leading-relaxed">
                  You have access to 3 tactical power-ups (usable once per run):
                </p>
                <ul className="mt-1.5 space-y-1 text-xs">
                  <li>
                    <span className="font-bold text-foreground">Time Freeze:</span> Freezes the 20-second countdown for 5 seconds.
                  </li>
                  <li className="text-muted-foreground/80">
                    <span className="font-semibold text-foreground/80">AI Hint & 50/50:</span> Previews of upcoming features (currently locked in live play).
                  </li>
                </ul>
              </section>
            </div>

            <div className="border-t border-border pt-4">
              <button
                type="button"
                onClick={() => setIsHowToPlayOpen(false)}
                className="flex w-full items-center justify-center rounded-xl bg-primary px-6 py-3 font-bold uppercase tracking-wide text-primary-foreground transition-all hover:opacity-95 active:translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              >
                Got It, Let&apos;s Play!
              </button>
            </div>
          </div>
        </div>
      )}
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

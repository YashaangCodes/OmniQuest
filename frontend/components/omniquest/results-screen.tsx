'use client'

import { useEffect, useRef, useState } from 'react'
import {
  Check,
  Clock,
  Flag,
  Flame,
  Hexagon,
  RotateCcw,
  Share2,
  ShieldAlert,
  Target,
  Trophy,
  X,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { AnswerRecord, TierElimination } from '@/lib/quiz-data'

interface ResultsScreenProps {
  topic: string
  answers: AnswerRecord[]
  totalStages?: number
  elimination?: TierElimination | null
  isForfeit?: boolean
  onPlayAgain: () => void
}

function getBestStreak(answers: AnswerRecord[]): number {
  let best = 0
  let current = 0
  for (const answer of answers) {
    current = answer.isCorrect ? current + 1 : 0
    best = Math.max(best, current)
  }
  return best
}

export function ResultsScreen({
  topic,
  answers,
  totalStages,
  elimination,
  isForfeit = false,
  onPlayAgain,
}: ResultsScreenProps) {
  const [shareStatus, setShareStatus] = useState<'idle' | 'copied' | 'error'>('idle')
  const resetTimeoutRef = useRef<number | null>(null)

  useEffect(() => {
    return () => {
      if (resetTimeoutRef.current !== null) window.clearTimeout(resetTimeoutRef.current)
    }
  }, [])

  const totalStagesCount = totalStages ?? answers.length
  const totalPoints = answers.reduce((total, answer) => total + answer.pointsEarned, 0)
  const correctCount = answers.filter((answer) => answer.isCorrect).length
  const accuracy = answers.length ? Math.round((correctCount / answers.length) * 100) : 0
  const averageSeconds = answers.length
    ? answers.reduce((total, answer) => total + answer.responseTimeMs, 0) / answers.length / 1000
    : 0
  const bestStreak = getBestStreak(answers)
  const isEliminated = Boolean(elimination)
  const isVictory = !isEliminated && !isForfeit && accuracy >= 60

  async function handleShare() {
    const shareText = isForfeit
      ? `I scored ${totalPoints} IP on OmniQuest (${topic}) before forfeiting — ${correctCount}/${answers.length} correct!`
      : `I scored ${totalPoints} IP on OmniQuest (${topic}) — ${correctCount}/${answers.length} correct!`
    try {
      if (navigator.share) {
        await navigator.share({ title: 'OmniQuest Score', text: shareText })
        return
      }
      await navigator.clipboard.writeText(shareText)
      setShareStatus('copied')
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return
      setShareStatus('error')
    }
    resetTimeoutRef.current = window.setTimeout(() => setShareStatus('idle'), 2500)
  }

  return (
    <main className="bg-grid min-h-dvh px-4 py-10 md:py-16">
      <div className="mx-auto w-full max-w-3xl">
        <header className="flex flex-col items-center text-center">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Hexagon className="size-5 text-primary" aria-hidden="true" />
            <span className="font-bold text-foreground">OmniQuest v0.5</span>
            <span aria-hidden="true">·</span>
            <span className="font-mono text-xs uppercase tracking-widest">Post-Game Analytics</span>
          </div>

          <div
            className={cn(
              'mt-8 flex size-20 items-center justify-center rounded-2xl border-2',
              isForfeit
                ? 'border-amber-500/60 bg-amber-500/15 text-amber-400 shadow-[0_0_48px_-8px_rgba(245,158,11,0.5)]'
                : isEliminated
                  ? 'border-destructive/60 bg-destructive/15 text-destructive shadow-[0_0_48px_-8px_var(--destructive)]'
                  : isVictory
                    ? 'border-tier-1/60 bg-tier-1/15 text-tier-1 shadow-[0_0_48px_-8px_var(--tier-1)]'
                    : 'border-destructive/60 bg-destructive/15 text-destructive shadow-[0_0_48px_-8px_var(--destructive)]',
            )}
          >
            {isForfeit ? (
              <Flag className="size-10" aria-hidden="true" />
            ) : isVictory ? (
              <Trophy className="size-10" aria-hidden="true" />
            ) : (
              <ShieldAlert className="size-10" aria-hidden="true" />
            )}
          </div>

          {isForfeit ? (
            <>
              <h1 className="mt-6 text-balance text-3xl font-bold tracking-tight text-amber-400 md:text-5xl">
                Run Forfeited
              </h1>
              <p className="mt-3 text-base text-muted-foreground">
                You voluntarily forfeited this run. All accumulated Insight Points and analytics have
                been preserved.
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                Topic: <span className="font-medium text-foreground">{topic}</span>
              </p>
            </>
          ) : isEliminated && elimination ? (
            <>
              <h1 className="mt-6 text-balance text-3xl font-bold tracking-tight text-destructive md:text-5xl">
                Eliminated in Tier {elimination.tier}
              </h1>
              <p className="mt-3 text-base text-muted-foreground">
                You earned{' '}
                <span className="font-mono font-bold text-destructive">
                  {elimination.earnedIp}
                </span>{' '}
                of the{' '}
                <span className="font-mono font-bold text-foreground">
                  {elimination.requiredIp} IP
                </span>{' '}
                required to advance.
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                Topic: <span className="font-medium text-foreground">{topic}</span>
              </p>
            </>
          ) : (
            <>
              <h1 className="mt-6 text-balance text-3xl font-bold tracking-tight md:text-5xl">
                {isVictory ? 'Gauntlet Cleared' : 'Gauntlet Over'}
              </h1>
              <p className="mt-2 text-muted-foreground">
                Topic: <span className="font-medium text-foreground">{topic}</span>
              </p>
            </>
          )}

          <div className="mt-8">
            <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
              Total Insight Points
            </p>
            <p className="mt-1 font-mono text-6xl font-bold tabular-nums text-primary drop-shadow-[0_0_24px_var(--primary)] md:text-7xl">
              {totalPoints.toLocaleString()}
              <span className="ml-2 text-2xl text-primary/80">IP</span>
            </p>
          </div>

          <p
            className={cn(
              'mt-4 rounded-full border px-3 py-1 font-mono text-xs uppercase tracking-widest',
              isForfeit
                ? 'border-amber-500/40 bg-amber-500/10 text-amber-300'
                : 'border-primary/40 bg-primary/10 text-primary',
            )}
          >
            {answers.length} of {totalStagesCount} stages completed{isForfeit ? ' (Forfeited)' : ''}
          </p>
        </header>

        <dl className="mt-10 grid grid-cols-2 gap-3 md:grid-cols-4">
          <StatCard icon={Target} label="Accuracy" value={`${accuracy}%`} />
          <StatCard icon={Check} label="Correct" value={`${correctCount}/${answers.length}`} />
          <StatCard icon={Clock} label="Avg. time" value={`${averageSeconds.toFixed(1)}s`} />
          <StatCard icon={Flame} label="Best streak" value={`${bestStreak}`} />
        </dl>

        <section aria-labelledby="breakdown-heading" className="mt-10">
          <h2
            id="breakdown-heading"
            className="mb-3 font-mono text-xs uppercase tracking-widest text-muted-foreground"
          >
            Stage breakdown
          </h2>
          {answers.length === 0 ? (
            <p className="rounded-xl border border-border bg-card p-4 text-center text-sm text-muted-foreground">
              No stages were completed in this run.
            </p>
          ) : (
            <ol className="flex flex-col gap-2">
              {answers.map((answer) => (
                <li
                  key={answer.questionId}
                  className="flex items-start gap-4 rounded-xl border border-border bg-card p-4"
                >
                  <span
                    className={cn(
                      'flex size-9 shrink-0 items-center justify-center rounded-lg',
                      answer.isCorrect ? 'bg-tier-1/15 text-tier-1' : 'bg-destructive/15 text-destructive',
                    )}
                  >
                    {answer.isCorrect ? (
                      <Check className="size-5" aria-label="Correct" />
                    ) : (
                      <X className="size-5" aria-label="Incorrect" />
                    )}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="font-mono text-xs text-muted-foreground">Stage {answer.stage}</p>
                    <p className="text-pretty font-medium">{answer.prompt}</p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Your answer:{' '}
                      <span className={answer.isCorrect ? 'text-tier-1' : 'text-destructive'}>
                        {answer.selectedAnswer ?? 'No answer (time ran out)'}
                      </span>
                      {!answer.isCorrect && (
                        <>
                          {' · '}Correct: <span className="text-tier-1">{answer.correctAnswer}</span>
                        </>
                      )}
                    </p>
                    {answer.explanation && (
                      <p className="mt-1.5 text-xs text-muted-foreground/80">
                        <span className="font-semibold text-foreground/80">Explanation: </span>
                        {answer.explanation}
                      </p>
                    )}
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="font-mono text-sm font-bold tabular-nums text-primary">
                      +{answer.pointsEarned}
                    </p>
                    <p className="font-mono text-xs tabular-nums text-muted-foreground">
                      {(answer.responseTimeMs / 1000).toFixed(1)}s
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </section>

        <div className="mt-10 flex flex-col gap-4 sm:flex-row">
          <button
            type="button"
            onClick={handleShare}
            className="flex flex-1 items-center justify-center gap-2 rounded-xl border-2 border-primary/60 bg-card px-6 py-4 font-bold text-primary shadow-[0_6px_0_0_var(--option-edge)] transition-all hover:-translate-y-0.5 hover:shadow-[0_8px_0_0_var(--option-edge),0_0_32px_-6px_var(--primary)] active:translate-y-1.5 active:shadow-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            <Share2 className="size-5" aria-hidden="true" />
            {shareStatus === 'copied'
              ? 'Copied to clipboard'
              : shareStatus === 'error'
                ? 'Could not share'
                : 'Share Score'}
          </button>
          <button
            type="button"
            onClick={onPlayAgain}
            className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-primary px-6 py-4 font-bold text-primary-foreground shadow-[0_6px_0_0_var(--primary-edge),0_0_40px_-8px_var(--primary)] transition-all hover:-translate-y-0.5 hover:shadow-[0_8px_0_0_var(--primary-edge),0_0_56px_-6px_var(--primary)] active:translate-y-1.5 active:shadow-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            <RotateCcw className="size-5" aria-hidden="true" />
            Play Again
          </button>
        </div>
        <p className="sr-only" aria-live="polite">
          {shareStatus === 'copied' ? 'Score copied to clipboard' : ''}
        </p>
      </div>
    </main>
  )
}

function StatCard({ icon: Icon, label, value }: { icon: typeof Target; label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <dt className="flex items-center gap-2 text-xs text-muted-foreground">
        <Icon className="size-4 text-primary" aria-hidden="true" />
        {label}
      </dt>
      <dd className="mt-2 font-mono text-2xl font-bold tabular-nums">{value}</dd>
    </div>
  )
}

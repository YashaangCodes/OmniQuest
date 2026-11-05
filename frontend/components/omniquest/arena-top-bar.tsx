import { Snowflake, Sparkles, Timer } from 'lucide-react'
import { cn } from '@/lib/utils'
import { QUESTION_TIME_LIMIT_MS, TIER_TARGET_IP, getTier, type Tier } from '@/lib/quiz-data'

interface ArenaTopBarProps {
  topic: string
  questionNumber: number
  totalQuestions: number
  score: number
  timeLeftMs: number
  isFrozen: boolean
  currentTier?: Tier
  tierScore?: number
  tierTarget?: number
}

export function ArenaTopBar({
  topic,
  questionNumber,
  totalQuestions,
  score,
  timeLeftMs,
  isFrozen,
  currentTier,
  tierScore = 0,
  tierTarget = TIER_TARGET_IP,
}: ArenaTopBarProps) {
  const percentRemaining = (timeLeftMs / QUESTION_TIME_LIMIT_MS) * 100
  const secondsLeft = Math.ceil(timeLeftMs / 1000)
  const isCritical = !isFrozen && secondsLeft <= 5

  const tier = currentTier ?? getTier(questionNumber)
  const percentFilled = Math.min(100, Math.max(0, (tierScore / tierTarget) * 100))
  const isTargetMet = tierScore >= tierTarget
  const isProgressing = !isTargetMet && tierScore >= 120

  const labelColorClass = isTargetMet
    ? 'text-tier-1'
    : isProgressing
      ? 'text-primary'
      : tierScore > 0
        ? 'text-destructive'
        : 'text-muted-foreground'

  const meterFillClass = isTargetMet
    ? 'bg-tier-1 shadow-[0_0_14px_var(--tier-1)]'
    : isProgressing
      ? 'bg-primary shadow-[0_0_10px_-2px_var(--primary)]'
      : tierScore > 0
        ? 'bg-destructive/80 shadow-[0_0_8px_-2px_var(--destructive)]'
        : 'bg-muted-foreground/30'

  return (
    <header className="border-b border-border bg-background/80 backdrop-blur">
      <div className="mx-auto flex w-full max-w-4xl flex-wrap items-center justify-between gap-3 px-4 py-4 md:px-8">
        <div className="min-w-0">
          <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
            Question {questionNumber} of {totalQuestions}
          </p>
          <p className="truncate text-lg font-bold">{topic}</p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Tier Progression Meter */}
          <div
            className={cn(
              'flex min-w-[210px] flex-col justify-center gap-1.5 rounded-xl border px-3.5 py-2 transition-all',
              isTargetMet
                ? 'border-tier-1/50 bg-tier-1/10 shadow-[0_0_20px_-4px_var(--tier-1)]'
                : isProgressing
                  ? 'border-primary/30 bg-primary/5'
                  : tierScore > 0
                    ? 'border-destructive/30 bg-destructive/5'
                    : 'border-border bg-card/80',
            )}
            aria-label={`Tier ${tier} requirement: ${tierScore} / ${tierTarget} IP`}
          >
            <div className="flex items-center justify-between gap-2 font-mono text-[11px] leading-tight">
              <span className="text-muted-foreground">
                Tier {tier} requirement:
              </span>
              <span className={cn('font-bold tabular-nums', labelColorClass)}>
                {tierScore} / {tierTarget} IP
              </span>
            </div>
            <div
              role="progressbar"
              aria-label={`Tier ${tier} requirement progression`}
              aria-valuemin={0}
              aria-valuemax={tierTarget}
              aria-valuenow={Math.min(tierScore, tierTarget)}
              aria-valuetext={`Tier ${tier} requirement: ${tierScore} / ${tierTarget} IP`}
              className="h-2 w-full overflow-hidden rounded-full bg-secondary"
            >
              <div
                className={cn('h-full rounded-full transition-all duration-300 ease-out', meterFillClass)}
                style={{ width: `${percentFilled}%` }}
              />
            </div>
          </div>

          {/* Total IP Score */}
          <div
            className="flex items-center gap-2 rounded-xl border border-primary/40 bg-primary/10 px-4 py-2"
            aria-label={`Score: ${score} Insight Points`}
          >
            <Sparkles className="size-4 text-primary" aria-hidden="true" />
            <span className="font-mono text-xl font-bold tabular-nums text-primary">
              {score.toLocaleString()}
            </span>
            <span className="font-mono text-sm text-primary/80">IP</span>
          </div>
        </div>
      </div>

      <div className="mx-auto flex w-full max-w-4xl items-center gap-3 px-4 pb-4 md:px-8">
        {isFrozen ? (
          <Snowflake className="size-4 shrink-0 text-primary" aria-hidden="true" />
        ) : (
          <Timer
            className={cn('size-4 shrink-0', isCritical ? 'text-destructive' : 'text-muted-foreground')}
            aria-hidden="true"
          />
        )}
        <div
          role="progressbar"
          aria-label="Time remaining"
          aria-valuemin={0}
          aria-valuemax={QUESTION_TIME_LIMIT_MS / 1000}
          aria-valuenow={secondsLeft}
          className="h-3 flex-1 overflow-hidden rounded-full bg-secondary"
        >
          <div
            className={cn(
              'h-full rounded-full transition-[width] duration-100 ease-linear',
              isFrozen
                ? 'bg-primary/60 shadow-[0_0_16px_var(--primary)]'
                : isCritical
                  ? 'bg-destructive shadow-[0_0_16px_var(--destructive)]'
                  : 'bg-primary shadow-[0_0_16px_-2px_var(--primary)]',
            )}
            style={{ width: `${percentRemaining}%` }}
          />
        </div>
        <span
          className={cn(
            'w-16 text-right font-mono text-sm font-bold tabular-nums',
            isCritical ? 'text-destructive' : 'text-foreground',
          )}
        >
          {isFrozen ? 'FROZEN' : `${secondsLeft}s`}
        </span>
      </div>
    </header>
  )
}

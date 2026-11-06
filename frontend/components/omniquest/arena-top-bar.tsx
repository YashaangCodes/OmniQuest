import { Flag, Snowflake, Sparkles, Timer } from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  QUESTION_TIME_LIMIT_MS,
  TIER_STYLES,
  TIER_TARGET_IP,
  getTier,
  type Tier,
} from '@/lib/quiz-data'

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
  onForfeitClick?: () => void
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
  onForfeitClick,
}: ArenaTopBarProps) {
  const percentRemaining = (timeLeftMs / QUESTION_TIME_LIMIT_MS) * 100
  const secondsLeft = Math.ceil(timeLeftMs / 1000)
  const isCritical = !isFrozen && secondsLeft <= 5

  const tier = currentTier ?? getTier(questionNumber)
  const tierStyle = TIER_STYLES[tier] || TIER_STYLES[1]
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
    <header className="shrink-0 border-b border-border bg-background/90 backdrop-blur-md">
      <div className="mx-auto flex w-full max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-3 md:px-6">
        {/* Stage, Tier & Topic */}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={cn(
                'rounded-full border px-2.5 py-0.5 font-mono text-[11px] font-semibold uppercase tracking-wider',
                tierStyle.border,
                tierStyle.softBg,
                tierStyle.text,
              )}
            >
              Stage {questionNumber} / {totalQuestions} · {tierStyle.label}
            </span>
          </div>
          <p className="mt-1 truncate text-base font-bold text-foreground md:text-lg">{topic}</p>
        </div>

        {/* IP Progress, Total Score & Forfeit Button */}
        <div className="flex flex-wrap items-center gap-2.5 sm:gap-3">
          {/* Tier Progression Meter */}
          <div
            className={cn(
              'flex min-w-[170px] flex-col justify-center gap-1 rounded-xl border px-3 py-1.5 transition-all sm:min-w-[200px]',
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
            <div className="flex items-center justify-between gap-2 font-mono text-[10px] leading-tight sm:text-[11px]">
              <span className="text-muted-foreground">Tier {tier} req:</span>
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
              className="h-1.5 w-full overflow-hidden rounded-full bg-secondary sm:h-2"
            >
              <div
                className={cn('h-full rounded-full transition-all duration-300 ease-out', meterFillClass)}
                style={{ width: `${percentFilled}%` }}
              />
            </div>
          </div>

          {/* Total IP Score */}
          <div
            className="flex items-center gap-1.5 rounded-xl border border-primary/40 bg-primary/10 px-3 py-1.5 sm:gap-2 sm:px-3.5"
            aria-label={`Score: ${score} Insight Points`}
          >
            <Sparkles className="size-3.5 text-primary sm:size-4" aria-hidden="true" />
            <span className="font-mono text-base font-bold tabular-nums text-primary sm:text-lg">
              {score.toLocaleString()}
            </span>
            <span className="font-mono text-xs text-primary/80">IP</span>
          </div>

          {/* Forfeit Run Button in Top Right */}
          {onForfeitClick && (
            <button
              type="button"
              onClick={onForfeitClick}
              className="inline-flex items-center gap-1.5 rounded-xl border border-destructive/40 bg-destructive/10 px-2.5 py-1.5 font-mono text-xs font-semibold text-destructive transition-all hover:border-destructive hover:bg-destructive/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive sm:px-3"
              aria-label="Forfeit active run"
              title="Forfeit active run"
            >
              <Flag className="size-3.5" aria-hidden="true" />
              <span className="hidden sm:inline">Forfeit Run</span>
              <span className="sm:hidden">Forfeit</span>
            </button>
          )}
        </div>
      </div>

      {/* Countdown Timer Bar */}
      <div className="mx-auto flex w-full max-w-5xl items-center gap-3 px-4 pb-2.5 md:px-6">
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
          className="h-2 flex-1 overflow-hidden rounded-full bg-secondary"
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
            'w-16 text-right font-mono text-xs font-bold tabular-nums sm:text-sm',
            isCritical ? 'text-destructive' : 'text-foreground',
          )}
        >
          {isFrozen ? 'FROZEN' : `${secondsLeft}s`}
        </span>
      </div>
    </header>
  )
}

import { Check, Hexagon, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  TIER_STYLES,
  type AnswerRecord,
  type PublicQuestion,
  type Tier,
} from '@/lib/quiz-data'

interface StageLadderProps {
  currentStage: number
  answers: AnswerRecord[]
  gauntlet: PublicQuestion[]
}

const TIERS_TOP_DOWN: Tier[] = [4, 3, 2, 1]

export function StageLadder({ currentStage, answers, gauntlet }: StageLadderProps) {
  const activeTiers = TIERS_TOP_DOWN.filter((tier) =>
    gauntlet.some((q) => q.tier === tier),
  )

  return (
    <aside
      aria-label="Stage ladder"
      className="hidden w-64 shrink-0 flex-col border-r border-sidebar-border bg-sidebar lg:sticky lg:top-0 lg:flex lg:h-dvh"
    >
      <div className="flex items-center gap-2 border-b border-sidebar-border px-5 py-4">
        <Hexagon className="size-5 text-primary" aria-hidden="true" />
        <span className="font-bold tracking-tight">OmniQuest v0</span>
      </div>

      <div className="px-5 pt-4">
        <p className="rounded-md border border-primary/40 bg-primary/10 px-2 py-1 text-center font-mono text-[11px] uppercase tracking-widest text-primary">
          Gauntlet · {gauntlet.length} stages
        </p>
      </div>

      <ol className="flex flex-1 flex-col gap-2 overflow-y-auto px-5 py-3">
        {activeTiers.map((tier) => {
          const questionsForTier = gauntlet
            .filter((q) => q.tier === tier)
            .sort((a, b) => b.stage - a.stage)

          return (
            <li key={tier}>
              <p
                className={cn(
                  'mb-1 font-mono text-[11px] uppercase tracking-widest',
                  TIER_STYLES[tier].text,
                )}
              >
                {TIER_STYLES[tier].label}
              </p>
              <ol className="flex flex-col gap-0.5">
                {questionsForTier.map((q) => (
                  <LadderRung
                    key={q.stage}
                    stage={q.stage}
                    tier={q.tier as Tier}
                    currentStage={currentStage}
                    answer={answers.find((a) => a.stage === q.stage)}
                  />
                ))}
              </ol>
            </li>
          )
        })}
      </ol>
    </aside>
  )
}

function LadderRung({
  stage,
  tier,
  currentStage,
  answer,
}: {
  stage: number
  tier: Tier
  currentStage: number
  answer?: AnswerRecord
}) {
  const styles = TIER_STYLES[tier] || TIER_STYLES[1]
  const isCurrent = stage === currentStage

  return (
    <li
      aria-current={isCurrent ? 'step' : undefined}
      className={cn(
        'flex items-center gap-3 rounded-md border px-3 py-0.5 text-sm transition-all',
        isCurrent
          ? cn(styles.border, styles.softBg, styles.glow, 'font-bold text-foreground')
          : 'border-transparent text-muted-foreground',
      )}
    >
      <span
        className={cn(
          'flex size-5 items-center justify-center rounded font-mono text-xs',
          isCurrent ? cn(styles.bg, 'text-background') : cn(styles.softBg, styles.text),
        )}
      >
        {stage}
      </span>
      <span className="flex-1">Stage {stage}</span>
      {answer?.isCorrect && <Check className="size-4 text-tier-1" aria-label="Correct" />}
      {answer && !answer.isCorrect && <X className="size-4 text-destructive" aria-label="Incorrect" />}
    </li>
  )
}

export function StageLadderCompact({ currentStage, answers, gauntlet }: StageLadderProps) {
  const currentQuestion = gauntlet.find((q) => q.stage === currentStage)
  const currentTier = (currentQuestion?.tier ?? 1) as Tier
  const styles = TIER_STYLES[currentTier] || TIER_STYLES[1]
  const totalStages = gauntlet.length
  const sortedGauntletDescending = [...gauntlet].sort((a, b) => b.stage - a.stage)

  return (
    <div className="border-b border-border bg-sidebar px-4 py-3 lg:hidden">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Hexagon className="size-4 text-primary" aria-hidden="true" />
          <span className="text-sm font-bold">OmniQuest v0</span>
        </div>
        <span className={cn('font-mono text-xs uppercase tracking-widest', styles.text)}>
          Stage {currentStage} / {totalStages} · {styles.label}
        </span>
      </div>
      <ol aria-label={`Stage ladder, ${totalStages} down to 1`} className="mt-3 flex gap-1">
        {sortedGauntletDescending.map((q) => {
          const stageStyles = TIER_STYLES[q.tier as Tier] || TIER_STYLES[1]
          const answer = answers.find((a) => a.stage === q.stage)
          const isCurrent = q.stage === currentStage
          return (
            <li
              key={q.stage}
              aria-current={isCurrent ? 'step' : undefined}
              aria-label={`Stage ${q.stage}`}
              className={cn(
                'h-2 flex-1 rounded-full',
                isCurrent
                  ? cn(stageStyles.bg, stageStyles.glow)
                  : answer
                    ? answer.isCorrect
                      ? stageStyles.bg
                      : 'bg-destructive/70'
                    : stageStyles.softBg,
              )}
            />
          )
        })}
      </ol>
      <div className="mt-1 flex justify-between font-mono text-[10px] text-muted-foreground">
        <span>{totalStages}</span>
        <span>Gauntlet Progress</span>
        <span>1</span>
      </div>
    </div>
  )
}

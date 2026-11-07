'use client'

import { Check, Gamepad2, Gem, LockKeyhole } from 'lucide-react'
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

const ALL_TIERS: Tier[] = [1, 2, 3, 4]

export function StageLadder({ currentStage, answers, gauntlet }: StageLadderProps) {
  const totalStages = gauntlet.length
  const activeTiers = ALL_TIERS.filter((tier) =>
    gauntlet.some((q) => q.tier === tier),
  )

  const progressPercent = Math.min(100, Math.round(((currentStage - 1) / totalStages) * 100))

  return (
    <aside
      aria-label="Stage ladder"
      className="hidden w-[220px] xl:w-[230px] shrink-0 flex-col border-r border-[#1c2745] bg-[#0a1024] px-5 py-6 lg:flex lg:h-full lg:max-h-dvh overflow-hidden"
    >
      {/* Header */}
      <div className="mb-5 flex items-center gap-2 text-xs font-black uppercase tracking-[0.16em] text-[#a98bff] shrink-0">
        <Gamepad2 size={16} />
        <span>Gauntlet ladder</span>
      </div>

      {/* Run Progress Box */}
      <div className="mb-5 rounded-xl border border-[#29385d] bg-[#111a34] p-3 shrink-0">
        <div className="flex justify-between text-[10px] text-[#7783a1]">
          <span>RUN PROGRESS</span>
          <span className="font-bold text-white">
            {Math.min(currentStage, totalStages)} / {totalStages}
          </span>
        </div>
        <div className="mt-2 h-1.5 rounded-full bg-[#202c4c] overflow-hidden">
          <div
            className="h-full rounded-full bg-gradient-to-r from-[#a36bff] to-[#73e4a5] transition-all duration-300"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      {/* Tier & Stage Ladder List */}
      <div className="flex-1 space-y-5 overflow-y-auto pr-1 min-h-0">
        {activeTiers.map((tier) => {
          const questionsForTier = gauntlet
            .filter((q) => q.tier === tier)
            .sort((a, b) => a.stage - b.stage)

          const isLastTierInGauntlet = tier === activeTiers[activeTiers.length - 1]
          const tierLabel = isLastTierInGauntlet ? 'Final tier' : 'Checkpoint'

          return (
            <div key={tier}>
              <div className="mb-2 flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-[#63708d]">
                <span className={TIER_STYLES[tier]?.text || 'text-white'}>
                  Tier {tier}
                </span>
                <span>{tierLabel}</span>
              </div>

              <div className="space-y-1.5">
                {questionsForTier.map((q) => {
                  const stageNum = q.stage
                  const answer = answers.find((a) => a.stage === stageNum)
                  const isDone = stageNum < currentStage || Boolean(answer)
                  const isCurrent = stageNum === currentStage && !answer
                  const isCheckpointStage =
                    (stageNum === 5 || stageNum === 10 || stageNum === 15) &&
                    stageNum < totalStages

                  return (
                    <div
                      key={stageNum}
                      className={cn(
                        'ladder-stage py-1 px-2 rounded-lg transition-colors',
                        isDone && 'done bg-[#111b33]',
                        isCurrent && 'current bg-[#1b1c46] border border-[#7154d8]/40 shadow-[0_0_12px_#7154d822]',
                      )}
                    >
                      <span className="flex size-4 items-center justify-center">
                        {isDone ? (
                          answer?.isCorrect ? (
                            <Check size={13} className="text-[#75e9ae]" />
                          ) : (
                            <span className="text-[#f16e8d] font-bold text-xs">✕</span>
                          )
                        ) : isCurrent ? (
                          <span className="h-2 w-2 rounded-full bg-[#9d73ff] shadow-[0_0_8px_#9d73ff] animate-pulse" />
                        ) : (
                          <LockKeyhole size={11} className="text-[#52607d]" />
                        )}
                      </span>

                      <span className={cn('text-xs', isCurrent ? 'font-bold text-white' : '')}>
                        Stage {stageNum}
                      </span>

                      {isCheckpointStage && (
                        <span title="Tier Checkpoint Gate" className="ml-auto flex items-center">
                          <Gem
                            size={12}
                            className="text-[#e9ad43]"
                            aria-hidden="true"
                          />
                        </span>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
    </aside>
  )
}

export function StageLadderCompact({ currentStage, answers, gauntlet }: StageLadderProps) {
  const totalStages = gauntlet.length
  const currentQuestion = gauntlet.find((q) => q.stage === currentStage)
  const currentTier = (currentQuestion?.tier ?? 1) as Tier
  const styles = TIER_STYLES[currentTier] || TIER_STYLES[1]

  return (
    <div className="border-b border-[#1c2745] bg-[#0a1024]/95 px-4 py-2 backdrop-blur-sm lg:hidden shrink-0">
      <div className="flex items-center justify-between text-xs">
        <span className="font-bold text-white">Gauntlet Progress</span>
        <span className={cn('font-mono text-[11px] font-bold uppercase tracking-wider', styles.text)}>
          Stage {currentStage} / {totalStages} · {styles.label}
        </span>
      </div>

      <ol aria-label={`Stage ladder 1 to ${totalStages}`} className="mt-1.5 flex gap-1">
        {gauntlet.map((q) => {
          const stageStyles = TIER_STYLES[q.tier as Tier] || TIER_STYLES[1]
          const answer = answers.find((a) => a.stage === q.stage)
          const isCurrent = q.stage === currentStage

          return (
            <li
              key={q.stage}
              aria-label={`Stage ${q.stage}`}
              className={cn(
                'h-1.5 flex-1 rounded-full transition-all',
                isCurrent
                  ? 'bg-[#9e67ff] shadow-[0_0_8px_#9e67ff]'
                  : answer
                    ? answer.isCorrect
                      ? 'bg-[#75e9ae]'
                      : 'bg-[#f16e8d]'
                    : 'bg-[#1e2a4a]',
              )}
            />
          )
        })}
      </ol>
    </div>
  )
}
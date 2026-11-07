'use client'

import { Lightbulb, Loader2, Scissors, Snowflake, Target } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { PowerUpId } from '@/lib/quiz-data'

export interface PowerUpItemStatus {
  remaining: number
  max: number
  usedOnStage: boolean
}

export interface PowerupsProps {
  difficulty?: string
  powerUps: Record<PowerUpId, PowerUpItemStatus>
  loadingPowerUps?: Partial<Record<PowerUpId, boolean>>
  disabled: boolean
  score: number
  accuracy: number
  streak: number
  currentStage: number
  totalStages: number
  tierScore?: number
  tierTarget?: number
  onUse: (id: PowerUpId) => void
}

export function Powerups({
  difficulty = 'Medium',
  powerUps,
  loadingPowerUps = {},
  disabled,
  score,
  accuracy,
  streak,
  currentStage,
  totalStages,
  tierScore = 0,
  tierTarget = 300,
  onUse,
}: PowerupsProps) {
  // Find next checkpoint stage (5, 10, 15) strictly less than totalStages
  const nextCheckpoint = [5, 10, 15].find((st) => st >= currentStage && st < totalStages)

  const items = [
    {
      id: 'hint' as PowerUpId,
      label: 'AI Hint',
      desc: 'Reveal a clue',
      icon: Lightbulb,
      tone: 'purple',
    },
    {
      id: 'freeze' as PowerUpId,
      label: 'Time Freeze',
      desc: 'Pause for 5s',
      icon: Snowflake,
      tone: 'blue',
    },
    {
      id: 'fiftyFifty' as PowerUpId,
      label: '50 / 50',
      desc: 'Remove two options',
      icon: Scissors,
      tone: 'gold',
    },
  ]

  return (
    <aside
      aria-label="Power-ups and run stats"
      className="hidden w-[236px] shrink-0 flex-col border-l border-[#1c2745] bg-[#0a1024] p-5 xl:flex h-full overflow-y-auto"
    >
      <div className="flex items-center justify-between mb-4">
        <p className="eyebrow">Power-ups</p>
        <span className="font-mono text-[10px] text-[#6b7897] uppercase tracking-wider">
          {difficulty}
        </span>
      </div>

      {/* Tactical Power-Up Buttons */}
      <div className="space-y-2.5">
        {items.map(({ id, label, desc, icon: Icon, tone }) => {
          const status = powerUps[id] || { remaining: 0, max: 0, usedOnStage: false }
          const { remaining, max, usedOnStage } = status
          const isLoading = loadingPowerUps[id]
          const isUnavailable = max === 0
          const isExhausted = max > 0 && remaining === 0
          const isButtonDisabled = disabled || isUnavailable || isExhausted || usedOnStage || isLoading

          let statusDesc = desc
          if (isUnavailable) {
            statusDesc = `Unavailable on ${difficulty}`
          } else if (isExhausted) {
            statusDesc = 'Exhausted this run'
          } else if (usedOnStage) {
            statusDesc = 'Used this question'
          }

          return (
            <button
              key={id}
              type="button"
              onClick={() => onUse(id)}
              disabled={isButtonDisabled}
              title={
                isUnavailable
                  ? `Not available on ${difficulty} difficulty.`
                  : isExhausted
                  ? 'No charges remaining for this gauntlet run.'
                  : usedOnStage
                  ? 'Already activated on this question.'
                  : `${remaining} of ${max} remaining`
              }
              className={cn(
                'powerup',
                tone,
                (isUnavailable || isExhausted) && 'opacity-40 cursor-not-allowed',
                usedOnStage && 'used opacity-60 cursor-not-allowed',
                isButtonDisabled && !isUnavailable && !isExhausted && !usedOnStage && 'opacity-60 cursor-not-allowed',
              )}
            >
              <span className={cn('power-icon shrink-0', (isUnavailable || isExhausted) && 'grayscale opacity-50')}>
                {isLoading ? (
                  <Loader2 size={16} className="animate-spin text-white" />
                ) : (
                  <Icon size={17} />
                )}
              </span>

              <span className="text-left min-w-0 flex-1">
                <strong className={cn('truncate', (isUnavailable || isExhausted) && 'text-[#6c7895]')}>
                  {label}
                </strong>
                <small className="truncate text-[9px] text-[#75819e]">{statusDesc}</small>
              </span>

              <span
                className={cn(
                  'power-count font-mono shrink-0',
                  (isUnavailable || isExhausted) && 'bg-[#18233d] text-[#556382]',
                  usedOnStage && 'bg-[#293655] text-[#8e9bb5]',
                  !isUnavailable && !isExhausted && remaining > 0 && 'text-[#73e6a8] border border-[#73e6a8]/30',
                )}
              >
                {remaining}/{max}
              </span>
            </button>
          )
        })}
      </div>

      <div className="my-6 h-px bg-[#1c2745]" />

      {/* Run Stats */}
      <p className="eyebrow mb-3">Run stats</p>
      <div className="space-y-3 rounded-xl border border-[#1f2d4f] bg-[#111a34] p-4">
        <div className="flex justify-between text-xs">
          <span className="text-[#7784a0]">Current score</span>
          <strong className="text-white font-mono">+{score.toLocaleString()} IP</strong>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-[#7784a0]">Accuracy</span>
          <strong className="text-[#73e6a8] font-mono">{accuracy}%</strong>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-[#7784a0]">Current streak</span>
          <strong className="text-[#e9ad43] font-mono">{streak}</strong>
        </div>
      </div>

      {/* Checkpoint / Target Card */}
      <div className="mt-4 rounded-xl border border-[#2b3d58] bg-[#12223a] p-4">
        <div className="flex items-center gap-2 text-[#73e6a8]">
          <Target size={16} />
          <span className="text-xs font-black">
            {nextCheckpoint ? `STAGE ${nextCheckpoint} CHECKPOINT` : 'FINAL GAUNTLET RUN'}
          </span>
        </div>
        <p className="mt-2 text-[11px] leading-4 text-[#a0abc1]">
          {nextCheckpoint
            ? `Earn at least ${tierTarget} IP in this tier to unlock the next tier checkpoint.`
            : 'Conquer the final stage to complete the gauntlet.'}
        </p>

        {nextCheckpoint && (
          <div className="mt-3">
            <div className="flex justify-between text-[10px] text-[#707f9c] font-mono mb-1">
              <span>Tier progress</span>
              <span className={tierScore >= tierTarget ? 'text-[#73e6a8] font-bold' : ''}>
                {tierScore} / {tierTarget} IP
              </span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-[#1b2848] overflow-hidden">
              <div
                className={cn(
                  'h-full rounded-full transition-all duration-300',
                  tierScore >= tierTarget ? 'bg-[#73e6a8]' : 'bg-[#9e67ff]',
                )}
                style={{ width: `${Math.min(100, (tierScore / tierTarget) * 100)}%` }}
              />
            </div>
          </div>
        )}
      </div>
    </aside>
  )
}

export function MobilePowerupsBar({
  difficulty = 'Medium',
  powerUps,
  loadingPowerUps = {},
  disabled,
  onUse,
}: {
  difficulty?: string
  powerUps: Record<PowerUpId, PowerUpItemStatus>
  loadingPowerUps?: Partial<Record<PowerUpId, boolean>>
  disabled: boolean
  onUse: (id: PowerUpId) => void
}) {
  const items = [
    { id: 'hint' as PowerUpId, label: 'Hint', icon: Lightbulb, tone: 'purple' },
    { id: 'freeze' as PowerUpId, label: 'Freeze', icon: Snowflake, tone: 'blue' },
    { id: 'fiftyFifty' as PowerUpId, label: '50/50', icon: Scissors, tone: 'gold' },
  ]

  return (
    <div className="xl:hidden shrink-0 border-t border-[#1c2745] bg-[#0b1126]/95 px-4 py-2 backdrop-blur-md">
      <div className="grid grid-cols-3 gap-2">
        {items.map(({ id, label, icon: Icon, tone }) => {
          const status = powerUps[id] || { remaining: 0, max: 0, usedOnStage: false }
          const { remaining, max, usedOnStage } = status
          const isLoading = loadingPowerUps[id]
          const isUnavailable = max === 0
          const isExhausted = max > 0 && remaining === 0
          const isButtonDisabled = disabled || isUnavailable || isExhausted || usedOnStage || isLoading

          return (
            <button
              key={id}
              type="button"
              onClick={() => onUse(id)}
              disabled={isButtonDisabled}
              title={
                isUnavailable
                  ? `Unavailable on ${difficulty}`
                  : isExhausted
                  ? 'Exhausted this run'
                  : usedOnStage
                  ? 'Used this question'
                  : `${remaining}/${max} available`
              }
              className={cn(
                'flex items-center justify-between gap-1 rounded-lg border border-[#29385a] bg-[#111a34] px-2 py-1.5 text-xs font-bold transition-colors',
                tone === 'purple' && 'text-[#b38dff]',
                tone === 'blue' && 'text-[#7cc5ff]',
                tone === 'gold' && 'text-[#efbb61]',
                (isUnavailable || isExhausted) && 'opacity-35 cursor-not-allowed',
                usedOnStage && 'opacity-50 cursor-not-allowed',
                isButtonDisabled && !isUnavailable && !isExhausted && !usedOnStage && 'opacity-60',
              )}
            >
              <div className="flex items-center gap-1.5 min-w-0 truncate">
                {isLoading ? (
                  <Loader2 size={13} className="animate-spin shrink-0" />
                ) : (
                  <Icon size={14} className="shrink-0" />
                )}
                <span className="truncate">{label}</span>
              </div>
              <span className="font-mono text-[10px] text-[#7e8ca8] shrink-0">
                {remaining}/{max}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

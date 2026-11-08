'use client'

import { Clock3, Flame, Gem, Snowflake, Timer } from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  QUESTION_TIME_LIMIT_MS,
  TIER_TARGET_IP,
  type Tier,
} from '@/lib/quiz-data'

interface ArenaTopBarProps {
  topic: string
  difficulty?: string
  stageNumber: number
  totalStages: number
  score: number
  streak?: number
  streakFireActive?: boolean
  timeLeftMs: number
  isFrozen: boolean
  currentTier?: Tier
  tierScore?: number
  tierTarget?: number | null
  onForfeitClick?: () => void
}

export function ArenaTopBar({
  topic,
  difficulty = 'Medium',
  stageNumber,
  totalStages,
  score,
  streak = 0,
  streakFireActive = false,
  timeLeftMs,
  isFrozen,
  currentTier,
  tierScore = 0,
  tierTarget = null,
  onForfeitClick,
}: ArenaTopBarProps) {
  const secondsLeft = Math.ceil(timeLeftMs / 1000)
  const isCritical = !isFrozen && secondsLeft <= 5

  const mins = Math.floor(secondsLeft / 60)
    .toString()
    .padStart(2, '0')
  const secs = (secondsLeft % 60).toString().padStart(2, '0')

  return (
    <header className="flex h-[72px] sm:h-[82px] shrink-0 items-center justify-between border-b border-[#1c2745] bg-[#0b1126] px-4 sm:px-8">
      {/* Topic & Context */}
      <div className="min-w-0 pr-2">
        <p className="eyebrow truncate">Knowledge gauntlet</p>
        <p className="mt-0.5 sm:mt-1 truncate text-xs sm:text-sm font-black text-white">
          {topic}
          <span className="mx-1.5 sm:mx-2 text-[#465271]">/</span>
          <span className="text-[#9b82f3] capitalize">{difficulty}</span>
        </p>
      </div>

      {/* Stats & Actions */}
      <div className="flex items-center gap-2.5 sm:gap-6">
        {/* Streak Indicator */}
        <div
          className={cn(
            'flex items-center gap-1.5 text-xs sm:text-sm font-bold transition-all',
            streakFireActive
              ? 'text-[#ff9d4d] drop-shadow-[0_0_12px_#ff9d4d]'
              : streak > 0
                ? 'text-[#e9ad43]'
                : 'text-[#697593]',
          )}
          title={streakFireActive ? 'Streak Fire Active (+50 IP Bonus)!' : `${streak} answer streak`}
        >
          <Flame
            size={18}
            className={cn(streakFireActive && 'animate-pulse text-[#ff9d4d]')}
            fill="currentColor"
          />
          <span className="font-mono">
            {streak} {streak === 1 ? 'streak' : 'streak'}
          </span>
          {streakFireActive && (
            <span className="hidden md:inline rounded bg-[#4c2e2a] px-1.5 py-0.5 text-[9px] font-black tracking-wider text-[#ffad63]">
              FIRE
            </span>
          )}
        </div>

        {/* Current Insight Points pill */}
        <div className="hidden sm:flex items-center gap-1.5 rounded-lg border border-[#273354] bg-[#111932] px-2.5 py-1.5 text-xs font-mono text-white">
          <Gem size={14} className="text-[#e9ad43]" />
          <span className="font-bold tabular-nums">{score.toLocaleString()}</span>
          <span className="text-[10px] text-[#73809e]">IP</span>
        </div>

        {/* Tier Progression pill */}
        <div
          className="hidden md:flex items-center gap-1.5 rounded-lg border border-[#273354] bg-[#111932] px-2.5 py-1.5 text-xs font-mono text-white"
          title={
            tierTarget === null || tierTarget === 0
              ? 'Tier Progression: No IP requirement'
              : `Tier Progression: ${tierScore} / ${tierTarget} IP (${
                  tierScore >= tierTarget
                    ? 'Qualified'
                    : `${Math.min(100, Math.round((tierScore / tierTarget) * 100))}%`
                })`
          }
        >
          <span className="text-[10px] uppercase font-bold text-[#9e67ff]">
            {currentTier ? `T${currentTier}` : 'Tier'}
          </span>
          <span
            className={cn(
              'font-bold tabular-nums',
              tierTarget !== null && tierTarget > 0 && tierScore >= tierTarget
                ? 'text-[#73e6a8]'
                : 'text-[#c2cbde]',
            )}
          >
            {tierTarget === null || tierTarget === 0
              ? 'No req'
              : `${tierScore}/${tierTarget}`}
          </span>
          <span className="text-[10px] text-[#73809e]">IP</span>
        </div>

        {/* Countdown Timer */}
        <div
          className={cn(
            'flex items-center gap-2 rounded-lg border px-3 py-1.5 font-mono text-xs sm:text-sm font-bold transition-colors',
            isFrozen
              ? 'border-[#2d4b7a] bg-[#162744] text-[#7cc5ff] shadow-[0_0_12px_#7cc5ff33]'
              : isCritical
                ? 'border-[#752a3d] bg-[#3a1622] text-[#f16e8d] animate-pulse shadow-[0_0_12px_#f16e8d33]'
                : 'border-[#704c5b] bg-[#251b2b] text-[#ffbb67]',
          )}
          aria-label={`Time remaining: ${secondsLeft} seconds`}
        >
          {isFrozen ? (
            <>
              <Snowflake size={15} className="animate-spin" />
              <span>FROZEN</span>
            </>
          ) : (
            <>
              <Clock3 size={15} />
              <span>{mins}:{secs}</span>
            </>
          )}
        </div>

        {/* Forfeit Run Button */}
        {onForfeitClick && (
          <button
            type="button"
            onClick={onForfeitClick}
            className="text-[10px] sm:text-[11px] font-black uppercase tracking-wider text-[#7784a0] hover:text-[#ff818d] transition-colors py-1 px-1.5 rounded focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#f16e8d]"
            aria-label="Forfeit active run"
          >
            Forfeit <span className="hidden sm:inline">run</span>
          </button>
        )}
      </div>
    </header>
  )
}
'use client'

import { useEffect, useState } from 'react'
import {
  Award,
  BookOpen,
  Brain,
  Check,
  Flame,
  Gamepad2,
  Gem,
  History,
  LockKeyhole,
  Play,
  Target,
  Trophy,
} from 'lucide-react'
import {
  formatDuration,
  getGameHistory,
  getPlayerStats,
  type GameRunRecord,
  type PlayerStats,
} from '@/lib/game-storage'
import { cn } from '@/lib/utils'

interface TrophyRoomProps {
  initialTab?: 'trophies' | 'history'
  onPlay?: () => void
}

export function TrophyRoom({ initialTab = 'trophies', onPlay }: TrophyRoomProps) {
  const [stats, setStats] = useState<PlayerStats | null>(null)
  const [history, setHistory] = useState<GameRunRecord[]>([])
  const [activeTab, setActiveTab] = useState<'trophies' | 'history'>(initialTab)

  useEffect(() => {
    setStats(getPlayerStats())
    setHistory(getGameHistory())
  }, [])

  useEffect(() => {
    setActiveTab(initialTab)
  }, [initialTab])

  if (!stats) return null

  return (
    <main className="flex-1 overflow-y-auto bg-[#080e20] p-4 sm:p-8">
      <div className="mx-auto max-w-[1050px] pb-12 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div>
            <p className="eyebrow">Your collection</p>
            <h1 className="mt-1 text-2xl sm:text-3xl font-black text-white">Trophy Room & History</h1>
            <p className="mt-1.5 text-xs sm:text-sm text-[#7d89a6]">
              Every run leaves a mark. Build your knowledge streak and unlock arena milestones.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="rounded-xl border border-[#2b3b60] bg-[#111a34] px-4 py-2.5 text-right">
              <p className="text-[10px] text-[#74809c] font-bold uppercase tracking-wider">TOTAL IP BANKED</p>
              <strong className="text-base sm:text-lg text-[#e9ad43] font-mono">
                {stats.totalIp.toLocaleString()} IP
              </strong>
            </div>

            {onPlay && (
              <button
                type="button"
                onClick={onPlay}
                className="primary-button text-xs py-2.5 px-4"
              >
                <Play size={13} fill="currentColor" /> Play Gauntlet
              </button>
            )}
          </div>
        </div>

        {/* Top 4 Real Player Metrics */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="trophy-metric">
            <Trophy size={18} className="text-[#9e67ff]" />
            <strong className="font-mono text-lg sm:text-xl">{stats.gamesPlayed}</strong>
            <span>games played</span>
          </div>

          <div className="trophy-metric">
            <Flame size={18} className="text-[#ff9d4d]" />
            <strong className="font-mono text-lg sm:text-xl">{stats.highestStreak}</strong>
            <span>highest streak</span>
          </div>

          <div className="trophy-metric">
            <Target size={18} className="text-[#75e9ae]" />
            <strong className="font-mono text-lg sm:text-xl">{stats.bestAccuracy}%</strong>
            <span>best accuracy</span>
          </div>

          <div className="trophy-metric">
            <Award size={18} className="text-[#e9ad43]" />
            <strong className="font-mono text-lg sm:text-xl">
              {stats.unlockedAchievementsCount} / {stats.achievements.length}
            </strong>
            <span>milestones unlocked</span>
          </div>
        </div>

        {/* Mobile Tab Filter */}
        <div className="flex border-b border-[#1c2745] gap-2 lg:hidden">
          <button
            type="button"
            onClick={() => setActiveTab('trophies')}
            className={cn(
              'pb-2.5 px-3 text-xs font-bold border-b-2 transition-colors',
              activeTab === 'trophies'
                ? 'border-[#9e67ff] text-white'
                : 'border-transparent text-[#74809c]',
            )}
          >
            Milestones ({stats.unlockedAchievementsCount}/{stats.achievements.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('history')}
            className={cn(
              'pb-2.5 px-3 text-xs font-bold border-b-2 transition-colors',
              activeTab === 'history'
                ? 'border-[#9e67ff] text-white'
                : 'border-transparent text-[#74809c]',
            )}
          >
            Game History ({history.length})
          </button>
        </div>

        {/* Milestones & Game History Grid */}
        <div className="grid gap-6 lg:grid-cols-[1.25fr_0.75fr]">
          {/* Section 1: Milestones Collection */}
          <section
            className={cn(
              'panel p-5 sm:p-6 space-y-4',
              activeTab !== 'trophies' && 'hidden lg:block',
            )}
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="eyebrow">Milestones</p>
                <h2 className="mt-1 text-base sm:text-lg font-black text-white">Achievement Collection</h2>
              </div>
              <span className="rounded-full bg-[#263458] px-2.5 py-1 text-[10px] font-bold text-[#9dafcd]">
                {stats.unlockedAchievementsCount} / {stats.achievements.length} unlocked
              </span>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 pt-1">
              {stats.achievements.map((ach) => {
                const IconComponent =
                  ach.id === 'combo-starter'
                    ? Flame
                    : ach.id === 'sharp-mind'
                      ? Brain
                      : ach.id === 'point-hoarder'
                        ? Gem
                        : Target

                return (
                  <div
                    key={ach.id}
                    className={cn(
                      'achievement transition-all',
                      !ach.unlocked && 'locked opacity-50 bg-[#0d1428]',
                    )}
                  >
                    <div className={`achievement-icon ${ach.color} shrink-0`}>
                      <IconComponent size={20} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <strong className="truncate block text-xs sm:text-sm text-white">
                        {ach.title}
                      </strong>
                      <p className="text-[10px] sm:text-[11px] leading-tight text-[#7784a0] mt-0.5">
                        {ach.desc}
                      </p>
                    </div>
                    {ach.unlocked ? (
                      <Check size={16} className="ml-auto text-[#73e6a8] shrink-0" />
                    ) : (
                      <LockKeyhole size={15} className="ml-auto text-[#6c7894] shrink-0" />
                    )}
                  </div>
                )
              })}
            </div>
          </section>

          {/* Section 2: Recent Game History */}
          <section
            className={cn(
              'panel p-5 sm:p-6 space-y-4',
              activeTab !== 'history' && 'hidden lg:block',
            )}
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="eyebrow">Recent runs</p>
                <h2 className="mt-1 text-base sm:text-lg font-black text-white">Game History</h2>
              </div>
              <span className="text-[11px] font-mono text-[#74809d]">
                {history.length} {history.length === 1 ? 'run' : 'runs'}
              </span>
            </div>

            {history.length === 0 ? (
              <div className="rounded-xl border border-dashed border-[#243354] bg-[#0c1328]/50 p-8 text-center space-y-3">
                <Gamepad2 size={28} className="mx-auto text-[#5b6887]" />
                <div>
                  <p className="text-xs font-bold text-white">No game history yet</p>
                  <p className="text-[11px] text-[#74809d] mt-1 max-w-[260px] mx-auto">
                    Complete your first learning gauntlet to start recording your scores, streaks, and accuracy.
                  </p>
                </div>
                {onPlay && (
                  <button
                    type="button"
                    onClick={onPlay}
                    className="secondary-button text-[10px] py-1.5 px-3"
                  >
                    <Play size={12} fill="currentColor" /> Enter the Arena
                  </button>
                )}
              </div>
            ) : (
              <div className="space-y-3 max-h-[380px] overflow-y-auto pr-1">
                {history.map((run) => (
                  <div key={run.id} className="history-row">
                    <div className="history-icon shrink-0">
                      <BookOpen size={15} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <strong className="truncate block text-xs sm:text-sm text-white">
                        {run.topic}
                      </strong>
                      <small className="truncate block text-[#73809c] text-[10px]">
                        {run.date} · {run.stagesCompleted}/{run.totalStages} stages
                        {run.isForfeit && ' (Forfeited)'}
                      </small>
                    </div>
                    <div className="text-right shrink-0">
                      <strong className="text-[#e9ad43] font-mono text-xs sm:text-sm">
                        +{run.score.toLocaleString()} IP
                      </strong>
                      <small className="text-[#73e6a8] font-mono block text-[10px]">
                        {run.accuracy}% accuracy
                      </small>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </main>
  )
}

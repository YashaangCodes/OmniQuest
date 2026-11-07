'use client'

import { useEffect, useRef, useState } from 'react'
import {
  Check,
  Clock3,
  Flag,
  Flame,
  Gem,
  Home,
  LockKeyhole,
  RotateCcw,
  Share2,
  ShieldAlert,
  Star,
  Target,
  Trophy,
  X,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { AnswerRecord, TierElimination } from '@/lib/quiz-data'
import { saveCompletedGame } from '@/lib/game-storage'

interface ResultsScreenProps {
  topic: string
  difficulty?: string
  answers: AnswerRecord[]
  totalStages?: number
  elimination?: TierElimination | null
  isForfeit?: boolean
  onPlayAgain: () => void
  onHome?: () => void
  onTrophies?: () => void
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
  difficulty = 'Medium',
  answers,
  totalStages,
  elimination,
  isForfeit = false,
  onPlayAgain,
  onHome,
  onTrophies,
}: ResultsScreenProps) {
  const [shareStatus, setShareStatus] = useState<'idle' | 'copied' | 'error'>('idle')
  const resetTimeoutRef = useRef<number | null>(null)
  const hasSavedRef = useRef<boolean>(false)

  const totalStagesCount = totalStages ?? answers.length
  const totalPoints = answers.reduce((total, answer) => total + answer.pointsEarned, 0)
  const correctCount = answers.filter((answer) => answer.isCorrect).length
  const missedCount = answers.length - correctCount
  const accuracy = answers.length ? Math.round((correctCount / answers.length) * 100) : 0
  const totalDurationSeconds = Math.round(
    answers.reduce((total, answer) => total + answer.responseTimeMs, 0) / 1000,
  )

  // Persist completed game run to localStorage once on mount
  useEffect(() => {
    if (!hasSavedRef.current && answers.length > 0) {
      hasSavedRef.current = true
      saveCompletedGame({
        topic,
        difficulty,
        stagesCompleted: answers.length,
        totalStages: totalStagesCount,
        score: totalPoints,
        accuracy,
        correctCount,
        bestStreak: getBestStreak(answers),
        durationSeconds: totalDurationSeconds,
        isForfeit,
      })
    }
  }, [answers, topic, difficulty, totalStagesCount, totalPoints, accuracy, correctCount, totalDurationSeconds, isForfeit])

  useEffect(() => {
    return () => {
      if (resetTimeoutRef.current !== null) window.clearTimeout(resetTimeoutRef.current)
    }
  }, [])

  const mins = Math.floor(totalDurationSeconds / 60)
    .toString()
    .padStart(2, '0')
  const secs = (totalDurationSeconds % 60).toString().padStart(2, '0')
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

  // Milestones
  const unlockedSharpMind = answers.length >= 5
  const unlockedComboStarter = bestStreak >= 3
  const unlockedPerfectRecall = answers.length > 0 && accuracy === 100

  return (
    <main className="results-bg flex-1 overflow-y-auto p-4 sm:p-10">
      <div className="mx-auto max-w-[920px] pb-12">
        {/* Header with Status Trophy/Badge */}
        <div className="mb-8 text-center">
          <div
            className={cn(
              'mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl border text-white shadow-lg',
              isForfeit
                ? 'border-[#704c5b] bg-[#251b2b] text-[#ffbb67]'
                : isEliminated
                  ? 'border-[#bd566b] bg-[#3e1d32] text-[#f16e8d]'
                  : 'border-[#7256bd] bg-[#2c205d] text-[#d3baff] shadow-[0_0_30px_#7256bd55]',
            )}
          >
            {isForfeit ? (
              <Flag size={30} />
            ) : isEliminated ? (
              <ShieldAlert size={30} />
            ) : (
              <Trophy size={30} />
            )}
          </div>

          <p className="eyebrow">
            {isForfeit ? 'Run forfeited' : isEliminated ? 'Elimination checkpoint' : 'Run complete'}
          </p>

          <h1 className="mt-2 text-3xl font-black text-white sm:text-4xl">
            {isForfeit
              ? 'Run Forfeited'
              : isEliminated && elimination
                ? `Eliminated in Tier ${elimination.tier}`
                : isVictory
                  ? 'That was a legendary run.'
                  : 'Gauntlet Completed.'}
          </h1>

          <p className="mt-2 text-sm text-[#8490ad]">
            {isForfeit
              ? 'You voluntarily ended this run. All accumulated IP and completed stats have been saved.'
              : isEliminated && elimination
                ? `You earned ${elimination.earnedIp} of the ${elimination.requiredIp} IP required to advance past the checkpoint.`
                : 'You stayed focused, answered quickly, and conquered the gauntlet.'}
          </p>
        </div>

        {/* Score Card Panel */}
        <div className="score-card panel">
          <p className="eyebrow">Final insight points</p>
          <div className="mt-2 text-5xl sm:text-6xl font-black tracking-[-0.06em] text-white">
            {totalPoints.toLocaleString()}
            <span className="ml-2 text-xl text-[#e9ad43]">IP</span>
          </div>

          <div className="mt-5 h-2 rounded-full bg-[#222f52] overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-[#8960ed] to-[#73e6a8] transition-all duration-500"
              style={{
                width: `${Math.min(100, Math.max(10, (totalPoints / (totalStagesCount * 150)) * 100))}%`,
              }}
            />
          </div>

          <div className="mt-2 flex justify-between text-[10px] text-[#73809f]">
            <span>{answers.length} of {totalStagesCount} stages completed</span>
            <span>Topic: {topic}</span>
          </div>
        </div>

        {/* 4 Stat Cards */}
        <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="result-stat">
            <Check size={17} className="text-[#73e6a8]" />
            <strong>
              {correctCount} / {answers.length}
            </strong>
            <span>correct answers</span>
          </div>

          <div className="result-stat">
            <Target size={17} className="text-[#a582ff]" />
            <strong>{accuracy}%</strong>
            <span>accuracy</span>
          </div>

          <div className="result-stat">
            <Flame size={17} className="text-[#ff9f53]" />
            <strong>{bestStreak}</strong>
            <span>highest streak</span>
          </div>

          <div className="result-stat">
            <Clock3 size={17} className="text-[#e9ad43]" />
            <strong>{mins}:{secs}</strong>
            <span>run duration</span>
          </div>
        </div>

        {/* 2-Column Performance Summary & Rewards */}
        <div className="mt-5 grid gap-5 md:grid-cols-[1fr_1fr]">
          {/* Performance Summary Donut */}
          <div className="panel p-6">
            <p className="eyebrow">Performance summary</p>
            <div className="mt-6 flex items-center justify-center">
              <div
                className="score-donut"
                style={{
                  borderRightColor: accuracy < 50 ? '#f36e82' : '#73e6a8',
                  borderBottomColor: accuracy < 75 ? '#f36e82' : '#73e6a8',
                }}
              >
                <div>
                  <strong>{accuracy}%</strong>
                  <span>accuracy</span>
                </div>
              </div>
            </div>

            <div className="mt-5 flex justify-center gap-5 text-[10px] text-[#8591ad]">
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-[#73e6a8]" /> Correct {correctCount}
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-[#f36e82]" /> Missed {missedCount}
              </span>
            </div>
          </div>

          {/* Rewards Unlocked */}
          <div className="panel p-6">
            <p className="eyebrow">Rewards unlocked</p>
            <div className="mt-4 space-y-3">
              <div className={cn('reward-row', !unlockedSharpMind && 'opacity-50')}>
                <span className="reward-icon">
                  <Star size={17} />
                </span>
                <span>
                  <strong>Sharp Mind</strong>
                  <small>Complete at least 5 stages</small>
                </span>
                {unlockedSharpMind ? (
                  <Check size={16} className="ml-auto text-[#73e6a8]" />
                ) : (
                  <LockKeyhole size={15} className="ml-auto text-[#6f7b98]" />
                )}
              </div>

              <div className={cn('reward-row', !unlockedComboStarter && 'opacity-50')}>
                <span className="reward-icon gold">
                  <Flame size={17} />
                </span>
                <span>
                  <strong>Combo Starter</strong>
                  <small>Reach a 3 answer streak</small>
                </span>
                {unlockedComboStarter ? (
                  <Check size={16} className="ml-auto text-[#73e6a8]" />
                ) : (
                  <LockKeyhole size={15} className="ml-auto text-[#6f7b98]" />
                )}
              </div>

              <div className={cn('reward-row', !unlockedPerfectRecall && 'opacity-50')}>
                <span className="reward-icon">
                  <Gem size={17} />
                </span>
                <span>
                  <strong>Perfect Recall</strong>
                  <small>Answer every stage correctly</small>
                </span>
                {unlockedPerfectRecall ? (
                  <Check size={16} className="ml-auto text-[#73e6a8]" />
                ) : (
                  <LockKeyhole size={15} className="ml-auto text-[#6f7b98]" />
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Detailed Stage Breakdown */}
        <section aria-labelledby="breakdown-heading" className="mt-8 panel p-6">
          <h2 id="breakdown-heading" className="eyebrow mb-4">
            Stage-by-stage breakdown
          </h2>

          {answers.length === 0 ? (
            <p className="py-4 text-center text-xs text-[#8490ad]">
              No stages were completed in this run.
            </p>
          ) : (
            <div className="space-y-3">
              {answers.map((answer) => (
                <div
                  key={answer.questionId}
                  className="flex items-start gap-3.5 rounded-xl border border-[#202f51] bg-[#111931] p-3.5"
                >
                  <span
                    className={cn(
                      'flex size-8 shrink-0 items-center justify-center rounded-lg text-xs font-bold',
                      answer.isCorrect
                        ? 'bg-[#153c37] text-[#75e9ae] border border-[#57c88e]/40'
                        : 'bg-[#3e1d32] text-[#f16e8d] border border-[#bd566b]/40',
                    )}
                  >
                    {answer.isCorrect ? <Check size={16} /> : <X size={16} />}
                  </span>

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 text-[10px] font-mono text-[#7784a0]">
                      <span>STAGE {answer.stage}</span>
                      <span>·</span>
                      <span className="tabular-nums">
                        {(answer.responseTimeMs / 1000).toFixed(1)}s
                      </span>
                    </div>

                    <p className="mt-1 text-xs sm:text-sm font-bold text-white leading-snug">
                      {answer.prompt}
                    </p>

                    <p className="mt-1.5 text-xs text-[#8490ad]">
                      <span>Your choice: </span>
                      <span
                        className={
                          answer.isCorrect ? 'text-[#75e9ae] font-bold' : 'text-[#f16e8d] font-bold'
                        }
                      >
                        {answer.selectedAnswer ?? 'Timed out'}
                      </span>
                      {!answer.isCorrect && (
                        <>
                          <span className="mx-2 text-[#465271]">·</span>
                          <span>Correct: </span>
                          <span className="text-[#75e9ae] font-bold">{answer.correctAnswer}</span>
                        </>
                      )}
                    </p>

                    {answer.explanation && (
                      <p className="mt-2 text-[11px] leading-relaxed text-[#9aa7c3] border-t border-[#1c2745] pt-1.5">
                        <strong className="text-white">Explanation: </strong>
                        {answer.explanation}
                      </p>
                    )}
                  </div>

                  <div className="shrink-0 text-right">
                    <span className="font-mono text-xs font-bold text-[#e9ad43]">
                      +{answer.pointsEarned} IP
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Action Buttons */}
        <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
          <button
            type="button"
            onClick={onPlayAgain}
            className="primary-button justify-center"
          >
            <RotateCcw size={16} /> Play again
          </button>

          {onHome && (
            <button
              type="button"
              onClick={onHome}
              className="secondary-button justify-center"
            >
              <Home size={16} /> Return home
            </button>
          )}

          {onTrophies && (
            <button
              type="button"
              onClick={onTrophies}
              className="secondary-button justify-center"
            >
              <Trophy size={16} /> Trophy room
            </button>
          )}

          <button
            type="button"
            onClick={handleShare}
            className="secondary-button justify-center"
          >
            <Share2 size={16} />
            {shareStatus === 'copied'
              ? 'Score copied!'
              : shareStatus === 'error'
                ? 'Unable to copy'
                : 'Share score'}
          </button>
        </div>
      </div>
    </main>
  )
}
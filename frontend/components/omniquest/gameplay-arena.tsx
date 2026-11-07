'use client'

import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, Flag, Trophy, X } from 'lucide-react'
import {
  TIER_TARGET_IP,
  getPowerUpLimits,
  getQuestionTier,
  getTierEarnedIP,
  isTierGateStage,
  type AnswerRecord,
  type PowerUpId,
  type PublicQuestion,
  type Tier,
  type TierElimination,
} from '@/lib/quiz-data'
import { forfeitGame } from '@/lib/api'
import { QuestionRound } from './question-round'
import { StageLadder, StageLadderCompact } from './stage-ladder'

interface GameplayArenaProps {
  sessionId: string
  topic: string
  difficulty?: string
  gauntlet: PublicQuestion[]
  fallbackMessage?: string
  onComplete: (
    answers: AnswerRecord[],
    elimination?: TierElimination | null,
    isForfeit?: boolean,
  ) => void
}

export function GameplayArena({
  sessionId,
  topic,
  difficulty = 'Medium',
  gauntlet,
  fallbackMessage,
  onComplete,
}: GameplayArenaProps) {
  const [questionIndex, setQuestionIndex] = useState(0)
  const [answers, setAnswers] = useState<AnswerRecord[]>([])
  const [streak, setStreak] = useState(0)
  const [streakFireActive, setStreakFireActive] = useState(false)

  // Official power-up limits determined by the run's selected difficulty
  const maxLimits = getPowerUpLimits(difficulty)

  // Track remaining power-up charges for this entire run
  const [remainingPowerUps, setRemainingPowerUps] = useState<Record<PowerUpId, number>>({
    hint: maxLimits.hint,
    freeze: maxLimits.freeze,
    fiftyFifty: maxLimits.fiftyFifty,
  })

  // Track power-ups activated on the current question/stage (prevent re-use on same question)
  const [usedOnCurrentStage, setUsedOnCurrentStage] = useState<Record<PowerUpId, boolean>>({
    hint: false,
    freeze: false,
    fiftyFifty: false,
  })

  const [tierClearedInfo, setTierClearedInfo] = useState<{
    tier: Tier
    earnedIp: number
  } | null>(null)
  const [isForfeitDialogOpen, setIsForfeitDialogOpen] = useState(false)
  const tierClearedTimerRef = useRef<number | null>(null)

  function handleUsePowerUp(id: PowerUpId, nextRemaining?: number) {
    setRemainingPowerUps((prev) => ({
      ...prev,
      [id]: typeof nextRemaining === 'number' ? nextRemaining : Math.max(0, prev[id] - 1),
    }))
    setUsedOnCurrentStage((prev) => ({
      ...prev,
      [id]: true,
    }))
  }

  const powerUpStatus: Record<
    PowerUpId,
    { remaining: number; max: number; usedOnStage: boolean }
  > = {
    hint: {
      remaining: remainingPowerUps.hint,
      max: maxLimits.hint,
      usedOnStage: usedOnCurrentStage.hint,
    },
    freeze: {
      remaining: remainingPowerUps.freeze,
      max: maxLimits.freeze,
      usedOnStage: usedOnCurrentStage.freeze,
    },
    fiftyFifty: {
      remaining: remainingPowerUps.fiftyFifty,
      max: maxLimits.fiftyFifty,
      usedOnStage: usedOnCurrentStage.fiftyFifty,
    },
  }

  useEffect(() => {
    return () => {
      if (tierClearedTimerRef.current !== null) {
        window.clearTimeout(tierClearedTimerRef.current)
      }
    }
  }, [])

  // Close forfeit modal on Escape key
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape' && isForfeitDialogOpen) {
        setIsForfeitDialogOpen(false)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isForfeitDialogOpen])

  const question = gauntlet[questionIndex]
  const currentStage = question.stage
  const currentTier = getQuestionTier(currentStage, gauntlet)
  const score = answers.reduce((total, answer) => total + answer.pointsEarned, 0)
  const baseTierScore = getTierEarnedIP(currentTier, answers, gauntlet)

  function handleRoundComplete(
    record: AnswerRecord,
    streakInfo?: { streak: number; streakFireActive: boolean },
  ) {
    const nextAnswers = [...answers, record]
    if (streakInfo) {
      setStreak(streakInfo.streak)
      setStreakFireActive(streakInfo.streakFireActive)
    }

    const isTierGate = isTierGateStage(currentStage, gauntlet.length)

    if (isTierGate) {
      // Include the IP earned for that final question of the tier
      const tierEarnedIp = getTierEarnedIP(currentTier, nextAnswers, gauntlet)

      if (tierEarnedIp < TIER_TARGET_IP) {
        // If tier IP is below 300, eliminate immediately and show results
        onComplete(nextAnswers, {
          tier: currentTier,
          earnedIp: tierEarnedIp,
          requiredIp: TIER_TARGET_IP,
        })
        return
      }

      // If tier IP is at least 300, show Tier Cleared modal, then advance
      setAnswers(nextAnswers)
      setTierClearedInfo({ tier: currentTier, earnedIp: tierEarnedIp })
      setUsedOnCurrentStage({ hint: false, freeze: false, fiftyFifty: false })

      tierClearedTimerRef.current = window.setTimeout(() => {
        setTierClearedInfo(null)
        setQuestionIndex((index) => index + 1)
      }, 1800)
      return
    }

    if (questionIndex >= gauntlet.length - 1) {
      // Completion of the gauntlet!
      onComplete(nextAnswers)
      return
    }

    setAnswers(nextAnswers)
    setUsedOnCurrentStage({ hint: false, freeze: false, fiftyFifty: false })
    setQuestionIndex((index) => index + 1)
  }

  function handleConfirmForfeit() {
    setIsForfeitDialogOpen(false)
    // Asynchronously notify backend that the game has ended via forfeit
    forfeitGame(sessionId).catch(() => {})
    // End active run immediately, preserving accumulated answers and score
    onComplete(answers, null, true)
  }

  return (
    <div className="flex h-dvh max-h-dvh w-full flex-col overflow-hidden bg-[#080e20] lg:flex-row">
      {/* Desktop Gauntlet Ladder Sidebar (Left Column) */}
      <StageLadder currentStage={currentStage} answers={answers} gauntlet={gauntlet} />

      {/* Main Gameplay Viewport */}
      <div className="relative flex h-full min-h-0 flex-1 flex-col overflow-hidden">
        {fallbackMessage && (
          <aside
            aria-label="Fallback notification"
            className="flex shrink-0 items-center justify-center gap-2 border-b border-amber-500/30 bg-amber-500/10 px-4 py-2 text-center text-xs font-mono text-amber-300"
          >
            <AlertTriangle className="size-4 shrink-0 text-amber-400" aria-hidden="true" />
            <span>{fallbackMessage}</span>
          </aside>
        )}

        {/* Compact Mobile Ladder Bar (< lg) */}
        <StageLadderCompact currentStage={currentStage} answers={answers} gauntlet={gauntlet} />

        {/* Question Round (Center & Right Columns) */}
        <QuestionRound
          key={`${sessionId}-stage-${question.stage}`}
          sessionId={sessionId}
          topic={topic}
          difficulty={difficulty}
          question={question}
          stage={currentStage}
          questionNumber={questionIndex + 1}
          totalQuestions={gauntlet.length}
          score={score}
          tierScore={baseTierScore}
          tierTarget={TIER_TARGET_IP}
          streak={streak}
          streakFireActive={streakFireActive}
          powerUps={powerUpStatus}
          onUsePowerUp={handleUsePowerUp}
          onComplete={handleRoundComplete}
          onForfeit={() => setIsForfeitDialogOpen(true)}
          isForfeitDialogOpen={isForfeitDialogOpen}
        />
      </div>

      {/* Tier Cleared Modal Dialog */}
      {tierClearedInfo && (
        <aside
          role="dialog"
          aria-modal="true"
          aria-label={`Tier ${tierClearedInfo.tier} Cleared`}
          className="fixed inset-0 z-50 flex items-center justify-center bg-[#050916]/80 p-4 backdrop-blur-md animate-in fade-in duration-200"
        >
          <div className="relative flex w-full max-w-md flex-col items-center rounded-2xl border-2 border-[#75e9ae] bg-[#101a34] p-8 text-center shadow-[0_0_64px_-12px_#75e9ae55]">
            <div className="flex size-16 items-center justify-center rounded-2xl border border-[#75e9ae]/60 bg-[#75e9ae]/15 text-[#75e9ae] shadow-[0_0_32px_-4px_#75e9ae]">
              <Trophy className="size-8" aria-hidden="true" />
            </div>
            <p className="mt-4 font-mono text-xs uppercase tracking-widest text-[#75e9ae]">
              Tier {tierClearedInfo.tier} Complete
            </p>
            <h2 className="mt-2 text-3xl font-black tracking-tight text-white">
              Tier Cleared!
            </h2>
            <p className="mt-2 text-sm text-[#8490ad]">
              You earned{' '}
              <span className="font-mono font-bold text-[#75e9ae]">
                {tierClearedInfo.earnedIp} IP
              </span>{' '}
              (checkpoint requirement: {TIER_TARGET_IP} IP)
            </p>
            <div className="mt-6 flex items-center gap-2 rounded-full border border-[#9e67ff]/40 bg-[#9e67ff]/10 px-4 py-1.5 text-xs font-mono text-[#9e67ff]">
              <span>Advancing to Tier {tierClearedInfo.tier + 1}</span>
              <span className="animate-pulse">...</span>
            </div>
          </div>
        </aside>
      )}

      {/* Forfeit Confirmation Modal */}
      {isForfeitDialogOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="forfeit-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-[#050916]/80 p-4 backdrop-blur-md animate-in fade-in duration-150"
          onClick={(e) => {
            if (e.target === e.currentTarget) setIsForfeitDialogOpen(false)
          }}
        >
          <div className="panel relative flex w-full max-w-md flex-col p-6 shadow-2xl md:p-8">
            <div className="flex items-start justify-between">
              <div className="flex size-12 items-center justify-center rounded-xl border border-[#f16e8d]/50 bg-[#f16e8d]/15 text-[#f16e8d] shadow-[0_0_24px_-4px_#f16e8d]">
                <Flag className="size-6" aria-hidden="true" />
              </div>
              <button
                type="button"
                onClick={() => setIsForfeitDialogOpen(false)}
                className="rounded-lg p-1.5 text-[#7783a1] hover:bg-[#141d3a] hover:text-white"
                aria-label="Cancel forfeit"
              >
                <X className="size-5" />
              </button>
            </div>

            <h2 id="forfeit-title" className="mt-4 text-2xl font-black tracking-tight text-white">
              Forfeit Active Run?
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-[#8490ad]">
              Are you sure you want to forfeit this run? Your current run will end immediately.
              Your accumulated <span className="font-semibold text-white">{score} Insight Points</span> and
              all completed stage stats will be preserved in your post-game analytics.
            </p>

            <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-3">
              <button
                type="button"
                onClick={() => setIsForfeitDialogOpen(false)}
                className="secondary-button flex-1 justify-center"
              >
                Resume Run
              </button>
              <button
                type="button"
                onClick={handleConfirmForfeit}
                className="rounded-xl border border-[#bd566b] bg-[#bd566b] px-4 py-2.5 text-xs font-black uppercase tracking-wider text-white transition-opacity hover:opacity-90"
              >
                Yes, Forfeit Run
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
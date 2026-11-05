'use client'

import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, Trophy } from 'lucide-react'
import {
  TIER_TARGET_IP,
  getQuestionTier,
  getTierEarnedIP,
  isTierGateStage,
  type AnswerRecord,
  type PowerUpId,
  type PublicQuestion,
  type Tier,
  type TierElimination,
} from '@/lib/quiz-data'
import { QuestionRound } from './question-round'
import { StageLadder, StageLadderCompact } from './stage-ladder'

interface GameplayArenaProps {
  sessionId: string
  topic: string
  gauntlet: PublicQuestion[]
  fallbackMessage?: string
  onComplete: (answers: AnswerRecord[], elimination?: TierElimination | null) => void
}

export function GameplayArena({
  sessionId,
  topic,
  gauntlet,
  fallbackMessage,
  onComplete,
}: GameplayArenaProps) {
  const [questionIndex, setQuestionIndex] = useState(0)
  const [answers, setAnswers] = useState<AnswerRecord[]>([])
  const [usedPowerUps, setUsedPowerUps] = useState<Record<PowerUpId, boolean>>({
    hint: false,
    freeze: false,
    fiftyFifty: false,
  })
  const [tierClearedInfo, setTierClearedInfo] = useState<{
    tier: Tier
    earnedIp: number
  } | null>(null)
  const tierClearedTimerRef = useRef<number | null>(null)

  useEffect(() => {
    return () => {
      if (tierClearedTimerRef.current !== null) {
        window.clearTimeout(tierClearedTimerRef.current)
      }
    }
  }, [])

  const question = gauntlet[questionIndex]
  const currentStage = question.stage
  const currentTier = getQuestionTier(currentStage, gauntlet)
  const score = answers.reduce((total, answer) => total + answer.pointsEarned, 0)
  const baseTierScore = getTierEarnedIP(currentTier, answers, gauntlet)

  function handleRoundComplete(record: AnswerRecord) {
    const nextAnswers = [...answers, record]
    const isTierGate = isTierGateStage(currentStage)

    if (isTierGate) {
      // Include the IP earned for that final question before deciding whether the player passed
      const tierEarnedIp = getTierEarnedIP(currentTier, nextAnswers, gauntlet)

      if (tierEarnedIp < TIER_TARGET_IP) {
        // If tier IP is below 300, end the game immediately and show results
        onComplete(nextAnswers, {
          tier: currentTier,
          earnedIp: tierEarnedIp,
          requiredIp: TIER_TARGET_IP,
        })
        return
      }

      // If tier IP is at least 300, show a brief "Tier Cleared" message,
      // reset tier IP to zero, then advance to the first stage of the next tier
      setAnswers(nextAnswers)
      setTierClearedInfo({ tier: currentTier, earnedIp: tierEarnedIp })

      tierClearedTimerRef.current = window.setTimeout(() => {
        setTierClearedInfo(null)
        setQuestionIndex((index) => index + 1)
      }, 1800)
      return
    }

    if (questionIndex >= gauntlet.length - 1) {
      // Normal completion at stage 20. There is no gate after Tier 4
      onComplete(nextAnswers)
      return
    }

    setAnswers(nextAnswers)
    setQuestionIndex((index) => index + 1)
  }

  return (
    <div className="flex min-h-dvh flex-col lg:flex-row">
      <StageLadder currentStage={currentStage} answers={answers} gauntlet={gauntlet} />

      <main className="bg-grid flex flex-1 flex-col">
        {fallbackMessage && (
          <aside
            aria-label="Fallback notification"
            className="flex items-center justify-center gap-2 border-b border-amber-500/30 bg-amber-500/10 px-4 py-2.5 text-center text-xs font-mono text-amber-300"
          >
            <AlertTriangle className="size-4 shrink-0 text-amber-400" aria-hidden="true" />
            <span>{fallbackMessage}</span>
          </aside>
        )}
        <StageLadderCompact currentStage={currentStage} answers={answers} gauntlet={gauntlet} />
        <QuestionRound
          key={`${sessionId}-stage-${question.stage}`}
          sessionId={sessionId}
          topic={topic}
          question={question}
          stage={currentStage}
          questionNumber={questionIndex + 1}
          totalQuestions={gauntlet.length}
          score={score}
          tierScore={baseTierScore}
          tierTarget={TIER_TARGET_IP}
          usedPowerUps={usedPowerUps}
          onUsePowerUp={(id) => setUsedPowerUps((used) => ({ ...used, [id]: true }))}
          onComplete={handleRoundComplete}
        />
      </main>

      {tierClearedInfo && (
        <aside
          role="dialog"
          aria-modal="true"
          aria-label={`Tier ${tierClearedInfo.tier} Cleared`}
          className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4 backdrop-blur-md animate-in fade-in duration-200"
        >
          <div className="relative flex w-full max-w-md flex-col items-center rounded-2xl border-2 border-tier-1/70 bg-card p-8 text-center shadow-[0_0_64px_-12px_var(--tier-1)]">
            <div className="flex size-16 items-center justify-center rounded-2xl border border-tier-1/60 bg-tier-1/15 text-tier-1 shadow-[0_0_32px_-4px_var(--tier-1)]">
              <Trophy className="size-8" aria-hidden="true" />
            </div>
            <p className="mt-4 font-mono text-xs uppercase tracking-widest text-tier-1">
              Tier {tierClearedInfo.tier} Complete
            </p>
            <h2 className="mt-2 text-3xl font-bold tracking-tight text-foreground">
              Tier Cleared!
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              You earned{' '}
              <span className="font-mono font-bold text-tier-1">
                {tierClearedInfo.earnedIp} IP
              </span>{' '}
              (required: {TIER_TARGET_IP} IP)
            </p>
            <div className="mt-6 flex items-center gap-2 rounded-full border border-primary/40 bg-primary/10 px-4 py-1.5 text-xs font-mono text-primary">
              <span>Advancing to Tier {tierClearedInfo.tier + 1}</span>
              <span className="animate-pulse">...</span>
            </div>
          </div>
        </aside>
      )}
    </div>
  )
}

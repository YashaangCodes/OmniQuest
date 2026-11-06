'use client'

import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, Flag, Trophy, X } from 'lucide-react'
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
  onComplete: (
    answers: AnswerRecord[],
    elimination?: TierElimination | null,
    isForfeit?: boolean,
  ) => void
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
  const [isForfeitDialogOpen, setIsForfeitDialogOpen] = useState(false)
  const tierClearedTimerRef = useRef<number | null>(null)

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

  function handleConfirmForfeit() {
    setIsForfeitDialogOpen(false)
    // End active run immediately, preserving accumulated answers and score without modifications
    onComplete(answers, null, true)
  }

  return (
    <div className="flex h-dvh max-h-dvh w-full flex-col overflow-hidden bg-background lg:flex-row">
      {/* Desktop Stage Ladder Sidebar */}
      <StageLadder currentStage={currentStage} answers={answers} gauntlet={gauntlet} />

      {/* Main Viewport Content Area */}
      <main className="bg-grid relative flex h-full min-h-0 flex-1 flex-col overflow-hidden">
        {fallbackMessage && (
          <aside
            aria-label="Fallback notification"
            className="flex shrink-0 items-center justify-center gap-2 border-b border-amber-500/30 bg-amber-500/10 px-4 py-2 text-center text-xs font-mono text-amber-300"
          >
            <AlertTriangle className="size-4 shrink-0 text-amber-400" aria-hidden="true" />
            <span>{fallbackMessage}</span>
          </aside>
        )}

        {/* Compact Mobile Ladder */}
        <StageLadderCompact currentStage={currentStage} answers={answers} gauntlet={gauntlet} />

        {/* Question Round takes remaining space without page-level scrolling */}
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
          onForfeit={() => setIsForfeitDialogOpen(true)}
          isForfeitDialogOpen={isForfeitDialogOpen}
        />
      </main>

      {/* Tier Cleared Modal Dialog */}
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

      {/* Forfeit Confirmation Modal */}
      {isForfeitDialogOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="forfeit-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4 backdrop-blur-md animate-in fade-in duration-150"
          onClick={(e) => {
            if (e.target === e.currentTarget) setIsForfeitDialogOpen(false)
          }}
        >
          <div className="relative flex w-full max-w-md flex-col rounded-2xl border border-border bg-card p-6 shadow-2xl md:p-8">
            <div className="flex items-start justify-between">
              <div className="flex size-12 items-center justify-center rounded-xl border border-destructive/50 bg-destructive/15 text-destructive shadow-[0_0_24px_-4px_var(--destructive)]">
                <Flag className="size-6" aria-hidden="true" />
              </div>
              <button
                type="button"
                onClick={() => setIsForfeitDialogOpen(false)}
                className="rounded-lg p-1.5 text-muted-foreground hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                aria-label="Cancel forfeit"
              >
                <X className="size-5" aria-hidden="true" />
              </button>
            </div>

            <h2 id="forfeit-title" className="mt-4 text-2xl font-bold tracking-tight text-foreground">
              Forfeit Active Run?
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              Are you sure you want to forfeit this run? Your current run will end immediately.
              Your accumulated <span className="font-semibold text-primary">{score} Insight Points</span> and
              all completed stage stats will be preserved in your post-game analytics.
            </p>

            <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-3">
              <button
                type="button"
                onClick={() => setIsForfeitDialogOpen(false)}
                className="flex-1 rounded-xl border border-border bg-secondary px-4 py-2.5 text-sm font-semibold text-secondary-foreground transition-colors hover:bg-secondary/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              >
                Resume Run
              </button>
              <button
                type="button"
                onClick={handleConfirmForfeit}
                className="flex-1 rounded-xl bg-destructive px-4 py-2.5 text-sm font-semibold text-destructive-foreground shadow-[0_4px_0_0_var(--destructive-edge)] transition-all hover:opacity-95 active:translate-y-1 active:shadow-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive"
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

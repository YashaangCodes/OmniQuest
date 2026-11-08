'use client'

import { useEffect, useEffectEvent, useState } from 'react'
import {
  AlertCircle,
  ArrowRight,
  Brain,
  Check,
  Gem,
  Info,
  Lightbulb,
  RotateCcw,
  X,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { startStage, submitAnswer, useFiftyFifty, useHint, useTimeFreeze } from '@/lib/api'
import {
  OPTION_LETTERS,
  QUESTION_TIME_LIMIT_MS,
  TIER_STYLES,
  TIMER_TICK_MS,
  TIME_FREEZE_DURATION_MS,
  calculatePoints,
  getTier,
  type AnswerRecord,
  type PowerUpId,
  type PublicQuestion,
  type Tier,
} from '@/lib/quiz-data'
import { AnswerButton, type AnswerState } from './answer-button'
import { ArenaTopBar } from './arena-top-bar'
import { MobilePowerupsBar, Powerups, type PowerUpItemStatus } from './power-ups-bar'

interface QuestionRoundProps {
  sessionId: string
  topic: string
  difficulty?: string
  question: PublicQuestion
  stage: number
  questionNumber: number
  totalQuestions: number
  score: number
  tierScore?: number
  tierTarget?: number | null
  streak: number
  streakFireActive: boolean
  powerUps: Record<PowerUpId, PowerUpItemStatus>
  onUsePowerUp: (id: PowerUpId, nextRemaining?: number) => void
  onComplete: (
    record: AnswerRecord,
    streakInfo?: { streak: number; streakFireActive: boolean },
  ) => void
  onForfeit?: () => void
  isForfeitDialogOpen?: boolean
}

export function QuestionRound({
  sessionId,
  topic,
  difficulty = 'Medium',
  question,
  stage,
  questionNumber,
  totalQuestions,
  score,
  tierScore = 0,
  tierTarget = null,
  streak,
  streakFireActive,
  powerUps,
  onUsePowerUp,
  onComplete,
  onForfeit,
  isForfeitDialogOpen = false,
}: QuestionRoundProps) {
  const [timeLeftMs, setTimeLeftMs] = useState(QUESTION_TIME_LIMIT_MS)
  const [isFrozen, setIsFrozen] = useState(false)
  const [selectedOptionText, setSelectedOptionText] = useState<string | null>(null)
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null)
  const [remainingTimeOnAnswer, setRemainingTimeOnAnswer] = useState<number>(QUESTION_TIME_LIMIT_MS)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submissionError, setSubmissionError] = useState<string | null>(null)
  const [result, setResult] = useState<AnswerRecord | null>(null)
  const [isAdvancing, setIsAdvancing] = useState(false)

  // Live power-up state
  const [hintText, setHintText] = useState<string | null>(null)
  const [eliminatedOptions, setEliminatedOptions] = useState<string[]>([])
  const [loadingPowerUps, setLoadingPowerUps] = useState<Partial<Record<PowerUpId, boolean>>>({})

  // Streak state updated by server validation
  const [currentStreak, setCurrentStreak] = useState(streak)
  const [isStreakFire, setIsStreakFire] = useState(streakFireActive)

  const tier = (question.tier ?? getTier(stage)) as Tier
  const tierStyles = TIER_STYLES[tier] || TIER_STYLES[1]
  const isFeedback = result !== null
  const isInputLocked =
    isSubmitting ||
    selectedOptionText !== null ||
    isFeedback ||
    Boolean(isForfeitDialogOpen)

  async function submitOption(
    optionText: string,
    optionIdx: number | null,
    remainingMs: number,
  ) {
    if (isSubmitting || result !== null) return

    setIsFrozen(false)
    setIsSubmitting(true)
    setSubmissionError(null)
    setSelectedOptionText(optionText)
    setSelectedIndex(optionIdx)
    setRemainingTimeOnAnswer(remainingMs)

    try {
      const response = await submitAnswer({
        session_id: sessionId,
        stage_number: question.stage,
        selected_option: optionText,
        remaining_time_ms: remainingMs,
        response_time_ms: QUESTION_TIME_LIMIT_MS - remainingMs,
      })

      const isCorrect = response.is_correct
      const speedBonus =
        response.speed_ip_awarded !== undefined
          ? response.speed_ip_awarded
          : isCorrect
            ? Math.round(remainingMs / 1000) * 5
            : 0
      const basePoints = response.base_ip_awarded ?? (isCorrect ? 100 : 0)
      const streakBonus = response.bonus_ip_awarded ?? 0
      const pointsEarned =
        response.points_awarded ?? (isCorrect ? basePoints + speedBonus + streakBonus : 0)

      if (response.current_streak !== undefined) {
        setCurrentStreak(response.current_streak)
      }
      if (response.streak_fire_active !== undefined) {
        setIsStreakFire(response.streak_fire_active)
      }

      const record: AnswerRecord = {
        questionId: `stage-${question.stage}`,
        stage: question.stage,
        prompt: question.question,
        selectedIndex: optionIdx,
        selectedAnswer: optionText || null,
        correctAnswer: response.correct_answer,
        explanation: response.explanation,
        isCorrect,
        responseTimeMs: QUESTION_TIME_LIMIT_MS - remainingMs,
        pointsEarned,
      }

      setResult(record)
      setIsSubmitting(false)
    } catch (err: unknown) {
      setIsSubmitting(false)
      const errorMsg =
        err instanceof Error
          ? err.message
          : 'Failed to submit answer. Please check your connection and retry.'
      setSubmissionError(errorMsg)
    }
  }

  // Authoritative server-side timer start
  useEffect(() => {
    if (!sessionId || !question?.stage) return
    startStage(sessionId, question.stage)
      .then((res) => {
        if (typeof res.remaining_seconds === 'number' && res.remaining_seconds > 0) {
          const serverMs = Math.round(res.remaining_seconds * 1000)
          // Synchronize if server has less time remaining (e.g. remount / resume)
          setTimeLeftMs((current) => Math.min(current, serverMs))
        }
      })
      .catch((err) => {
        console.error('Failed to initialize server timer for stage:', err)
      })
  }, [sessionId, question?.stage])

  // Timer tick down
  useEffect(() => {
    if (isInputLocked || isFrozen) return
    const intervalId = window.setInterval(() => {
      setTimeLeftMs((time) => Math.max(0, time - TIMER_TICK_MS))
    }, TIMER_TICK_MS)
    return () => window.clearInterval(intervalId)
  }, [isInputLocked, isFrozen])

  // Handle timeout
  const handleTimeout = useEffectEvent(() => {
    submitOption('', null, 0)
  })

  useEffect(() => {
    if (timeLeftMs === 0 && !isInputLocked) {
      handleTimeout()
    }
  }, [timeLeftMs, isInputLocked])

  // Time Freeze duration: 5 seconds
  useEffect(() => {
    if (!isFrozen) return
    const timeoutId = window.setTimeout(() => setIsFrozen(false), TIME_FREEZE_DURATION_MS)
    return () => window.clearTimeout(timeoutId)
  }, [isFrozen])

  async function handlePowerUp(id: PowerUpId) {
    const status = powerUps[id]
    if (
      isInputLocked ||
      !status ||
      status.max === 0 ||
      status.remaining <= 0 ||
      status.usedOnStage ||
      loadingPowerUps[id]
    ) {
      return
    }

    if (id === 'freeze') {
      if (isFrozen) return
      setLoadingPowerUps((prev) => ({ ...prev, freeze: true }))
      try {
        const res = await useTimeFreeze(sessionId, stage)
        setIsFrozen(true)
        const nextRem =
          typeof res.remaining_time_freezes === 'number'
            ? res.remaining_time_freezes
            : Math.max(0, status.remaining - 1)
        onUsePowerUp('freeze', nextRem)
      } catch (err: unknown) {
        // Failed request must NOT consume charge
        const errMsg = err instanceof Error ? err.message : 'Could not activate Time Freeze.'
        setSubmissionError(errMsg)
      } finally {
        setLoadingPowerUps((prev) => ({ ...prev, freeze: false }))
      }
    } else if (id === 'hint') {
      setLoadingPowerUps((prev) => ({ ...prev, hint: true }))
      try {
        const res = await useHint(sessionId, stage)
        if (res.is_available === false || !res.hint) {
          // Hint is unavailable: display notice without deducting charge
          setHintText(res.message || 'AI Hint is unavailable for this question.')
        } else {
          const nextRem =
            typeof res.remaining_hints === 'number'
              ? res.remaining_hints
              : Math.max(0, status.remaining - 1)
          onUsePowerUp('hint', nextRem)
          setHintText(res.hint)
        }
      } catch (err: unknown) {
        // Failed API request must NOT consume power-up charge
        const errMsg = err instanceof Error ? err.message : 'Could not fetch AI hint.'
        setHintText(`Notice: ${errMsg}`)
      } finally {
        setLoadingPowerUps((prev) => ({ ...prev, hint: false }))
      }
    } else if (id === 'fiftyFifty') {
      setLoadingPowerUps((prev) => ({ ...prev, fiftyFifty: true }))
      try {
        const res = await useFiftyFifty(sessionId, stage)
        const nextRem =
          typeof res.remaining_fifty_fifty === 'number'
            ? res.remaining_fifty_fifty
            : Math.max(0, status.remaining - 1)
        onUsePowerUp('fiftyFifty', nextRem)
        setEliminatedOptions(res.options_to_remove)
      } catch (err: unknown) {
        // Failed API request must NOT consume power-up charge
        const errMsg = err instanceof Error ? err.message : 'Could not eliminate options.'
        setSubmissionError(errMsg)
      } finally {
        setLoadingPowerUps((prev) => ({ ...prev, fiftyFifty: false }))
      }
    }
  }

  function handleNextStage() {
    if (!result || isAdvancing) return
    setIsAdvancing(true)
    onComplete(result, {
      streak: currentStreak,
      streakFireActive: isStreakFire,
    })
  }

  function getAnswerState(index: number, option: string): AnswerState {
    if (eliminatedOptions.includes(option)) {
      return 'eliminated'
    }

    if (result) {
      if (option === result.correctAnswer) {
        return result.isCorrect ? 'correct' : 'reveal'
      }
      if (option === result.selectedAnswer) {
        return 'incorrect'
      }
      return 'dimmed'
    }

    if (isSubmitting || selectedOptionText !== null) {
      if (index === selectedIndex) {
        return 'selected'
      }
      return 'dimmed'
    }

    return 'idle'
  }

  const currentTotalScore = score + (result?.pointsEarned ?? 0)
  const currentTierScore = tierScore + (result?.pointsEarned ?? 0)
  const accuracyPercent =
    stage > 1 ? Math.round((score / ((stage - 1) * 150)) * 100) : 100

  // Difficulty dot color index
  const diffIndex =
    difficulty.toLowerCase() === 'easy'
      ? 0
      : difficulty.toLowerCase() === 'hard'
        ? 2
        : difficulty.toLowerCase() === 'expert'
          ? 3
          : 1

  return (
    <div className="flex h-full min-h-0 flex-1 flex-row overflow-hidden">
      {/* Center Column: Top bar + Question Arena */}
      <div className="flex min-w-0 flex-1 flex-col h-full overflow-hidden">
        {/* Arena Top Status Bar */}
        <ArenaTopBar
          topic={topic}
          difficulty={difficulty}
          stageNumber={questionNumber}
          totalStages={totalQuestions}
          score={currentTotalScore}
          streak={currentStreak}
          streakFireActive={isStreakFire}
          timeLeftMs={timeLeftMs}
          isFrozen={isFrozen}
          currentTier={tier}
          tierScore={currentTierScore}
          tierTarget={tierTarget}
          onForfeitClick={onForfeit}
        />

        {/* Main Viewport Content Area */}
        <main className="arena-bg flex min-h-0 flex-1 flex-col items-center overflow-y-auto p-4 sm:p-8">
          <div className="w-full max-w-[760px] my-auto space-y-4">
            {/* Stage & Question Value Header */}
            <div className="flex items-center justify-between">
              <div>
                <span className="eyebrow">
                  STAGE {stage} OF {totalQuestions}
                </span>
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  <span className="tier-badge">{tierStyles.label}</span>
                  <span className="text-xs text-[#76839f]">
                    {stage === totalQuestions ? '· Final challenge' : '· Checkpoint run'}
                  </span>
                  <span className="xl:hidden inline-flex items-center gap-1 rounded bg-[#131b34] border border-[#273559] px-2 py-0.5 text-[10px] font-mono text-[#a2aeca]">
                    <span className="text-[#8492b4]">Tier:</span>
                    <span
                      className={
                        tierTarget !== null && tierTarget > 0 && currentTierScore >= tierTarget
                          ? 'text-[#73e6a8] font-bold'
                          : ''
                      }
                    >
                      {tierTarget === null || tierTarget === 0
                        ? 'No IP requirement'
                        : `${currentTierScore} / ${tierTarget} IP`}
                    </span>
                  </span>
                </div>
              </div>

              <div className="text-right">
                <div className="text-[10px] font-bold uppercase tracking-wider text-[#727e9b]">
                  Question value
                </div>
                <div className="mt-1 flex items-center gap-1 text-sm font-black text-[#e9ad43]">
                  <Gem size={14} />
                  <span>+{100 + Math.round(timeLeftMs / 1000) * 5} IP</span>
                </div>
              </div>
            </div>

            {/* Question Panel */}
            <div className="question-panel">
              <div className="mb-6 flex items-center justify-between">
                <div className="flex items-center gap-2 text-xs text-[#a3aec7]">
                  <Brain size={16} className="text-[#a67eff]" />
                  <span>{topic}</span>
                </div>
                <div className="difficulty-pill">
                  <span className={`difficulty-dot d-${diffIndex}`} />
                  <span>{difficulty}</span>
                </div>
              </div>

              <h2 className="text-xl sm:text-[26px] font-black leading-[1.3] text-white">
                {question.question}
              </h2>

              {/* AI Hint Callout Box */}
              {hintText && (
                <div className="mt-5 flex items-start gap-3 rounded-xl border border-[#654db0] bg-[#2b205b]/45 p-3 text-xs leading-5 text-[#d3c8ff] animate-in fade-in">
                  <Lightbulb size={16} className="mt-0.5 shrink-0 text-[#d6a64b]" />
                  <span>
                    <strong className="text-white">AI Hint: </strong>
                    {hintText}
                  </span>
                </div>
              )}

              {/* Submission Error Banner */}
              {submissionError && (
                <div
                  role="alert"
                  className="mt-4 flex items-center justify-between gap-3 rounded-xl border border-[#f16e8d]/50 bg-[#f16e8d]/15 p-3 text-xs text-[#f16e8d]"
                >
                  <div className="flex items-center gap-2">
                    <AlertCircle size={16} className="shrink-0" />
                    <span>{submissionError}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() =>
                      submitOption(
                        selectedOptionText ?? '',
                        selectedIndex,
                        remainingTimeOnAnswer,
                      )
                    }
                    className="inline-flex items-center gap-1 rounded bg-[#f16e8d] px-2.5 py-1 text-[11px] font-bold text-[#2a131b]"
                  >
                    <RotateCcw size={12} /> Retry
                  </button>
                </div>
              )}

              {/* 4 Answer Options */}
              <div className="mt-7 grid gap-3 sm:grid-cols-2">
                {question.options.map((option, idx) => (
                  <AnswerButton
                    key={option}
                    letter={OPTION_LETTERS[idx]}
                    text={option}
                    state={getAnswerState(idx, option)}
                    disabled={isInputLocked}
                    onSelect={() => submitOption(option, idx, timeLeftMs)}
                  />
                ))}
              </div>

              {/* Result Feedback & Explanation Box */}
              {result && (
                <div
                  className={cn(
                    'result-box animate-in fade-in zoom-in-95 duration-150',
                    result.isCorrect ? 'good' : 'bad',
                  )}
                >
                  <div className="flex items-center gap-2 font-black text-white text-sm sm:text-base">
                    {result.isCorrect ? (
                      <Check size={18} className="text-[#75e9ae]" />
                    ) : (
                      <X size={18} className="text-[#f16e8d]" />
                    )}
                    <span>
                      {result.isCorrect
                        ? `Correct · +${result.pointsEarned} Insight Points`
                        : result.selectedAnswer === null
                          ? "Time's up — keep your focus"
                          : 'Not quite — study the explanation below'}
                    </span>
                  </div>

                  {result.explanation && (
                    <p className="mt-2 text-xs leading-5 text-[#aab4ca] max-h-32 overflow-y-auto">
                      <strong className="text-white">Explanation: </strong>
                      {result.explanation}
                    </p>
                  )}

                  {/* Prominent Next Stage Button: Manual Progression */}
                  <button
                    type="button"
                    onClick={handleNextStage}
                    disabled={isAdvancing}
                    className="primary-button mt-4 w-full justify-center"
                  >
                    <span>
                      {stage === totalQuestions ? 'View results' : 'Next stage'}
                    </span>
                    <ArrowRight size={15} />
                  </button>
                </div>
              )}
            </div>

            <div className="flex justify-center gap-2 text-[10px] text-[#64708c]">
              <span className="flex items-center gap-1">
                <Info size={12} />
                Select an answer to lock your choice. Timer stops immediately.
              </span>
            </div>
          </div>
        </main>

        {/* Mobile Tactical Power-up Bar */}
        <MobilePowerupsBar
          difficulty={difficulty}
          powerUps={powerUps}
          loadingPowerUps={loadingPowerUps}
          disabled={isInputLocked}
          onUse={handlePowerUp}
        />
      </div>

      {/* Right Column: Tactical Power-Ups & Live Stats Panel */}
      <Powerups
        difficulty={difficulty}
        powerUps={powerUps}
        loadingPowerUps={loadingPowerUps}
        disabled={isInputLocked}
        score={currentTotalScore}
        accuracy={accuracyPercent}
        streak={currentStreak}
        currentStage={stage}
        totalStages={totalQuestions}
        tierScore={currentTierScore}
        tierTarget={tierTarget}
        onUse={handlePowerUp}
      />
    </div>
  )
}
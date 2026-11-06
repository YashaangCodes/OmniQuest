'use client'

import { useEffect, useEffectEvent, useState } from 'react'
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  RotateCcw,
  XCircle,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { submitAnswer } from '@/lib/api'
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
import { PowerUpsBar } from './power-ups-bar'

interface QuestionRoundProps {
  sessionId: string
  topic: string
  question: PublicQuestion
  stage: number
  questionNumber: number
  totalQuestions: number
  score: number
  tierScore?: number
  tierTarget?: number
  usedPowerUps: Record<PowerUpId, boolean>
  onUsePowerUp: (id: PowerUpId) => void
  onComplete: (record: AnswerRecord) => void
  onForfeit?: () => void
  isForfeitDialogOpen?: boolean
}

export function QuestionRound({
  sessionId,
  topic,
  question,
  stage,
  questionNumber,
  totalQuestions,
  score,
  tierScore = 0,
  tierTarget,
  usedPowerUps,
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
      })

      const isCorrect = response.is_correct
      const pointsEarned = isCorrect ? calculatePoints(remainingMs) : 0

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

  // Countdown timer tick: only ticks down when input is not locked and not frozen
  useEffect(() => {
    if (isInputLocked || isFrozen) return
    const intervalId = window.setInterval(() => {
      setTimeLeftMs((time) => Math.max(0, time - TIMER_TICK_MS))
    }, TIMER_TICK_MS)
    return () => window.clearInterval(intervalId)
  }, [isInputLocked, isFrozen])

  // Handle timeout by submitting an empty selected_option
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

  function handlePowerUp(id: PowerUpId) {
    if (isInputLocked || usedPowerUps[id]) return
    if (id === 'freeze') {
      onUsePowerUp('freeze')
      setIsFrozen(true)
    }
  }

  function handleNextStage() {
    if (!result || isAdvancing) return
    setIsAdvancing(true)
    onComplete(result)
  }

  function getAnswerState(index: number, option: string): AnswerState {
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

  const correctOptionIndex = result
    ? question.options.findIndex((opt) => opt === result.correctAnswer)
    : -1
  const correctLetter =
    correctOptionIndex >= 0 ? OPTION_LETTERS[correctOptionIndex] : ''

  const feedbackMessage = !result
    ? ''
    : result.isCorrect
      ? `Correct! +${result.pointsEarned} IP`
      : result.selectedAnswer === null
        ? `Time's up. The answer was ${correctLetter ? `${correctLetter}: ` : ''}${result.correctAnswer}`
        : `Incorrect. The answer was ${correctLetter ? `${correctLetter}: ` : ''}${result.correctAnswer}`

  const currentTierScore = tierScore + (result?.pointsEarned ?? 0)
  const currentTotalScore = score + (result?.pointsEarned ?? 0)

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col overflow-hidden">
      {/* Top Bar with score, timer, tier meter, and forfeit run button */}
      <ArenaTopBar
        topic={topic}
        questionNumber={questionNumber}
        totalQuestions={totalQuestions}
        score={currentTotalScore}
        timeLeftMs={timeLeftMs}
        isFrozen={isFrozen}
        currentTier={tier}
        tierScore={currentTierScore}
        tierTarget={tierTarget}
        onForfeitClick={onForfeit}
      />

      {/* Center Section: Flexible, centered, internal scrolling only */}
      <div className="flex min-h-0 flex-1 flex-col justify-center overflow-y-auto px-4 py-4 md:px-8 md:py-6">
        <div className="mx-auto my-auto flex w-full max-w-4xl flex-col gap-4 md:gap-6">
          {/* Question Card */}
          <section
            aria-labelledby="question-prompt"
            className="rounded-2xl border border-border bg-card p-5 shadow-lg md:p-8"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={cn(
                  'rounded-full border px-3 py-0.5 font-mono text-xs uppercase tracking-widest',
                  tierStyles.border,
                  tierStyles.softBg,
                  tierStyles.text,
                )}
              >
                Stage {stage} · {tierStyles.label}
              </span>
              <span className="rounded-full border border-border bg-secondary px-3 py-0.5 text-xs text-muted-foreground">
                {topic}
              </span>
            </div>
            <h1
              id="question-prompt"
              className="mt-3 text-balance text-xl font-bold leading-snug tracking-tight text-foreground md:text-2xl lg:text-3xl"
            >
              {question.question}
            </h1>
          </section>

          {/* Feedback & Explanation & Next Stage Section */}
          {result && (
            <div className="flex flex-col items-center gap-3 rounded-2xl border border-border/80 bg-card/60 p-4 text-center shadow-md backdrop-blur-sm animate-in fade-in zoom-in-95 duration-150 md:p-6">
              <div
                role="status"
                aria-live="polite"
                className={cn(
                  'flex items-center gap-2 font-mono text-base font-bold uppercase tracking-wider md:text-lg',
                  result.isCorrect ? 'text-tier-1' : 'text-destructive',
                )}
              >
                {result.isCorrect ? (
                  <CheckCircle2 className="size-5 shrink-0" aria-hidden="true" />
                ) : (
                  <XCircle className="size-5 shrink-0" aria-hidden="true" />
                )}
                <span>{feedbackMessage}</span>
              </div>

              {result.explanation && (
                <div className="max-h-32 w-full overflow-y-auto rounded-xl border border-border/70 bg-card/90 px-4 py-2.5 text-xs leading-relaxed text-muted-foreground md:text-sm">
                  <span className="font-semibold text-foreground">Explanation: </span>
                  {result.explanation}
                </div>
              )}

              {/* Prominent Next Stage Button: Manual Progression */}
              <button
                type="button"
                onClick={handleNextStage}
                disabled={isAdvancing}
                className="mt-2 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-8 py-3 text-base font-bold uppercase tracking-wider text-primary-foreground shadow-[0_4px_0_0_var(--primary-edge),0_0_32px_-6px_var(--primary)] transition-all hover:-translate-y-0.5 hover:shadow-[0_6px_0_0_var(--primary-edge),0_0_44px_-4px_var(--primary)] active:translate-y-1 active:shadow-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50 sm:w-auto"
              >
                <span>{stage === totalQuestions ? 'Complete Gauntlet' : 'Next Stage'}</span>
                <ArrowRight className="size-5" aria-hidden="true" />
              </button>
            </div>
          )}

          {/* Submission Error Banner */}
          {submissionError && (
            <div
              role="alert"
              className="flex w-full flex-col items-center justify-between gap-3 rounded-xl border border-destructive/50 bg-destructive/15 p-4 text-center sm:flex-row sm:text-left animate-in fade-in"
            >
              <div className="flex items-center gap-2 text-sm text-destructive">
                <AlertCircle className="size-5 shrink-0" aria-hidden="true" />
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
                className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-destructive px-3 py-1.5 text-xs font-bold uppercase tracking-wider text-destructive-foreground transition-opacity hover:opacity-90"
              >
                <RotateCcw className="size-3.5" aria-hidden="true" />
                Retry Submission
              </button>
            </div>
          )}

          {/* Answer Options Grid */}
          <div
            role="group"
            aria-label="Answer options"
            className="grid grid-cols-1 gap-3 sm:grid-cols-2"
          >
            {question.options.map((option, index) => (
              <AnswerButton
                key={option}
                letter={OPTION_LETTERS[index]}
                text={option}
                state={getAnswerState(index, option)}
                disabled={isInputLocked}
                onSelect={() => submitOption(option, index, timeLeftMs)}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Bottom Bar: Power-ups section visible at bottom */}
      <footer className="shrink-0 border-t border-border/80 bg-background/95 px-4 py-2 backdrop-blur-md md:px-8">
        <div className="mx-auto w-full max-w-4xl">
          <PowerUpsBar
            usedPowerUps={usedPowerUps}
            disabled={isInputLocked}
            onUse={handlePowerUp}
          />
        </div>
      </footer>
    </div>
  )
}

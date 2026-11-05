'use client'

import { useEffect, useEffectEvent, useState } from 'react'
import { AlertCircle, RotateCcw } from 'lucide-react'
import { cn } from '@/lib/utils'
import { submitAnswer } from '@/lib/api'
import {
  FEEDBACK_DURATION_MS,
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
}: QuestionRoundProps) {
  const [timeLeftMs, setTimeLeftMs] = useState(QUESTION_TIME_LIMIT_MS)
  const [isFrozen, setIsFrozen] = useState(false)
  const [selectedOptionText, setSelectedOptionText] = useState<string | null>(null)
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null)
  const [remainingTimeOnAnswer, setRemainingTimeOnAnswer] = useState<number>(QUESTION_TIME_LIMIT_MS)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submissionError, setSubmissionError] = useState<string | null>(null)
  const [result, setResult] = useState<AnswerRecord | null>(null)

  const tier = (question.tier ?? getTier(stage)) as Tier
  const tierStyles = TIER_STYLES[tier] || TIER_STYLES[1]
  const isFeedback = result !== null
  const isInputLocked = isSubmitting || selectedOptionText !== null || isFeedback

  async function submitOption(
    optionText: string,
    optionIdx: number | null,
    remainingMs: number,
  ) {
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

  // Countdown timer tick
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

  // Time Freeze duration
  useEffect(() => {
    if (!isFrozen) return
    const timeoutId = window.setTimeout(() => setIsFrozen(false), TIME_FREEZE_DURATION_MS)
    return () => window.clearTimeout(timeoutId)
  }, [isFrozen])

  // Advance after feedback duration (2 seconds)
  const advance = useEffectEvent(() => {
    if (result) onComplete(result)
  })

  useEffect(() => {
    if (!result) return
    const timeoutId = window.setTimeout(() => advance(), FEEDBACK_DURATION_MS)
    return () => window.clearTimeout(timeoutId)
  }, [result])

  function handlePowerUp(id: PowerUpId) {
    if (isInputLocked || usedPowerUps[id]) return
    if (id === 'freeze') {
      onUsePowerUp('freeze')
      setIsFrozen(true)
    }
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
    <div className="flex flex-1 flex-col">
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
      />

      <div className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-4 py-6 md:px-8 md:py-10">
        <section
          aria-labelledby="question-prompt"
          className="rounded-2xl border border-border bg-card p-6 shadow-xl md:p-10"
        >
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={cn(
                'rounded-full border px-3 py-1 font-mono text-xs uppercase tracking-widest',
                tierStyles.border,
                tierStyles.softBg,
                tierStyles.text,
              )}
            >
              Stage {stage} · {tierStyles.label}
            </span>
            <span className="rounded-full border border-border bg-secondary px-3 py-1 text-xs text-muted-foreground">
              {topic}
            </span>
          </div>
          <h1
            id="question-prompt"
            className="mt-5 text-balance text-2xl font-bold leading-snug tracking-tight md:text-3xl"
          >
            {question.question}
          </h1>
        </section>

        <div className="min-h-12 flex flex-col items-center justify-center">
          {result && (
            <div className="flex flex-col items-center gap-1.5 text-center">
              <div
                role="status"
                aria-live="polite"
                className={cn(
                  'font-mono text-base font-bold uppercase tracking-wider',
                  result.isCorrect ? 'text-tier-1' : 'text-destructive',
                )}
              >
                {feedbackMessage}
              </div>
              {result.explanation && (
                <p className="max-w-2xl text-sm font-normal text-muted-foreground">
                  {result.explanation}
                </p>
              )}
            </div>
          )}

          {submissionError && (
            <div
              role="alert"
              className="flex w-full flex-col items-center justify-between gap-3 rounded-xl border border-destructive/50 bg-destructive/15 p-4 text-center sm:flex-row sm:text-left"
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
                Retry
              </button>
            </div>
          )}
        </div>

        <div role="group" aria-label="Answer options" className="grid grid-cols-1 gap-4 sm:grid-cols-2">
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

        <PowerUpsBar usedPowerUps={usedPowerUps} disabled={isInputLocked} onUse={handlePowerUp} />
      </div>
    </div>
  )
}

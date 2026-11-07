'use client'

import { Check, Loader2, X } from 'lucide-react'
import { cn } from '@/lib/utils'

export type AnswerState =
  | 'idle'
  | 'selected'
  | 'correct'
  | 'incorrect'
  | 'reveal'
  | 'dimmed'
  | 'eliminated'

interface AnswerButtonProps {
  letter: string
  text: string
  state: AnswerState
  disabled: boolean
  onSelect: () => void
}

export function AnswerButton({
  letter,
  text,
  state,
  disabled,
  onSelect,
}: AnswerButtonProps) {
  const isEliminated = state === 'eliminated'
  const isSelected = state === 'selected'
  const isCorrect = state === 'correct'
  const isReveal = state === 'reveal'
  const isIncorrect = state === 'incorrect'

  return (
    <button
      type="button"
      onClick={onSelect}
      disabled={disabled || isEliminated}
      aria-label={isEliminated ? `${letter}: ${text} (eliminated)` : `${letter}: ${text}`}
      className={cn(
        'answer-button w-full',
        isSelected && 'border-[#8a64e7] bg-[#211a4c] text-white',
        isCorrect && 'correct',
        isReveal && 'correct-reveal',
        isIncorrect && 'incorrect',
        isEliminated && 'eliminated',
        state === 'dimmed' && 'opacity-40',
      )}
    >
      <span className="answer-key shrink-0 font-mono font-bold">
        {letter}
      </span>

      <span className="min-w-0 flex-1 leading-snug break-words">
        {text}
      </span>

      {isSelected && (
        <Loader2 className="size-4 shrink-0 animate-spin text-[#9e67ff]" aria-hidden="true" />
      )}
      {(isCorrect || isReveal) && (
        <Check className="size-4.5 shrink-0 text-[#75e9ae]" aria-hidden="true" />
      )}
      {isIncorrect && (
        <X className="size-4.5 shrink-0 text-[#f16e8d]" aria-hidden="true" />
      )}
    </button>
  )
}
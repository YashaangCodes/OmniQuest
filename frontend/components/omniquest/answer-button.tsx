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

const STATE_STYLES: Record<AnswerState, string> = {
  idle: 'border-border bg-card shadow-[0_4px_0_0_var(--option-edge)] sm:shadow-[0_6px_0_0_var(--option-edge)] enabled:hover:-translate-y-0.5 enabled:hover:border-primary/70 enabled:hover:shadow-[0_6px_0_0_var(--option-edge),0_0_28px_-6px_var(--primary)] enabled:active:translate-y-1.5 enabled:active:shadow-none',
  selected:
    'border-primary bg-primary/10 shadow-[0_3px_0_0_var(--primary-edge),0_0_24px_-4px_var(--primary)]',
  correct:
    'border-tier-1 bg-tier-1/15 shadow-[0_4px_0_0_var(--tier-1-edge),0_0_36px_-6px_var(--tier-1)]',
  incorrect:
    'translate-y-0.5 border-destructive bg-destructive/15 shadow-[0_2px_0_0_var(--destructive-edge),0_0_36px_-6px_var(--destructive)]',
  reveal: 'border-dashed border-tier-1/70 bg-card shadow-[0_4px_0_0_var(--option-edge)]',
  dimmed: 'border-border bg-card opacity-50 shadow-[0_4px_0_0_var(--option-edge)]',
  eliminated: 'border-border bg-card/40 opacity-30 line-through',
}

const LETTER_STYLES: Record<AnswerState, string> = {
  idle: 'bg-secondary text-primary group-enabled:group-hover:bg-primary group-enabled:group-hover:text-primary-foreground',
  selected: 'bg-primary text-primary-foreground',
  correct: 'bg-tier-1 text-background',
  incorrect: 'bg-destructive text-background',
  reveal: 'bg-tier-1/20 text-tier-1',
  dimmed: 'bg-secondary text-muted-foreground',
  eliminated: 'bg-secondary text-muted-foreground',
}

export function AnswerButton({ letter, text, state, disabled, onSelect }: AnswerButtonProps) {
  return (
    <button
      type="button"
      onClick={onSelect}
      disabled={disabled}
      aria-label={state === 'eliminated' ? `${letter}: ${text} (eliminated)` : `${letter}: ${text}`}
      className={cn(
        'group flex min-h-14 sm:min-h-16 md:min-h-18 w-full items-center gap-3 rounded-xl border-2 px-3 py-2.5 sm:px-4 sm:py-3.5 text-left text-sm font-medium text-card-foreground transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed sm:text-base md:text-lg',
        STATE_STYLES[state],
      )}
    >
      <span
        className={cn(
          'flex size-8 shrink-0 items-center justify-center rounded-lg font-mono text-sm font-bold transition-colors sm:size-9 sm:text-base',
          LETTER_STYLES[state],
        )}
      >
        {letter}
      </span>
      <span className="flex-1 leading-snug">{text}</span>
      {state === 'selected' && (
        <Loader2 className="size-5 shrink-0 animate-spin text-primary sm:size-6" aria-hidden="true" />
      )}
      {state === 'correct' && (
        <Check className="size-5 shrink-0 text-tier-1 sm:size-6" aria-hidden="true" />
      )}
      {state === 'incorrect' && (
        <X className="size-5 shrink-0 text-destructive sm:size-6" aria-hidden="true" />
      )}
    </button>
  )
}

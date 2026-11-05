import { Lightbulb, Percent, Snowflake } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { PowerUpId } from '@/lib/quiz-data'

interface PowerUpConfig {
  id: PowerUpId
  label: string
  description: string
  icon: typeof Lightbulb
  disabledInLive?: boolean
}

const POWER_UPS: PowerUpConfig[] = [
  {
    id: 'hint',
    label: 'AI Hint',
    description: 'Not available yet',
    icon: Lightbulb,
    disabledInLive: true,
  },
  {
    id: 'freeze',
    label: 'Time Freeze',
    description: 'Pause for 5s',
    icon: Snowflake,
    disabledInLive: false,
  },
  {
    id: 'fiftyFifty',
    label: '50/50',
    description: 'Not available yet',
    icon: Percent,
    disabledInLive: true,
  },
]

interface PowerUpsBarProps {
  usedPowerUps: Record<PowerUpId, boolean>
  disabled: boolean
  onUse: (id: PowerUpId) => void
}

export function PowerUpsBar({ usedPowerUps, disabled, onUse }: PowerUpsBarProps) {
  return (
    <section aria-labelledby="power-ups-heading" className="pt-2">
      <h2
        id="power-ups-heading"
        className="mb-3 font-mono text-xs uppercase tracking-widest text-muted-foreground"
      >
        Power-Ups · one use each per run
      </h2>
      <div className="grid grid-cols-3 gap-3">
        {POWER_UPS.map(({ id, label, description, icon: Icon, disabledInLive }) => {
          const isUsed = usedPowerUps[id]
          const isUnavailable = Boolean(disabledInLive)
          const isButtonDisabled = disabled || isUsed || isUnavailable

          return (
            <button
              key={id}
              type="button"
              onClick={() => onUse(id)}
              disabled={isButtonDisabled}
              title={isUnavailable ? `${label}: Not available yet in live mode` : undefined}
              className={cn(
                'flex flex-col items-center gap-1 rounded-xl border border-border bg-card px-2 py-3 text-center transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed sm:flex-row sm:gap-3 sm:px-4 sm:text-left',
                'shadow-[0_4px_0_0_var(--option-edge)] enabled:hover:border-primary/60 enabled:hover:shadow-[0_4px_0_0_var(--option-edge),0_0_24px_-6px_var(--primary)] enabled:active:translate-y-1 enabled:active:shadow-none',
                isUsed && 'opacity-40 shadow-none',
                disabled && !isUsed && !isUnavailable && 'opacity-60',
                isUnavailable && 'opacity-45 shadow-none border-dashed',
              )}
            >
              <span
                className={cn(
                  'flex size-9 shrink-0 items-center justify-center rounded-lg',
                  isUnavailable ? 'bg-secondary text-muted-foreground' : 'bg-primary/15 text-primary',
                )}
              >
                <Icon className="size-5" aria-hidden="true" />
              </span>
              <span className="min-w-0">
                <span className="block text-sm font-bold">{label}</span>
                <span className="block text-xs text-muted-foreground">
                  {isUnavailable ? 'Not available yet' : isUsed ? 'Used' : description}
                </span>
              </span>
            </button>
          )
        })}
      </div>
    </section>
  )
}

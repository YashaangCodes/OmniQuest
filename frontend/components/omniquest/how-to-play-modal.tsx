'use client'

import { useEffect } from 'react'
import {
  ArrowRight,
  Brain,
  CheckCircle2,
  CircleHelp,
  Clock,
  Flame,
  Layers,
  Lightbulb,
  Scissors,
  Snowflake,
  Sparkles,
  Trophy,
  X,
  Zap,
} from 'lucide-react'

interface HowToPlayModalProps {
  isOpen: boolean
  onClose: () => void
  onStart?: () => void
}

export function HowToPlayModal({ isOpen, onClose, onStart }: HowToPlayModalProps) {
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape' && isOpen) {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="how-to-play-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#050916]/85 p-4 backdrop-blur-md animate-in fade-in duration-150"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        className="panel relative flex max-h-[90dvh] w-full max-w-2xl flex-col p-6 shadow-2xl md:p-8"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#1c2745] pb-4 shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="flex size-8 items-center justify-center rounded-lg bg-[#2a205d] text-[#9e67ff] border border-[#7256c7]/40">
              <CircleHelp size={18} />
            </div>
            <div>
              <h2 id="how-to-play-modal-title" className="text-lg font-bold tracking-tight text-white">
                How to Play OmniQuest v0.9
              </h2>
              <p className="text-[11px] text-[#707c99]">The Official Arena Combat & Knowledge Rules</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-[#7783a1] transition-colors hover:bg-[#141d3a] hover:text-white"
            aria-label="Close rules modal"
          >
            <X size={18} />
          </button>
        </div>

        {/* Scrollable Rules Content */}
        <div className="flex-1 space-y-6 overflow-y-auto py-5 pr-1.5 text-xs sm:text-sm text-[#8b97b3]">
          {/* Section 1: Gauntlet Structure & Dynamic Lengths */}
          <section className="space-y-1.5">
            <h3 className="flex items-center gap-2 text-xs font-black uppercase tracking-wider text-white">
              <Layers size={15} className="text-[#9e67ff]" />
              1. Gauntlet Structure & Dynamic Game Lengths
            </h3>
            <p className="leading-relaxed">
              OmniQuest generates tailored learning gauntlets for any subject or uploaded source document.
              Gauntlets dynamically scale across <strong className="text-white">5, 10, 15, or 20 stages</strong>:
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 font-mono text-[11px]">
              <div className="rounded-lg border border-[#243354] bg-[#111932] p-2 text-center">
                <span className="block font-bold text-white">5 Questions</span>
                <span className="text-[10px] text-[#73809e]">Tier 1 Only</span>
              </div>
              <div className="rounded-lg border border-[#243354] bg-[#111932] p-2 text-center">
                <span className="block font-bold text-white">10 Questions</span>
                <span className="text-[10px] text-[#73809e]">Tiers 1 & 2</span>
              </div>
              <div className="rounded-lg border border-[#243354] bg-[#111932] p-2 text-center">
                <span className="block font-bold text-white">15 Questions</span>
                <span className="text-[10px] text-[#73809e]">Tiers 1, 2 & 3</span>
              </div>
              <div className="rounded-lg border border-[#243354] bg-[#111932] p-2 text-center">
                <span className="block font-bold text-white">20 Questions</span>
                <span className="text-[10px] text-[#73809e]">Full 4 Tiers</span>
              </div>
            </div>
          </section>

          {/* Section 2: Four Difficulty Tiers (5 Questions Per Tier) */}
          <section className="space-y-1.5">
            <h3 className="flex items-center gap-2 text-xs font-black uppercase tracking-wider text-[#75e9ae]">
              <Trophy size={15} className="text-[#75e9ae]" />
              2. Four Difficulty Tiers (5 Questions per Tier)
            </h3>
            <p className="leading-relaxed">
              Every tier contains exactly 5 sequential questions that increase in depth and analytical complexity:
            </p>
            <ul className="space-y-1.5 pt-1 text-xs">
              <li className="rounded-lg border border-[#75e9ae]/20 bg-[#75e9ae]/5 p-2">
                <span className="font-bold text-[#75e9ae]">Tier 1 (Stages 1–5): </span>
                Foundational definitions, primary principles, and core recall.
              </li>
              <li className="rounded-lg border border-[#e9ad43]/20 bg-[#e9ad43]/5 p-2">
                <span className="font-bold text-[#e9ad43]">Tier 2 (Stages 6–10): </span>
                Conceptual mechanisms, functional relationships, and causal dynamics.
              </li>
              <li className="rounded-lg border border-[#ff8c58]/20 bg-[#ff8c58]/5 p-2">
                <span className="font-bold text-[#ff8c58]">Tier 3 (Stages 11–15): </span>
                Applied analytical scenarios, edge cases, and real-world problem-solving.
              </li>
              <li className="rounded-lg border border-[#f16e8d]/20 bg-[#f16e8d]/5 p-2">
                <span className="font-bold text-[#f16e8d]">Tier 4 (Stages 16–20): </span>
                Multi-step synthesis, cross-domain evaluation, and the Golden Final Challenge.
              </li>
            </ul>
          </section>

          {/* Section 3: Insight Points & Checkpoint Requirements */}
          <section className="space-y-1.5">
            <h3 className="flex items-center gap-2 text-xs font-black uppercase tracking-wider text-[#e9ad43]">
              <Sparkles size={15} className="text-[#e9ad43]" />
              3. Insight Points (IP) & Checkpoint Requirements
            </h3>
            <p className="leading-relaxed">
              Each stage provides a 20-second countdown. Correct answers award{' '}
              <strong className="text-white">100 base IP</strong> plus{' '}
              <strong className="text-[#e9ad43]">5 bonus IP per remaining second</strong> (up to 200 IP total per question).
            </p>
            <div className="rounded-xl border border-[#e9ad43]/30 bg-[#e9ad43]/10 p-3 text-xs leading-relaxed text-[#e5caa3]">
              <strong className="text-[#e9ad43] block mb-1">Tier Gate Checkpoints (Stages 5, 10, 15):</strong>
              At intermediate checkpoints, you must accumulate at least <strong className="text-white font-mono">300 IP</strong> within that tier to clear the gate and bank your points. If you fall short of 300 IP at a checkpoint, your run ends in elimination.
            </div>
          </section>

          {/* Section 4: Streak Fire */}
          <section className="space-y-1.5">
            <h3 className="flex items-center gap-2 text-xs font-black uppercase tracking-wider text-[#ff9d4d]">
              <Flame size={15} className="text-[#ff9d4d]" />
              4. Streak Fire Multiplier
            </h3>
            <p className="leading-relaxed">
              Answering 3 questions in a row correctly ignites <strong className="text-[#ff9d4d]">Streak Fire</strong>.
              While active, every subsequent correct answer awards an automatic{' '}
              <strong className="text-white font-mono">+50 IP Streak Bonus</strong>!
              An incorrect answer or timeout resets your streak.
            </p>
          </section>

          {/* Section 5: Answer Locking & Manual Progression */}
          <section className="space-y-1.5">
            <h3 className="flex items-center gap-2 text-xs font-black uppercase tracking-wider text-white">
              <CheckCircle2 size={15} className="text-[#9e67ff]" />
              5. Answer Locking & Manual Progression
            </h3>
            <p className="leading-relaxed">
              When you click an answer option, your choice is locked immediately and the timer stops.
              The server validates your response and provides the verified correct answer and comprehensive explanation.
              Study the explanation at your own pace—advancement occurs only when you manually click{' '}
              <strong className="text-white">Next Stage</strong>.
            </p>
          </section>

          {/* Section 6: Tactical Power-Ups */}
          <section className="space-y-2">
            <h3 className="flex items-center gap-2 text-xs font-black uppercase tracking-wider text-[#7cc5ff]">
              <Zap size={15} className="text-[#7cc5ff]" />
              6. Tactical Power-Ups & Difficulty Allocation
            </h3>
            <p className="leading-relaxed">
              OmniQuest v0.9 enforces an official difficulty-based power-up quota per game run. These limits apply uniformly across all gauntlet lengths (5, 10, 15, or 20 questions):
            </p>

            {/* Official Power-Up Allocation Table */}
            <div className="overflow-hidden rounded-xl border border-[#233556] bg-[#0c142c]">
              <table className="w-full text-left font-mono text-[11px]">
                <thead>
                  <tr className="border-b border-[#233556] bg-[#121c38] text-[#8e9cb9]">
                    <th className="p-2 pl-3 font-semibold">Difficulty</th>
                    <th className="p-2 text-center font-semibold text-[#b38dff]">AI Hint</th>
                    <th className="p-2 text-center font-semibold text-[#efbb61]">50 / 50</th>
                    <th className="p-2 text-center font-semibold text-[#7cc5ff]">Time Freeze</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1b2848] text-white">
                  <tr>
                    <td className="p-2 pl-3 font-bold text-[#75e9ae]">Easy</td>
                    <td className="p-2 text-center">2</td>
                    <td className="p-2 text-center">2</td>
                    <td className="p-2 text-center">2</td>
                  </tr>
                  <tr>
                    <td className="p-2 pl-3 font-bold text-[#e9ad43]">Medium</td>
                    <td className="p-2 text-center">1</td>
                    <td className="p-2 text-center">1</td>
                    <td className="p-2 text-center">2</td>
                  </tr>
                  <tr>
                    <td className="p-2 pl-3 font-bold text-[#ff8c58]">Hard</td>
                    <td className="p-2 text-center text-[#616e8b]">0</td>
                    <td className="p-2 text-center text-[#616e8b]">0</td>
                    <td className="p-2 text-center">2</td>
                  </tr>
                  <tr>
                    <td className="p-2 pl-3 font-bold text-[#f16e8d]">Expert</td>
                    <td className="p-2 text-center text-[#616e8b]">0</td>
                    <td className="p-2 text-center text-[#616e8b]">0</td>
                    <td className="p-2 text-center text-[#616e8b]">0</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div className="grid gap-2 sm:grid-cols-3 pt-1 text-xs">
              <div className="rounded-xl border border-[#654db0] bg-[#2b205b]/40 p-2.5">
                <div className="flex items-center gap-1.5 text-white font-bold mb-1">
                  <Lightbulb size={14} className="text-[#d6a64b]" />
                  <span>AI Hint</span>
                </div>
                <p className="text-[11px] text-[#aeb8d1]">
                  Asks Gemini to generate a subtle 1-sentence clue without revealing the answer.
                </p>
              </div>

              <div className="rounded-xl border border-[#2d4b7a] bg-[#162744]/60 p-2.5">
                <div className="flex items-center gap-1.5 text-white font-bold mb-1">
                  <Snowflake size={14} className="text-[#7cc5ff]" />
                  <span>Time Freeze</span>
                </div>
                <p className="text-[11px] text-[#aeb8d1]">
                  Completely freezes the 20-second countdown clock for 5 seconds of calm contemplation.
                </p>
              </div>

              <div className="rounded-xl border border-[#745a38] bg-[#30251d]/60 p-2.5">
                <div className="flex items-center gap-1.5 text-white font-bold mb-1">
                  <Scissors size={14} className="text-[#efbb61]" />
                  <span>50 / 50</span>
                </div>
                <p className="text-[11px] text-[#aeb8d1]">
                  Permanently eliminates exactly two incorrect options for the active question.
                </p>
              </div>
            </div>

            <p className="text-[11px] leading-relaxed text-[#75819e] pt-1">
              <strong className="text-white">Usage Rules:</strong> A power-up cannot be activated more than once on the same question. Failed network requests do not consume power-up charges. Power-ups are disabled once depleted or on difficulties where quota is 0.
            </p>
          </section>
        </div>

        {/* Modal Actions */}
        <div className="border-t border-[#1c2745] pt-4 flex flex-col sm:flex-row gap-2.5 shrink-0">
          <button
            type="button"
            onClick={onClose}
            className="secondary-button flex-1 justify-center"
          >
            Close Guide
          </button>
          {onStart && (
            <button
              type="button"
              onClick={() => {
                onClose()
                onStart()
              }}
              className="primary-button flex-1 justify-center"
            >
              Enter the Arena <ArrowRight size={15} />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

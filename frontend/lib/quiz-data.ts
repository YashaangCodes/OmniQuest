export type Tier = 1 | 2 | 3 | 4

export type PowerUpId = 'hint' | 'freeze' | 'fiftyFifty'

export type Difficulty = 'Easy' | 'Medium' | 'Hard' | 'Expert'

export const POWER_UP_LIMITS_BY_DIFFICULTY: Record<
  Difficulty,
  Record<PowerUpId, number>
> = {
  Easy: { hint: 2, fiftyFifty: 2, freeze: 2 },
  Medium: { hint: 1, fiftyFifty: 1, freeze: 2 },
  Hard: { hint: 0, fiftyFifty: 0, freeze: 2 },
  Expert: { hint: 0, fiftyFifty: 0, freeze: 0 },
}

export function getPowerUpLimits(difficulty: string = 'Medium'): Record<PowerUpId, number> {
  const trimmed = (difficulty || 'Medium').trim()
  const normalized = (trimmed.charAt(0).toUpperCase() + trimmed.slice(1).toLowerCase()) as Difficulty
  return POWER_UP_LIMITS_BY_DIFFICULTY[normalized] || POWER_UP_LIMITS_BY_DIFFICULTY.Medium
}

import type { PublicQuestion } from './api'

export type {
  PublicQuestion,
  GenerateGameResponse,
  SubmitAnswerRequest,
  SubmitAnswerResponse,
} from './api'

export interface QuizQuestion {
  id: string
  category: string
  prompt: string
  options: [string, string, string, string]
  correctIndex: number
  hint: string
}

export interface AnswerRecord {
  questionId: string
  stage: number
  prompt: string
  selectedIndex: number | null
  selectedAnswer: string | null
  correctAnswer: string
  explanation?: string
  isCorrect: boolean
  responseTimeMs: number
  pointsEarned: number
}

export const TOTAL_STAGES = 20
export const QUESTION_TIME_LIMIT_MS = 20_000
export const FEEDBACK_DURATION_MS = 2_000
export const TIME_FREEZE_DURATION_MS = 5_000
export const TIMER_TICK_MS = 100
export const OPTION_LETTERS = ['A', 'B', 'C', 'D'] as const

export const DEMO_QUESTIONS: QuizQuestion[] = [
  {
    id: 'q1',
    category: 'Data Structures',
    prompt: 'Which data structure follows Last-In, First-Out (LIFO) order?',
    options: ['Queue', 'Stack', 'Linked List', 'Hash Map'],
    correctIndex: 1,
    hint: 'Picture a pile of plates — you always take the top one first.',
  },
  {
    id: 'q2',
    category: 'Web Fundamentals',
    prompt: 'What does the HTTP status code 404 indicate?',
    options: ['Internal server error', 'Unauthorized', 'Resource not found', 'Permanent redirect'],
    correctIndex: 2,
    hint: 'You usually see it after following a broken link.',
  },
  {
    id: 'q3',
    category: 'Algorithms',
    prompt: 'What is the time complexity of binary search on a sorted array?',
    options: ['O(log n)', 'O(n)', 'O(n log n)', 'O(1)'],
    correctIndex: 0,
    hint: 'Each step cuts the remaining search space in half.',
  },
  {
    id: 'q4',
    category: 'Astronomy',
    prompt: 'Which planet has the shortest year in our solar system?',
    options: ['Venus', 'Mars', 'Earth', 'Mercury'],
    correctIndex: 3,
    hint: 'The closer a planet is to the Sun, the faster it orbits.',
  },
  {
    id: 'q5',
    category: 'CSS',
    prompt: "Which CSS property controls the space between an element's border and its content?",
    options: ['margin', 'padding', 'gap', 'outline'],
    correctIndex: 1,
    hint: 'Margin is outside the border. This one lives inside it.',
  },
]

export function getTier(stage: number): Tier {
  if (stage <= 5) return 1
  if (stage <= 10) return 2
  if (stage <= 15) return 3
  return 4
}

export const TIER_TARGET_IP = 300
export const TIER_GATE_STAGES = [5, 10, 15] as const

export const TIER_PROGRESSION_THRESHOLDS: Record<
  Difficulty,
  Record<1 | 2 | 3, number | null>
> = {
  Easy: { 1: null, 2: null, 3: 300 },
  Medium: { 1: 150, 2: 250, 3: 300 },
  Hard: { 1: 300, 2: 350, 3: 400 },
  Expert: { 1: 300, 2: 400, 3: 500 },
}

export function getTierProgressionThreshold(
  difficulty: string = 'Medium',
  fromTier: 1 | 2 | 3,
): number | null {
  const trimmed = (difficulty || 'Medium').trim()
  const normalized = (trimmed.charAt(0).toUpperCase() + trimmed.slice(1).toLowerCase()) as Difficulty
  const diffMatrix = TIER_PROGRESSION_THRESHOLDS[normalized] || TIER_PROGRESSION_THRESHOLDS.Medium
  return diffMatrix[fromTier] ?? null
}

export interface TierElimination {
  tier: Tier
  earnedIp: number
  requiredIp: number
}

export function getQuestionTier(stage: number, gauntlet?: PublicQuestion[]): Tier {
  const match = gauntlet?.find((q) => q.stage === stage)
  if (match && typeof match.tier === 'number' && match.tier >= 1 && match.tier <= 4) {
    return match.tier as Tier
  }
  return getTier(stage)
}

export function getTierEarnedIP(
  tier: Tier,
  answers: AnswerRecord[],
  gauntlet?: PublicQuestion[],
): number {
  return answers
    .filter((a) => getQuestionTier(a.stage, gauntlet) === tier)
    .reduce((sum, a) => sum + a.pointsEarned, 0)
}

export function isTierGateStage(stage: number, totalStages: number = 20): boolean {
  return (stage === 5 || stage === 10 || stage === 15) && stage < totalStages
}

export const TIER_STYLES: Record<
  Tier,
  { label: string; text: string; bg: string; softBg: string; border: string; glow: string }
> = {
  1: {
    label: 'Tier 1',
    text: 'text-tier-1',
    bg: 'bg-tier-1',
    softBg: 'bg-tier-1/15',
    border: 'border-tier-1/70',
    glow: 'shadow-[0_0_24px_-4px_var(--tier-1)]',
  },
  2: {
    label: 'Tier 2',
    text: 'text-tier-2',
    bg: 'bg-tier-2',
    softBg: 'bg-tier-2/15',
    border: 'border-tier-2/70',
    glow: 'shadow-[0_0_24px_-4px_var(--tier-2)]',
  },
  3: {
    label: 'Tier 3',
    text: 'text-tier-3',
    bg: 'bg-tier-3',
    softBg: 'bg-tier-3/15',
    border: 'border-tier-3/70',
    glow: 'shadow-[0_0_24px_-4px_var(--tier-3)]',
  },
  4: {
    label: 'Tier 4',
    text: 'text-tier-4',
    bg: 'bg-tier-4',
    softBg: 'bg-tier-4/15',
    border: 'border-tier-4/70',
    glow: 'shadow-[0_0_24px_-4px_var(--tier-4)]',
  },
}

export function calculatePoints(timeLeftMs: number): number {
  return 100 + Math.round(timeLeftMs / 1000) * 5
}

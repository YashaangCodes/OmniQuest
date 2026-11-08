/**
 * OmniQuest v0.9 Local Storage Management
 * Handles persistent guest statistics, completed game history, and achievement unlocking.
 * Fully client-safe with defensive SSR checks.
 */

export const STORAGE_KEY_HISTORY = 'omniquest_game_history'
export const STORAGE_KEY_SETTINGS = 'omniquest_settings'

export interface GameRunRecord {
  id: string
  topic: string
  difficulty: string
  date: string
  timestamp: number
  stagesCompleted: number
  totalStages: number
  score: number
  accuracy: number
  correctCount: number
  bestStreak: number
  durationSeconds: number
  isForfeit: boolean
}

export interface Achievement {
  id: string
  title: string
  desc: string
  color: 'orange' | 'purple' | 'gold' | 'green'
  unlocked: boolean
  unlockedAt?: number
}

export interface PlayerStats {
  playerName: string
  playerInitials: string
  level: number
  levelTitle: string
  totalIp: number
  currentLevelIp: number
  nextLevelIp: number
  levelProgressPercent: number
  gamesPlayed: number
  highestScore: number
  highestStreak: number
  bestAccuracy: number
  bestTimeSeconds: number
  activeDayStreak: number
  achievements: Achievement[]
  unlockedAchievementsCount: number
}

export interface UserSettings {
  soundEnabled: boolean
  reducedMotion: boolean
}

const DEFAULT_SETTINGS: UserSettings = {
  soundEnabled: true,
  reducedMotion: false,
}

function isClient(): boolean {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'
}

/**
 * Format a timestamp into a human-readable date.
 */
export function formatRunDate(timestamp: number): string {
  const date = new Date(timestamp)
  const now = new Date()

  const isToday =
    date.getDate() === now.getDate() &&
    date.getMonth() === now.getMonth() &&
    date.getFullYear() === now.getFullYear()

  if (isToday) return 'Today'

  const yesterday = new Date(now)
  yesterday.setDate(yesterday.getDate() - 1)
  const isYesterday =
    date.getDate() === yesterday.getDate() &&
    date.getMonth() === yesterday.getMonth() &&
    date.getFullYear() === yesterday.getFullYear()

  if (isYesterday) return 'Yesterday'

  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
  })
}

/**
 * Format duration in seconds to MM:SS.
 */
export function formatDuration(totalSeconds: number): string {
  if (totalSeconds <= 0) return '00:00'
  const mins = Math.floor(totalSeconds / 60)
    .toString()
    .padStart(2, '0')
  const secs = (totalSeconds % 60).toString().padStart(2, '0')
  return `${mins}:${secs}`
}

/**
 * Retrieve all completed game runs from localStorage.
 */
export function getGameHistory(): GameRunRecord[] {
  if (!isClient()) return []

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY_HISTORY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.sort((a, b) => b.timestamp - a.timestamp)
  } catch {
    return []
  }
}

/**
 * Save a newly completed game run to localStorage.
 */
export function saveCompletedGame(
  run: Omit<GameRunRecord, 'id' | 'timestamp' | 'date'>,
): GameRunRecord {
  const timestamp = Date.now()
  const record: GameRunRecord = {
    ...run,
    id: `run_${timestamp}_${Math.random().toString(36).substring(2, 7)}`,
    timestamp,
    date: formatRunDate(timestamp),
  }

  if (isClient()) {
    try {
      const existing = getGameHistory()
      const updated = [record, ...existing]
      // Store up to 50 most recent runs
      window.localStorage.setItem(STORAGE_KEY_HISTORY, JSON.stringify(updated.slice(0, 50)))
    } catch {
      // Storage quota or privacy restriction
    }
  }

  return record
}

/**
 * Calculate consecutive daily play streak based on completed run dates.
 */
function calculateDayStreak(runs: GameRunRecord[]): number {
  if (runs.length === 0) return 0

  const uniqueDays = Array.from(
    new Set(
      runs.map((r) => {
        const d = new Date(r.timestamp)
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
      }),
    ),
  ).sort().reverse()

  if (uniqueDays.length === 0) return 0

  const today = new Date()
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`

  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)
  const yesterdayStr = `${yesterday.getFullYear()}-${String(yesterday.getMonth() + 1).padStart(2, '0')}-${String(yesterday.getDate()).padStart(2, '0')}`

  // If player hasn't played today or yesterday, streak is 0
  if (uniqueDays[0] !== todayStr && uniqueDays[0] !== yesterdayStr) {
    return 0
  }

  let streak = 1
  let currentDate = new Date(uniqueDays[0])

  for (let i = 1; i < uniqueDays.length; i++) {
    const prevDate = new Date(currentDate)
    prevDate.setDate(prevDate.getDate() - 1)
    const prevDateStr = `${prevDate.getFullYear()}-${String(prevDate.getMonth() + 1).padStart(2, '0')}-${String(prevDate.getDate()).padStart(2, '0')}`

    if (uniqueDays[i] === prevDateStr) {
      streak++
      currentDate = prevDate
    } else {
      break
    }
  }

  return streak
}

/**
 * Derive full player stats and achievement progress from actual local history.
 * Never invents fictional numbers; returns zeroed stats for new guest users.
 */
export function getPlayerStats(): PlayerStats {
  const history = getGameHistory()

  const gamesPlayed = history.length
  const totalIp = history.reduce((sum, run) => sum + (run.score || 0), 0)
  const highestScore = gamesPlayed ? Math.max(...history.map((r) => r.score)) : 0
  const highestStreak = gamesPlayed ? Math.max(...history.map((r) => r.bestStreak)) : 0
  const bestAccuracy = gamesPlayed ? Math.max(...history.map((r) => r.accuracy)) : 0

  const completedNonForfeits = history.filter((r) => !r.isForfeit && r.stagesCompleted === r.totalStages)
  const bestTimeSeconds = completedNonForfeits.length
    ? Math.min(...completedNonForfeits.map((r) => r.durationSeconds))
    : 0

  // Level Progression: Level 1 starts at 0 IP, 1,000 IP per level
  const level = 1 + Math.floor(totalIp / 1000)
  const currentLevelIp = totalIp % 1000
  const nextLevelIp = 1000
  const levelProgressPercent = Math.min(100, Math.round((currentLevelIp / nextLevelIp) * 100))
  const levelTitle = `Level ${level < 10 ? `0${level}` : level}`

  // Achievement unlock logic verified against actual gameplay data
  const achievements: Achievement[] = [
    {
      id: 'combo-starter',
      title: 'Combo Starter',
      desc: 'Reach a 3 answer streak in any gauntlet',
      color: 'orange',
      unlocked: highestStreak >= 3,
    },
    {
      id: 'sharp-mind',
      title: 'Sharp Mind',
      desc: 'Complete a gauntlet of at least 5 stages',
      color: 'purple',
      unlocked: history.some((r) => !r.isForfeit && r.stagesCompleted >= 5),
    },
    {
      id: 'point-hoarder',
      title: 'Point Hoarder',
      desc: 'Earn 5,000 total Insight Points across all runs',
      color: 'gold',
      unlocked: totalIp >= 5000,
    },
    {
      id: 'perfect-recall',
      title: 'Perfect Recall',
      desc: 'Achieve 100% accuracy in a gauntlet of at least 5 stages',
      color: 'green',
      unlocked: history.some(
        (r) => !r.isForfeit && r.accuracy === 100 && r.stagesCompleted >= 5,
      ),
    },
  ]

  const unlockedAchievementsCount = achievements.filter((a) => a.unlocked).length
  const activeDayStreak = calculateDayStreak(history)

  return {
    playerName: 'Guest Player',
    playerInitials: 'GP',
    level,
    levelTitle,
    totalIp,
    currentLevelIp,
    nextLevelIp,
    levelProgressPercent,
    gamesPlayed,
    highestScore,
    highestStreak,
    bestAccuracy,
    bestTimeSeconds,
    activeDayStreak,
    achievements,
    unlockedAchievementsCount,
  }
}

/**
 * Retrieve user settings.
 */
export function getUserSettings(): UserSettings {
  if (!isClient()) return DEFAULT_SETTINGS
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY_SETTINGS)
    if (!raw) return DEFAULT_SETTINGS
    return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) }
  } catch {
    return DEFAULT_SETTINGS
  }
}

/**
 * Save user settings.
 */
export function saveUserSettings(settings: Partial<UserSettings>): UserSettings {
  const current = getUserSettings()
  const updated = { ...current, ...settings }
  if (isClient()) {
    try {
      window.localStorage.setItem(STORAGE_KEY_SETTINGS, JSON.stringify(updated))
    } catch {
      // Storage error
    }
  }
  return updated
}

/**
 * Clear all guest data from localStorage.
 */
export function clearAllGuestData(): void {
  if (!isClient()) return
  try {
    window.localStorage.removeItem(STORAGE_KEY_HISTORY)
    window.localStorage.removeItem(STORAGE_KEY_SETTINGS)
  } catch {
    // Storage error
  }
}

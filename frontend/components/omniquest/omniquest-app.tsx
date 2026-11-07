'use client'

import { useEffect, useState } from 'react'
import {
  Bell,
  Brain,
  ChevronDown,
  CircleHelp,
  Gamepad2,
  Gem,
  History,
  Home,
  Menu,
  Settings,
  Trophy,
  X,
} from 'lucide-react'
import type { AnswerRecord, PublicQuestion, TierElimination } from '@/lib/quiz-data'
import { getPlayerStats, type PlayerStats } from '@/lib/game-storage'
import { GameplayArena } from './gameplay-arena'
import { ResultsScreen } from './results-screen'
import { SetupScreen, type Difficulty } from './setup-screen'
import { TrophyRoom } from './trophy-room'
import { HowToPlayModal } from './how-to-play-modal'
import { SettingsModal } from './settings-modal'

type Screen =
  | { name: 'setup' }
  | {
      name: 'playing'
      sessionId: string
      topic: string
      difficulty: Difficulty
      gauntlet: PublicQuestion[]
      fallbackMessage?: string
    }
  | {
      name: 'results'
      topic: string
      difficulty: Difficulty
      answers: AnswerRecord[]
      totalStages: number
      elimination?: TierElimination | null
      isForfeit?: boolean
    }
  | { name: 'trophies'; tab?: 'trophies' | 'history' }

function Logo() {
  return (
    <div className="flex items-center gap-3">
      <div className="logo-mark shrink-0">
        <Brain size={21} />
      </div>
      <div>
        <div className="text-[17px] font-black tracking-[0.13em] text-white">
          OMNI<span className="text-[#9e67ff]">QUEST</span>
        </div>
        <div className="text-[9px] font-bold tracking-[0.24em] text-[#697593]">
          KNOWLEDGE ARENA
        </div>
      </div>
    </div>
  )
}

interface SideNavProps {
  currentView: string
  currentTab?: 'trophies' | 'history'
  stats: PlayerStats | null
  onNavigate: (view: 'setup' | 'trophies', tab?: 'trophies' | 'history') => void
  onHowTo: () => void
  onSettings: () => void
}

function SideNav({
  currentView,
  currentTab,
  stats,
  onNavigate,
  onHowTo,
  onSettings,
}: SideNavProps) {
  const trophyBadge =
    stats && stats.unlockedAchievementsCount > 0
      ? String(stats.unlockedAchievementsCount)
      : undefined

  const navItems = [
    { label: 'Home', icon: Home, action: () => onNavigate('setup') },
    { label: 'Play Arena', icon: Gamepad2, action: () => onNavigate('setup') },
    {
      label: 'Trophy Room',
      icon: Trophy,
      action: () => onNavigate('trophies', 'trophies'),
      badge: trophyBadge,
    },
    {
      label: 'Game History',
      icon: History,
      action: () => onNavigate('trophies', 'history'),
    },
    { label: 'How to Play', icon: CircleHelp, action: onHowTo },
    { label: 'Settings', icon: Settings, action: onSettings },
  ]

  const levelText = stats ? stats.levelTitle : 'Level 01'
  const currentIp = stats ? stats.totalIp : 0
  const progressPercent = stats ? stats.levelProgressPercent : 0
  const nextLevelIp = stats ? stats.nextLevelIp : 1000

  return (
    <aside className="hidden w-[236px] shrink-0 flex-col border-r border-[#1c2745] bg-[#0a1024] lg:flex h-full select-none">
      <div className="flex h-[82px] items-center border-b border-[#1c2745] px-7 shrink-0">
        <Logo />
      </div>

      <div className="flex-1 px-4 py-7 overflow-y-auto">
        <p className="eyebrow px-3 pb-4">Main menu</p>
        <div className="space-y-1.5">
          {navItems.map(({ label, icon: Icon, action, badge }) => {
            const isActive =
              (currentView === 'setup' && (label === 'Home' || label === 'Play Arena')) ||
              (currentView === 'trophies' && currentTab === 'trophies' && label === 'Trophy Room') ||
              (currentView === 'trophies' && currentTab === 'history' && label === 'Game History')

            return (
              <button
                key={label}
                type="button"
                onClick={action}
                className={`nav-item ${isActive ? 'active' : ''}`}
              >
                <Icon size={18} />
                <span>{label}</span>
                {badge && (
                  <span className="ml-auto rounded-md bg-[#e9ad43] px-1.5 text-[10px] font-black text-[#161326]">
                    {badge}
                  </span>
                )}
              </button>
            )
          })}
        </div>

        <div className="my-7 h-px bg-[#1c2745]" />

        {/* Real Guest Player Progress Card */}
        <p className="eyebrow px-3 pb-4">Your progress</p>
        <div className="progress-card">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs text-[#aeb8d1]">Arena level</span>
            <span className="text-xs font-bold text-[#75e9ae] font-mono">{levelText}</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-[#1e2948]">
            <div
              className="h-full rounded-full bg-gradient-to-r from-[#7153ed] to-[#78e9af] transition-all duration-300"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <div className="mt-2 flex justify-between text-[10px] text-[#66718d] font-mono">
            <span>{currentIp.toLocaleString()} IP</span>
            <span>{nextLevelIp.toLocaleString()} IP</span>
          </div>
        </div>
      </div>

      <div className="border-t border-[#1c2745] p-5 shrink-0">
        <div className="flex items-center justify-between text-[10px] font-bold text-[#65718d]">
          <span>OMNIQUEST v1.0</span>
          <span className="flex items-center gap-1.5 text-[#71e9ab]">
            <span className="h-1.5 w-1.5 rounded-full bg-[#71e9ab] animate-pulse" />
            ONLINE
          </span>
        </div>
      </div>
    </aside>
  )
}

function TopBar({
  title,
  stats,
  onOpenMenu,
  onOpenSettings,
}: {
  title: string
  stats: PlayerStats | null
  onOpenMenu: () => void
  onOpenSettings: () => void
}) {
  const currentIp = stats ? stats.totalIp : 0
  const levelText = stats ? stats.levelTitle : 'Level 01'
  const playerName = stats ? stats.playerName : 'Guest Player'
  const playerInitials = stats ? stats.playerInitials : 'GP'

  return (
    <header className="flex h-[72px] sm:h-[82px] shrink-0 items-center justify-between border-b border-[#1c2745] bg-[#0b1126]/95 px-5 sm:px-8">
      <div className="flex items-center gap-4">
        <button
          type="button"
          className="text-[#98a3bf] hover:text-white lg:hidden"
          onClick={onOpenMenu}
          aria-label="Open navigation menu"
        >
          <Menu size={22} />
        </button>

        <div>
          <div className="flex items-center gap-2.5">
            <span className="h-2 w-2 rounded-full bg-[#74e6a7] shadow-[0_0_10px_#74e6a7]" />
            <span className="text-sm font-bold capitalize text-white">{title}</span>
          </div>
          <p className="mt-0.5 hidden text-[11px] text-[#697593] sm:block">
            Train your mind. Own your progress.
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2.5 sm:gap-5">
        <div className="hidden items-center gap-2 rounded-xl border border-[#273354] bg-[#111932] px-3 py-2 sm:flex">
          <Gem size={15} className="text-[#e9ad43]" />
          <span className="text-[11px] text-[#8692b1]">Insight Points</span>
          <strong className="text-sm text-white font-mono">{currentIp.toLocaleString()}</strong>
        </div>

        <button
          type="button"
          onClick={onOpenSettings}
          className="relative rounded-xl border border-[#273354] bg-[#111932] p-2.5 text-[#9ba6c3] hover:text-white transition-colors"
          aria-label="Settings"
          title="Arena Settings"
        >
          <Settings size={17} />
        </button>

        {/* Guest Mode Profile Overview */}
        <button
          type="button"
          onClick={onOpenSettings}
          className="hidden items-center gap-2.5 sm:flex border-l border-[#1c2745] pl-4 text-left group"
        >
          <div className="flex size-8 items-center justify-center rounded-xl bg-gradient-to-br from-[#7153ed] to-[#9e67ff] text-xs font-black text-white">
            {playerInitials}
          </div>
          <div className="hidden text-left md:block">
            <p className="text-xs font-bold text-white leading-tight group-hover:text-[#9e67ff] transition-colors">
              {playerName}
            </p>
            <p className="text-[10px] text-[#6d7895] font-mono">{levelText}</p>
          </div>
          <ChevronDown size={14} className="text-[#73809e] group-hover:text-white transition-colors" />
        </button>
      </div>
    </header>
  )
}

export function OmniQuestApp() {
  const [screen, setScreen] = useState<Screen>({ name: 'setup' })
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [isHowToOpen, setIsHowToOpen] = useState(false)
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)

  // Real guest player stats
  const [stats, setStats] = useState<PlayerStats | null>(null)

  function refreshStats() {
    setStats(getPlayerStats())
  }

  useEffect(() => {
    refreshStats()
  }, [])

  // In active gameplay arena, render the fixed-viewport 3-column game directly
  if (screen.name === 'playing') {
    return (
      <GameplayArena
        sessionId={screen.sessionId}
        topic={screen.topic}
        difficulty={screen.difficulty}
        gauntlet={screen.gauntlet}
        fallbackMessage={screen.fallbackMessage}
        onComplete={(answers, elimination, isForfeit) => {
          setScreen({
            name: 'results',
            topic: screen.topic,
            difficulty: screen.difficulty,
            answers,
            totalStages: screen.gauntlet.length,
            elimination,
            isForfeit,
          })
          refreshStats()
        }}
      />
    )
  }

  const currentViewTitle =
    screen.name === 'results'
      ? 'Run complete'
      : screen.name === 'trophies'
        ? screen.tab === 'history'
          ? 'Game history'
          : 'Trophy room'
        : 'Setup hub'

  const currentTab = screen.name === 'trophies' ? screen.tab ?? 'trophies' : undefined

  return (
    <div className="app-shell flex h-dvh max-h-dvh w-full overflow-hidden bg-[#080e20] text-[#edf1ff]">
      {/* Left Navigation Sidebar */}
      <SideNav
        currentView={screen.name}
        currentTab={currentTab}
        stats={stats}
        onNavigate={(view, tab) =>
          setScreen(view === 'trophies' ? { name: 'trophies', tab: tab || 'trophies' } : { name: 'setup' })
        }
        onHowTo={() => setIsHowToOpen(true)}
        onSettings={() => setIsSettingsOpen(true)}
      />

      {/* Main Viewport Column */}
      <div className="flex min-w-0 flex-1 flex-col h-full overflow-hidden">
        <TopBar
          title={currentViewTitle}
          stats={stats}
          onOpenMenu={() => setMobileMenuOpen(true)}
          onOpenSettings={() => setIsSettingsOpen(true)}
        />

        {/* View Switcher */}
        {screen.name === 'setup' && (
          <SetupScreen
            onStart={({ sessionId, topic, gauntlet, fallbackMessage, difficulty }) =>
              setScreen({
                name: 'playing',
                sessionId,
                topic,
                difficulty,
                gauntlet,
                fallbackMessage,
              })
            }
            onHowTo={() => setIsHowToOpen(true)}
          />
        )}

        {screen.name === 'results' && (
          <ResultsScreen
            topic={screen.topic}
            difficulty={screen.difficulty}
            answers={screen.answers}
            totalStages={screen.totalStages}
            elimination={screen.elimination}
            isForfeit={screen.isForfeit}
            onPlayAgain={() => {
              setScreen({ name: 'setup' })
              refreshStats()
            }}
            onHome={() => {
              setScreen({ name: 'setup' })
              refreshStats()
            }}
            onTrophies={() => {
              setScreen({ name: 'trophies', tab: 'trophies' })
              refreshStats()
            }}
          />
        )}

        {screen.name === 'trophies' && (
          <TrophyRoom
            initialTab={screen.tab || 'trophies'}
            onPlay={() => setScreen({ name: 'setup' })}
          />
        )}
      </div>

      {/* Mobile Drawer Menu */}
      {mobileMenuOpen && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 bg-[#050916]/80 backdrop-blur-sm lg:hidden animate-in fade-in duration-150"
          onClick={() => setMobileMenuOpen(false)}
        >
          <div
            className="h-full w-[270px] bg-[#0a1024] p-5 shadow-2xl flex flex-col justify-between"
            onClick={(e) => e.stopPropagation()}
          >
            <div>
              <div className="flex items-center justify-between border-b border-[#1c2745] pb-4">
                <Logo />
                <button
                  type="button"
                  onClick={() => setMobileMenuOpen(false)}
                  className="rounded-lg p-1 text-[#7783a1] hover:text-white"
                  aria-label="Close menu"
                >
                  <X size={18} />
                </button>
              </div>

              <div className="mt-6 space-y-1.5">
                <button
                  type="button"
                  onClick={() => {
                    setScreen({ name: 'setup' })
                    setMobileMenuOpen(false)
                  }}
                  className={`nav-item ${screen.name === 'setup' ? 'active' : ''}`}
                >
                  <Home size={18} />
                  <span>Home / Setup Hub</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setScreen({ name: 'trophies', tab: 'trophies' })
                    setMobileMenuOpen(false)
                  }}
                  className={`nav-item ${
                    screen.name === 'trophies' && screen.tab !== 'history' ? 'active' : ''
                  }`}
                >
                  <Trophy size={18} />
                  <span>Trophy Room</span>
                  {stats && stats.unlockedAchievementsCount > 0 && (
                    <span className="ml-auto rounded-md bg-[#e9ad43] px-1.5 text-[10px] font-black text-[#161326]">
                      {stats.unlockedAchievementsCount}
                    </span>
                  )}
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setScreen({ name: 'trophies', tab: 'history' })
                    setMobileMenuOpen(false)
                  }}
                  className={`nav-item ${
                    screen.name === 'trophies' && screen.tab === 'history' ? 'active' : ''
                  }`}
                >
                  <History size={18} />
                  <span>Game History</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setIsHowToOpen(true)
                    setMobileMenuOpen(false)
                  }}
                  className="nav-item"
                >
                  <CircleHelp size={18} />
                  <span>How to Play</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setIsSettingsOpen(true)
                    setMobileMenuOpen(false)
                  }}
                  className="nav-item"
                >
                  <Settings size={18} />
                  <span>Settings</span>
                </button>
              </div>
            </div>

            <div className="border-t border-[#1c2745] pt-4">
              <div className="flex items-center justify-between text-[10px] font-bold text-[#65718d]">
                <span>OMNIQUEST v1.0</span>
                <span className="flex items-center gap-1.5 text-[#71e9ab]">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#71e9ab] animate-pulse" />
                  ONLINE
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Global How to Play Modal */}
      <HowToPlayModal
        isOpen={isHowToOpen}
        onClose={() => setIsHowToOpen(false)}
        onStart={() => {
          setScreen({ name: 'setup' })
        }}
      />

      {/* Global Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        stats={stats || getPlayerStats()}
        onClose={() => setIsSettingsOpen(false)}
        onDataReset={refreshStats}
      />
    </div>
  )
}

'use client'

import { useEffect, useState } from 'react'
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  HardDrive,
  Info,
  RotateCcw,
  Settings,
  Sparkles,
  Trash2,
  User,
  Volume2,
  VolumeX,
  X,
} from 'lucide-react'
import {
  STORAGE_KEY_HISTORY,
  clearAllGuestData,
  getUserSettings,
  saveUserSettings,
  type PlayerStats,
  type UserSettings,
} from '@/lib/game-storage'
import { API_BASE_URL } from '@/lib/api'

interface SettingsModalProps {
  isOpen: boolean
  stats: PlayerStats
  onClose: () => void
  onDataReset: () => void
}

export function SettingsModal({
  isOpen,
  stats,
  onClose,
  onDataReset,
}: SettingsModalProps) {
  const [settings, setSettings] = useState<UserSettings>({
    soundEnabled: true,
    reducedMotion: false,
  })
  const [isConfirmingReset, setIsConfirmingReset] = useState(false)
  const [resetSuccess, setResetSuccess] = useState(false)

  useEffect(() => {
    if (isOpen) {
      setSettings(getUserSettings())
      setIsConfirmingReset(false)
      setResetSuccess(false)
    }
  }, [isOpen])

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

  function handleToggleSound() {
    const updated = saveUserSettings({ soundEnabled: !settings.soundEnabled })
    setSettings(updated)
  }

  function handleToggleMotion() {
    const updated = saveUserSettings({ reducedMotion: !settings.reducedMotion })
    setSettings(updated)
  }

  function handleExecuteReset() {
    clearAllGuestData()
    setResetSuccess(true)
    setIsConfirmingReset(false)
    onDataReset()
    setTimeout(() => {
      setResetSuccess(false)
    }, 2500)
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#050916]/85 p-4 backdrop-blur-md animate-in fade-in duration-150"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        className="panel relative flex max-h-[90dvh] w-full max-w-lg flex-col p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#1c2745] pb-4 shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="flex size-8 items-center justify-center rounded-lg bg-[#2a205d] text-[#9e67ff] border border-[#7256c7]/40">
              <Settings size={18} />
            </div>
            <div>
              <h2 id="settings-modal-title" className="text-lg font-bold tracking-tight text-white">
                Arena Settings
              </h2>
              <p className="text-[11px] text-[#707c99]">Preferences & Local Guest Data</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-[#7783a1] transition-colors hover:bg-[#141d3a] hover:text-white"
            aria-label="Close settings"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 space-y-5 overflow-y-auto py-5 pr-1 text-xs text-[#8b97b3]">
          {/* Guest Identity Overview */}
          <section className="rounded-xl border border-[#243354] bg-[#111932] p-4">
            <div className="flex items-center gap-3">
              <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-[#7153ed] to-[#9e67ff] font-mono text-sm font-black text-white">
                {stats.playerInitials}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="font-bold text-white text-sm">{stats.playerName}</h3>
                  <span className="rounded bg-[#212c4c] px-1.5 py-0.5 text-[10px] font-mono text-[#75e9ae]">
                    {stats.levelTitle}
                  </span>
                </div>
                <p className="mt-0.5 text-[11px] text-[#74809d]">
                  Guest Session · {stats.totalIp.toLocaleString()} IP banked · {stats.gamesPlayed} runs completed
                </p>
              </div>
            </div>
          </section>

          {/* Preferences */}
          <section className="space-y-3">
            <p className="eyebrow">Audio & Experience</p>

            <div className="flex items-center justify-between rounded-xl border border-[#202f51] bg-[#101a34] p-3.5">
              <div className="flex items-center gap-3">
                <span className="flex size-7 items-center justify-center rounded-lg bg-[#243354] text-[#a78aff]">
                  {settings.soundEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
                </span>
                <div>
                  <strong className="block text-white text-xs">Arena Sound Effects</strong>
                  <span className="text-[10px] text-[#707c99]">Timer alarms & submission audio</span>
                </div>
              </div>
              <button
                type="button"
                onClick={handleToggleSound}
                className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                  settings.soundEnabled ? 'bg-[#9e67ff]' : 'bg-[#29385c]'
                }`}
                aria-label="Toggle sound effects"
              >
                <span
                  className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out ${
                    settings.soundEnabled ? 'translate-x-4' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>

            <div className="flex items-center justify-between rounded-xl border border-[#202f51] bg-[#101a34] p-3.5">
              <div className="flex items-center gap-3">
                <span className="flex size-7 items-center justify-center rounded-lg bg-[#243354] text-[#a78aff]">
                  <Sparkles size={16} />
                </span>
                <div>
                  <strong className="block text-white text-xs">Reduced Motion</strong>
                  <span className="text-[10px] text-[#707c99]">Minimize visual background pulses</span>
                </div>
              </div>
              <button
                type="button"
                onClick={handleToggleMotion}
                className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                  settings.reducedMotion ? 'bg-[#9e67ff]' : 'bg-[#29385c]'
                }`}
                aria-label="Toggle reduced motion"
              >
                <span
                  className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out ${
                    settings.reducedMotion ? 'translate-x-4' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>
          </section>

          {/* Local Data Management */}
          <section className="space-y-3">
            <p className="eyebrow">Local Storage Management</p>

            <div className="rounded-xl border border-[#202f51] bg-[#101a34] p-3.5 space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <HardDrive size={16} className="text-[#e9ad43]" />
                  <div>
                    <strong className="block text-white text-xs">Guest Play History</strong>
                    <span className="text-[10px] text-[#707c99]">
                      Key: <code className="text-[#aeb8d1] font-mono">{STORAGE_KEY_HISTORY}</code>
                    </span>
                  </div>
                </div>
                <span className="text-[10px] font-mono text-[#73e6a8]">Active</span>
              </div>

              {resetSuccess ? (
                <div className="flex items-center gap-2 rounded-lg bg-[#153c37] p-2 text-xs font-bold text-[#75e9ae]">
                  <CheckCircle2 size={15} />
                  <span>All local records and statistics have been reset.</span>
                </div>
              ) : isConfirmingReset ? (
                <div className="space-y-2 rounded-lg border border-[#f16e8d]/40 bg-[#3a1824] p-3 text-xs text-[#ffb9c5]">
                  <p className="font-bold flex items-center gap-1.5 text-[#f16e8d]">
                    <AlertTriangle size={14} /> Clear all local records?
                  </p>
                  <p className="text-[11px] leading-relaxed text-[#dfa9b4]">
                    This will permanently clear your game history, personal best, and reset your level to Level 01.
                  </p>
                  <div className="flex gap-2 pt-1">
                    <button
                      type="button"
                      onClick={handleExecuteReset}
                      className="rounded-lg bg-[#bd566b] px-3 py-1.5 text-xs font-bold text-white transition-opacity hover:opacity-90"
                    >
                      Yes, Clear Data
                    </button>
                    <button
                      type="button"
                      onClick={() => setIsConfirmingReset(false)}
                      className="rounded-lg border border-[#4d2432] bg-[#221017] px-3 py-1.5 text-xs text-[#c0a2ab] hover:text-white"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => setIsConfirmingReset(true)}
                  className="flex items-center gap-1.5 text-[11px] font-bold text-[#f16e8d] hover:text-white transition-colors"
                >
                  <Trash2 size={13} />
                  <span>Reset guest statistics and history</span>
                </button>
              )}
            </div>
          </section>

          {/* System Info */}
          <section className="rounded-xl border border-[#1c2745] bg-[#0c1328] p-3.5 space-y-1.5 font-mono text-[10px] text-[#6d7895]">
            <div className="flex justify-between">
              <span>App Version:</span>
              <span className="text-white">OmniQuest v1.0.0</span>
            </div>
            <div className="flex justify-between">
              <span>Backend API:</span>
              <span className="text-white truncate max-w-[200px]">{API_BASE_URL}</span>
            </div>
            <div className="flex justify-between">
              <span>Mode:</span>
              <span className="text-[#75e9ae]">Client-Side Sandboxed Guest</span>
            </div>
          </section>
        </div>

        {/* Footer */}
        <div className="border-t border-[#1c2745] pt-4 flex justify-end shrink-0">
          <button
            type="button"
            onClick={onClose}
            className="secondary-button justify-center px-6"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  )
}

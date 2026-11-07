'use client'

import { useEffect, useRef, useState } from 'react'
import {
  AlertCircle,
  ArrowRight,
  BookOpen,
  Brain,
  Check,
  CircleHelp,
  Clock,
  Flame,
  Loader2,
  Play,
  ShieldCheck,
  Sparkles,
  Target,
  Upload,
  X,
  Zap,
} from 'lucide-react'
import { generateGame, uploadDocument } from '@/lib/api'
import type { PublicQuestion } from '@/lib/quiz-data'
import { formatDuration, getPlayerStats, type PlayerStats } from '@/lib/game-storage'
import { HowToPlayModal } from './how-to-play-modal'

export type Difficulty = 'Easy' | 'Medium' | 'Hard' | 'Expert'
export type GenerationMode = 'strict' | 'enhanced'

const SUGGESTED_TOPICS = ['Data Structures', 'Web Fundamentals', 'Astronomy']
const SUGGESTED_LEVELS = ['10th Grade', 'Beginner', 'Expert', 'Pop Culture']

interface SetupScreenProps {
  onStart: (params: {
    sessionId: string
    topic: string
    gauntlet: PublicQuestion[]
    fallbackMessage?: string
    difficulty: Difficulty
    totalStages: number
  }) => void
  onHowTo?: () => void
}

export function SetupScreen({ onStart, onHowTo }: SetupScreenProps) {
  // Clean inputs without arbitrary demo defaults
  const [topic, setTopic] = useState('')
  const [targetLevel, setTargetLevel] = useState('')
  const [difficulty, setDifficulty] = useState<Difficulty>('Medium')
  const [mode, setMode] = useState<GenerationMode>('enhanced')
  const [length, setLength] = useState<number>(20)

  // Real player stats from localStorage
  const [stats, setStats] = useState<PlayerStats | null>(null)

  // Document upload state
  const [uploadedFile, setUploadedFile] = useState<{
    name: string
    sizeLabel: string
    text: string
  } | null>(null)
  const [isUploadingDoc, setIsUploadingDoc] = useState(false)
  const [docError, setDocError] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)

  // Gauntlet generation state
  const [isLoading, setIsLoading] = useState(false)
  const [showColdStartWarning, setShowColdStartWarning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isHowToPlayOpen, setIsHowToPlayOpen] = useState(false)

  const coldStartTimerRef = useRef<number | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    setStats(getPlayerStats())
  }, [])

  useEffect(() => {
    return () => {
      if (coldStartTimerRef.current !== null) {
        window.clearTimeout(coldStartTimerRef.current)
      }
    }
  }, [])

  async function handleFileProcess(file: File) {
    if (!file) return
    setIsUploadingDoc(true)
    setDocError(null)

    try {
      const response = await uploadDocument(file)
      const sizeKb = Math.round(file.size / 1024)
      const sizeLabel = sizeKb > 1024 ? `${(sizeKb / 1024).toFixed(1)} MB` : `${sizeKb} KB`

      setUploadedFile({
        name: response.filename,
        sizeLabel: `${sizeLabel} · ${response.word_count.toLocaleString()} words`,
        text: response.text,
      })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to parse uploaded document.'
      setDocError(msg)
    } finally {
      setIsUploadingDoc(false)
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) {
      handleFileProcess(file)
    }
  }

  function handleDrop(e: React.DragEvent<HTMLLabelElement>) {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files?.[0]
    if (file) {
      handleFileProcess(file)
    }
  }

  const trimmedTopic = topic.trim()

  async function handleSubmit(event?: React.FormEvent) {
    if (event) event.preventDefault()
    if (!trimmedTopic || isLoading || isUploadingDoc) return

    setIsLoading(true)
    setError(null)
    setShowColdStartWarning(false)

    // Trigger cold-start warning after 5s of waiting
    coldStartTimerRef.current = window.setTimeout(() => {
      setShowColdStartWarning(true)
    }, 5000)

    try {
      const baseLevel = targetLevel.trim() || 'General'
      const combinedLevel = `${baseLevel} - ${difficulty} Level`
      const generationModeParam =
        mode === 'strict' && uploadedFile?.text
          ? 'Strict Material Only'
          : 'AI Enhanced'

      const response = await generateGame(trimmedTopic, combinedLevel, {
        question_count: length,
        difficulty,
        source_text: uploadedFile?.text || null,
        generation_mode: generationModeParam,
      })

      if (coldStartTimerRef.current !== null) {
        window.clearTimeout(coldStartTimerRef.current)
        coldStartTimerRef.current = null
      }
      setShowColdStartWarning(false)

      if (!response.gauntlet || response.gauntlet.length === 0) {
        throw new Error('Received an empty gauntlet from the server.')
      }

      onStart({
        sessionId: response.session_id,
        topic: response.topic,
        gauntlet: response.gauntlet,
        fallbackMessage: response.is_fallback
          ? (response.message ?? 'API unavailable, loaded sample round.')
          : undefined,
        difficulty,
        totalStages: response.gauntlet.length,
      })
    } catch (err: unknown) {
      if (coldStartTimerRef.current !== null) {
        window.clearTimeout(coldStartTimerRef.current)
        coldStartTimerRef.current = null
      }
      setShowColdStartWarning(false)
      setIsLoading(false)

      const message =
        err instanceof Error
          ? err.message
          : 'Failed to generate gauntlet. Please verify the backend is running and try again.'
      setError(message)
    }
  }

  return (
    <div className="flex-1 min-h-0 overflow-y-auto px-4 py-4 sm:px-6 sm:py-5 lg:px-8">
      <div className="mx-auto max-w-[1080px] space-y-5 pb-8">
        {/* Hero Section */}
        <section className="hero relative overflow-hidden rounded-2xl border border-[#2c3a63] p-5 sm:p-7 min-h-[210px]">
          <div className="hero-orbit orbit-one" aria-hidden="true" />
          <div className="hero-orbit orbit-two" aria-hidden="true" />

          <div className="relative z-10 max-w-[540px]">
            <div className="mb-3.5 inline-flex items-center gap-2 rounded-full border border-[#5b4cb4]/50 bg-[#392b79]/35 px-3 py-1 text-[10px] font-black tracking-[0.18em] text-[#bfadff]">
              <Sparkles size={12} /> SEASON 01 · THE AWAKENING
            </div>
            <h1 className="max-w-[500px] text-2xl font-black leading-[1.02] tracking-[-0.04em] text-white sm:text-4xl">
              YOUR KNOWLEDGE.<br />
              <span className="text-[#75e9ae]">YOUR ARENA.</span>
            </h1>
            <p className="mt-3 max-w-[420px] text-xs sm:text-sm leading-relaxed text-[#b5bdd3]">
              Challenge your limits. Conquer every tier. Earn{' '}
              <span className="font-bold text-[#e9ad43]">Insight Points</span> with every verified answer.
            </p>
            <button
              type="button"
              onClick={() => handleSubmit()}
              disabled={isLoading || !trimmedTopic}
              className="mt-5 primary-button"
            >
              <Play size={14} fill="currentColor" /> Enter the arena <ArrowRight size={14} />
            </button>
          </div>

          <div className="hero-visual" aria-hidden="true">
            <div className="neon-ring ring-a" />
            <div className="neon-ring ring-b" />
            <div className="brain-shape">
              <Brain size={100} strokeWidth={1} />
            </div>
            <div className="float-chip chip-a">
              <Target size={18} />
            </div>
            <div className="float-chip chip-b">
              <Zap size={16} />
            </div>
          </div>
        </section>

        {/* Configuration Hub & Daily Challenge Grid */}
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_310px]">
          {/* Main Configuration Panel */}
          <section className="panel p-5 sm:p-6">
            <div className="mb-5 flex items-start justify-between">
              <div>
                <p className="eyebrow">Configure your run</p>
                <h2 className="mt-1 text-lg sm:text-xl font-black text-white">Build your knowledge gauntlet</h2>
              </div>
              <div className="hidden rounded-lg border border-[#29385e] bg-[#121c38] px-3 py-1.5 text-right sm:block">
                <div className="text-[10px] font-bold uppercase tracking-wider text-[#73809e]">EST. REWARD</div>
                <div className="text-xs sm:text-sm font-black text-[#e9ad43]">+{length * 100} IP</div>
              </div>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Topic & Target Level Inputs */}
              <div className="grid gap-3.5 sm:grid-cols-2">
                <div>
                  <label htmlFor="topic-input" className="field-label">
                    Topic <span className="text-[#f16e8d]">*</span>
                  </label>
                  <input
                    id="topic-input"
                    value={topic}
                    onChange={(e) => {
                      setTopic(e.target.value)
                      if (error) setError(null)
                    }}
                    maxLength={50}
                    disabled={isLoading}
                    className="field-input"
                    placeholder="e.g. Data Structures, Quantum Computing..."
                  />
                  <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                    <span className="text-[10px] text-[#707c99]">Suggestions:</span>
                    {SUGGESTED_TOPICS.map((suggestion) => (
                      <button
                        key={suggestion}
                        type="button"
                        onClick={() => {
                          setTopic(suggestion)
                          if (error) setError(null)
                        }}
                        disabled={isLoading}
                        className="rounded-md border border-[#243354] bg-[#111932] px-2 py-0.5 text-[10px] text-[#8e9ab6] transition-colors hover:border-[#8663df] hover:text-white disabled:opacity-50"
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between">
                    <label htmlFor="level-input" className="field-label">
                      Target level / context
                    </label>
                    <span className="text-[10px] text-[#697593]">Optional</span>
                  </div>
                  <input
                    id="level-input"
                    value={targetLevel}
                    onChange={(e) => {
                      setTargetLevel(e.target.value)
                      if (error) setError(null)
                    }}
                    maxLength={50}
                    disabled={isLoading}
                    className="field-input"
                    placeholder="e.g. Beginner, 10th Grade, Expert..."
                  />
                  <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                    <span className="text-[10px] text-[#707c99]">Examples:</span>
                    {SUGGESTED_LEVELS.map((level) => (
                      <button
                        key={level}
                        type="button"
                        onClick={() => {
                          setTargetLevel(level)
                          if (error) setError(null)
                        }}
                        disabled={isLoading}
                        className="rounded-md border border-[#243354] bg-[#111932] px-2 py-0.5 text-[10px] text-[#8e9ab6] transition-colors hover:border-[#8663df] hover:text-white disabled:opacity-50"
                      >
                        {level}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Difficulty Selector */}
              <div>
                <div className="field-label mb-1.5">Difficulty</div>
                <div className="grid grid-cols-4 gap-2">
                  {(['Easy', 'Medium', 'Hard', 'Expert'] as Difficulty[]).map((item, i) => (
                    <button
                      key={item}
                      type="button"
                      onClick={() => setDifficulty(item)}
                      disabled={isLoading}
                      className={`choice-button ${difficulty === item ? 'selected' : ''}`}
                    >
                      <span className={`difficulty-dot d-${i}`} />
                      {item}
                    </button>
                  ))}
                </div>
              </div>

              {/* Reference Material Upload */}
              <div>
                <div className="field-label mb-1.5 flex items-center justify-between">
                  <span>Reference material</span>
                  <span className="font-normal normal-case tracking-normal text-[#697593]">
                    PDF, DOCX, PPTX, TXT · Max 25MB (Optional)
                  </span>
                </div>

                {isUploadingDoc ? (
                  <div className="file-selected justify-center">
                    <Loader2 size={18} className="animate-spin text-[#a78aff]" />
                    <span className="text-xs text-[#aeb8d1]">Parsing document content...</span>
                  </div>
                ) : uploadedFile ? (
                  <div className="file-selected">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#2b276d] text-[#a78aff]">
                      <BookOpen size={18} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-xs font-bold text-white">{uploadedFile.name}</p>
                      <p className="mt-0.5 text-[10px] text-[#7582a0]">{uploadedFile.sizeLabel} · Ready</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setUploadedFile(null)
                        setDocError(null)
                        if (fileInputRef.current) fileInputRef.current.value = ''
                      }}
                      className="text-[#6e7a96] transition-colors hover:text-white"
                      aria-label="Remove uploaded file"
                    >
                      <X size={16} />
                    </button>
                  </div>
                ) : (
                  <label
                    onDragOver={(e) => {
                      e.preventDefault()
                      setIsDragging(true)
                    }}
                    onDragLeave={() => setIsDragging(false)}
                    onDrop={handleDrop}
                    className={`upload-box cursor-pointer transition-colors ${
                      isDragging ? 'border-[#8a65e7] bg-[#1d224d]' : ''
                    }`}
                  >
                    <Upload size={18} className="text-[#a883ff]" />
                    <span className="text-xs font-bold text-[#c1c8dc]">
                      Drop material here or <span className="text-[#9d76ff]">browse files</span>
                    </span>
                    <span className="text-[10px] text-[#677491]">
                      Generates questions grounded in your course materials
                    </span>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".pdf,.docx,.pptx,.txt"
                      className="sr-only"
                      onChange={handleFileChange}
                    />
                  </label>
                )}

                {docError && (
                  <p className="mt-1.5 text-xs text-[#f16e8d]">{docError}</p>
                )}
              </div>

              {/* Generation Mode Toggle */}
              <div>
                <div className="field-label mb-1.5">Generation mode</div>
                <div className="mode-grid">
                  <button
                    type="button"
                    onClick={() => setMode('strict')}
                    disabled={!uploadedFile}
                    title={!uploadedFile ? 'Upload a reference document first to enable strict mode' : undefined}
                    className={`mode-button ${mode === 'strict' ? 'selected' : ''} ${
                      !uploadedFile ? 'opacity-40 cursor-not-allowed' : ''
                    }`}
                  >
                    <ShieldCheck size={18} />
                    <span>
                      <strong>Strict material only</strong>
                      <small>Questions stay strictly inside your upload</small>
                    </span>
                    {mode === 'strict' && <Check size={15} className="ml-auto" />}
                  </button>

                  <button
                    type="button"
                    onClick={() => setMode('enhanced')}
                    className={`mode-button ${mode === 'enhanced' ? 'selected' : ''}`}
                  >
                    <Sparkles size={18} />
                    <span>
                      <strong>AI enhanced</strong>
                      <small>Fill gaps with broader foundational knowledge</small>
                    </span>
                    {mode === 'enhanced' && <Check size={15} className="ml-auto" />}
                  </button>
                </div>
              </div>

              {/* Gauntlet Length Selector */}
              <div>
                <div className="flex items-center justify-between">
                  <div className="field-label">Gauntlet length</div>
                  <span className="text-[11px] font-bold text-[#9d83f8]">
                    {length / 5} {length === 5 ? 'tier' : 'tiers'} · {length} questions
                  </span>
                </div>
                <div className="mt-1.5 grid grid-cols-4 gap-2">
                  {[5, 10, 15, 20].map((n) => (
                    <button
                      key={n}
                      type="button"
                      onClick={() => setLength(n)}
                      disabled={isLoading}
                      className={`length-button ${length === n ? 'selected' : ''}`}
                    >
                      <strong>{n}</strong>
                      <span>questions</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Cold Start Server Warning */}
              {isLoading && showColdStartWarning && (
                <div
                  role="status"
                  aria-live="polite"
                  className="flex items-start gap-3 rounded-xl border border-amber-500/40 bg-amber-500/15 p-3.5 text-xs text-amber-200 animate-in fade-in"
                >
                  <Clock className="size-4 shrink-0 text-amber-400 animate-pulse mt-0.5" aria-hidden="true" />
                  <div className="flex-1 text-left">
                    <p className="font-semibold text-amber-300">Server Cold Start</p>
                    <p className="mt-0.5 text-[11px] text-amber-200/90 leading-relaxed">
                      Waking up the server... this might take 40-50 seconds on the first run.
                    </p>
                  </div>
                </div>
              )}

              {/* Error Message */}
              {error && (
                <div
                  role="alert"
                  className="flex items-start gap-3 rounded-xl border border-[#f16e8d]/50 bg-[#f16e8d]/15 p-3.5 text-xs text-[#f16e8d] animate-in fade-in"
                >
                  <AlertCircle className="size-4 shrink-0 mt-0.5" aria-hidden="true" />
                  <div className="flex-1 text-left">
                    <p className="font-semibold">Unable to initialize gauntlet</p>
                    <p className="mt-0.5 text-[11px] leading-relaxed opacity-90">{error}</p>
                  </div>
                </div>
              )}

              {/* Action Buttons */}
              <div className="mt-6 flex flex-col gap-2.5 pt-1 sm:flex-row">
                <button
                  type="submit"
                  disabled={!trimmedTopic || isLoading || isUploadingDoc}
                  className="primary-button flex-1 justify-center"
                >
                  {isLoading ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      Generating gauntlet...
                    </>
                  ) : (
                    <>
                      <Play size={14} fill="currentColor" /> Enter the arena
                    </>
                  )}
                </button>

                <button
                  type="button"
                  onClick={() => {
                    if (onHowTo) onHowTo()
                    else setIsHowToPlayOpen(true)
                  }}
                  disabled={isLoading}
                  className="secondary-button justify-center"
                >
                  <CircleHelp size={15} /> How to play
                </button>
              </div>
            </form>
          </section>

          {/* Real Personal Best & Daily Challenge Aside */}
          <aside className="space-y-4">
            <div className="panel p-4 sm:p-5">
              <p className="eyebrow">Personal best</p>
              <div className="mt-2.5 flex items-end gap-2">
                <span className="text-2xl sm:text-3xl font-black text-white font-mono">
                  {stats && stats.highestScore > 0 ? stats.highestScore.toLocaleString() : '0'}
                </span>
                <span className="mb-0.5 text-xs text-[#7f8aa7]">IP</span>
              </div>
              <div className="mt-2 text-[11px] text-[#73e7a8]">
                {stats && stats.gamesPlayed > 0
                  ? `${stats.gamesPlayed} completed run${stats.gamesPlayed > 1 ? 's' : ''}`
                  : 'Play a run to establish your record'}
              </div>
              <div className="mt-3.5 grid grid-cols-3 gap-1.5 sm:gap-2 text-center font-mono">
                <div className="stat-mini">
                  <strong>{stats && stats.bestAccuracy > 0 ? `${stats.bestAccuracy}%` : '0%'}</strong>
                  <span>accuracy</span>
                </div>
                <div className="stat-mini">
                  <strong>{stats ? stats.highestStreak : 0}</strong>
                  <span>best streak</span>
                </div>
                <div className="stat-mini">
                  <strong>
                    {stats && stats.bestTimeSeconds > 0
                      ? formatDuration(stats.bestTimeSeconds)
                      : '--:--'}
                  </strong>
                  <span>best time</span>
                </div>
              </div>
            </div>

            <div className="panel overflow-hidden p-4 sm:p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="eyebrow">Daily challenge</p>
                  <h3 className="mt-1 text-sm sm:text-base font-black text-white">The Signal Boost</h3>
                </div>
                <div className="rounded-lg bg-[#2c235c] p-2 text-[#b893ff]">
                  <Zap size={16} />
                </div>
              </div>
              <p className="mt-2 text-xs leading-5 text-[#8490ad]">
                Answer 3 questions in a row without using a power-up.
              </p>
              <div className="mt-3 flex items-end justify-between">
                <div>
                  <span className="text-lg font-black text-[#e9ad43]">+250</span>
                  <span className="ml-1 text-[10px] text-[#74809d]">IP bonus</span>
                </div>
                <div className="text-right">
                  <div className="text-[9px] font-bold text-[#74809d]">OBJECTIVE</div>
                  <div className="text-xs font-bold text-white">Active Daily</div>
                </div>
              </div>
            </div>

            <div className="status-card">
              <Flame
                size={22}
                className={stats && stats.activeDayStreak > 0 ? 'text-[#ff9d4d]' : 'text-[#5f6c89]'}
              />
              <div>
                <p className="text-xs font-black text-white">
                  {stats && stats.activeDayStreak > 0
                    ? 'Your streak is alive'
                    : 'Start your streak'}
                </p>
                <p className="mt-0.5 text-[10px] text-[#929db8]">
                  {stats && stats.activeDayStreak > 0
                    ? `${stats.activeDayStreak} day${stats.activeDayStreak > 1 ? 's' : ''} of showing up.`
                    : 'Enter the arena to build your daily streak.'}
                </p>
              </div>
            </div>
          </aside>
        </div>
      </div>

      {/* Functional How to Play Modal */}
      <HowToPlayModal
        isOpen={isHowToPlayOpen}
        onClose={() => setIsHowToPlayOpen(false)}
        onStart={() => handleSubmit()}
      />
    </div>
  )
}

'use client'

import { useState } from 'react'
import type { AnswerRecord, PublicQuestion, TierElimination } from '@/lib/quiz-data'
import { GameplayArena } from './gameplay-arena'
import { ResultsScreen } from './results-screen'
import { SetupScreen } from './setup-screen'

type Screen =
  | { name: 'setup' }
  | {
      name: 'playing'
      sessionId: string
      topic: string
      gauntlet: PublicQuestion[]
      fallbackMessage?: string
    }
  | {
      name: 'results'
      topic: string
      answers: AnswerRecord[]
      totalStages: number
      elimination?: TierElimination | null
      isForfeit?: boolean
    }

export function OmniQuestApp() {
  const [screen, setScreen] = useState<Screen>({ name: 'setup' })

  if (screen.name === 'playing') {
    return (
      <GameplayArena
        sessionId={screen.sessionId}
        topic={screen.topic}
        gauntlet={screen.gauntlet}
        fallbackMessage={screen.fallbackMessage}
        onComplete={(answers, elimination, isForfeit) =>
          setScreen({
            name: 'results',
            topic: screen.topic,
            answers,
            totalStages: screen.gauntlet.length,
            elimination,
            isForfeit,
          })
        }
      />
    )
  }

  if (screen.name === 'results') {
    return (
      <ResultsScreen
        topic={screen.topic}
        answers={screen.answers}
        totalStages={screen.totalStages}
        elimination={screen.elimination}
        isForfeit={screen.isForfeit}
        onPlayAgain={() => setScreen({ name: 'setup' })}
      />
    )
  }

  return (
    <SetupScreen
      onStart={({ sessionId, topic, gauntlet, fallbackMessage }) =>
        setScreen({
          name: 'playing',
          sessionId,
          topic,
          gauntlet,
          fallbackMessage,
        })
      }
    />
  )
}

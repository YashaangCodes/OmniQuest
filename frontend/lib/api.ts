export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000'

export interface PublicQuestion {
  stage: number
  tier: number
  question: string
  options: string[]
}

export interface GenerateGameResponse {
  session_id: string
  topic: string
  difficulty?: string
  power_up_limits?: {
    hint: number
    fifty_fifty: number
    time_freeze: number
  }
  question_count?: number
  gauntlet: PublicQuestion[]
  tier_checkpoints?: number[]
  tier_target_ip?: number
  is_fallback?: boolean
  message?: string
}

export interface GenerateGameOptions {
  question_count?: number
  difficulty?: 'Easy' | 'Medium' | 'Hard' | 'Expert'
  source_text?: string | null
  generation_mode?: 'Strict Material Only' | 'AI Enhanced'
}

export interface UploadDocumentResponse {
  filename: string
  text: string
  character_count: number
  word_count: number
}

export interface UseHintRequest {
  session_id: string
  stage_number: number
}

export interface UseHintResponse {
  hint?: string | null
  is_available?: boolean
  message?: string | null
  remaining_hints?: number
}

export interface UseFiftyFiftyRequest {
  session_id: string
  stage_number: number
}

export interface UseFiftyFiftyResponse {
  options_to_remove: string[]
  remaining_fifty_fifty?: number
}

export interface SubmitAnswerRequest {
  session_id: string
  stage_number: number
  selected_option: string
}

export interface SubmitAnswerResponse {
  is_correct: boolean
  correct_answer: string
  explanation: string
  current_streak?: number
  streak_fire_active?: boolean
  base_ip_awarded?: number
  bonus_ip_awarded?: number
  total_ip_awarded?: number
}

function extractErrorMessage(data: unknown, fallback: string): string {
  if (!data || typeof data !== 'object') return fallback

  const { detail } = data as { detail?: unknown }
  if (typeof detail === 'string' && detail.trim()) {
    return detail.trim()
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === 'string') return item.trim()
        if (item && typeof item === 'object' && 'msg' in item) {
          const msg = String(item.msg).trim()
          return msg.replace(/^Value error,\s*/i, '')
        }
        return null
      })
      .filter((msg): msg is string => Boolean(msg && msg.length > 0))

    if (messages.length > 0) {
      return messages.join('; ')
    }
  }

  return fallback
}

export async function uploadDocument(file: File): Promise<UploadDocumentResponse> {
  const formData = new FormData()
  formData.append('file', file)

  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}/upload-document`, {
      method: 'POST',
      body: formData,
    })
  } catch {
    throw new Error(
      `Unable to connect to the backend at ${API_BASE_URL}. Please ensure the server is running.`,
    )
  }

  if (!response.ok) {
    let errorDetail = `Document upload failed (${response.status})`
    try {
      const data = await response.json()
      errorDetail = extractErrorMessage(data, errorDetail)
    } catch {
      // Non-JSON response
    }
    throw new Error(errorDetail)
  }

  return response.json()
}

export async function generateGame(
  topic?: string | null,
  target_level: string = 'General',
  options?: GenerateGameOptions,
): Promise<GenerateGameResponse> {
  const normalizedTopic = topic ? topic.trim() : null
  const normalizedLevel = (target_level || '').trim() || 'General'

  const payload: Record<string, unknown> = {
    target_level: normalizedLevel,
  }

  if (normalizedTopic) {
    payload.topic = normalizedTopic
  }

  if (options?.question_count) {
    payload.question_count = options.question_count
  }
  if (options?.difficulty) {
    payload.difficulty = options.difficulty
  }
  if (options?.source_text) {
    payload.source_text = options.source_text
  }
  if (options?.generation_mode) {
    payload.generation_mode = options.generation_mode
  }

  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}/generate-game`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    })
  } catch (err: unknown) {
    const errorText =
      err instanceof Error && err.name === 'AbortError'
        ? 'Request timed out while contacting the server.'
        : `Unable to connect to the backend at ${API_BASE_URL}. Please ensure the server is running.`
    throw new Error(errorText)
  }

  if (!response.ok) {
    let errorDetail = `Generation failed (${response.status})`
    try {
      const data = await response.json()
      errorDetail = extractErrorMessage(data, errorDetail)
    } catch {
      // Non-JSON response
    }
    throw new Error(errorDetail)
  }

  return response.json()
}

export async function useHint(sessionId: string, stageNumber: number): Promise<UseHintResponse> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}/use-hint`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_id: sessionId,
        stage_number: stageNumber,
      }),
    })
  } catch {
    throw new Error(`Unable to connect to the backend at ${API_BASE_URL}.`)
  }

  if (!response.ok) {
    let errorDetail = `Hint request failed (${response.status})`
    try {
      const data = await response.json()
      errorDetail = extractErrorMessage(data, errorDetail)
    } catch {
      // Non-JSON response
    }
    throw new Error(errorDetail)
  }

  return response.json()
}

export async function useFiftyFifty(
  sessionId: string,
  stageNumber: number,
): Promise<UseFiftyFiftyResponse> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}/use-50-50`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_id: sessionId,
        stage_number: stageNumber,
      }),
    })
  } catch {
    throw new Error(`Unable to connect to the backend at ${API_BASE_URL}.`)
  }

  if (!response.ok) {
    let errorDetail = `50/50 request failed (${response.status})`
    try {
      const data = await response.json()
      errorDetail = extractErrorMessage(data, errorDetail)
    } catch {
      // Non-JSON response
    }
    throw new Error(errorDetail)
  }

  return response.json()
}

export async function submitAnswer(payload: SubmitAnswerRequest): Promise<SubmitAnswerResponse> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}/submit-answer`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    })
  } catch {
    throw new Error(
      `Unable to connect to the backend at ${API_BASE_URL}. Please check your connection.`,
    )
  }

  if (!response.ok) {
    let errorDetail = `Submission failed (${response.status})`
    try {
      const data = await response.json()
      errorDetail = extractErrorMessage(data, errorDetail)
    } catch {
      // Non-JSON response
    }
    throw new Error(errorDetail)
  }

  return response.json()
}

export async function forfeitGame(
  sessionId: string,
): Promise<{ session_id: string; status: string }> {
  try {
    const response = await fetch(`${API_BASE_URL}/forfeit-game`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ session_id: sessionId }),
    })
    if (!response.ok) {
      return { session_id: sessionId, status: 'failed' }
    }
    return response.json()
  } catch {
    return { session_id: sessionId, status: 'error' }
  }
}

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
  gauntlet: PublicQuestion[]
  is_fallback?: boolean
  message?: string
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

export async function generateGame(
  topic: string,
  target_level: string = 'General',
): Promise<GenerateGameResponse> {
  const normalizedTopic = topic.trim()
  const normalizedLevel = (target_level || '').trim() || 'General'

  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}/generate-game`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        topic: normalizedTopic,
        target_level: normalizedLevel,
      }),
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

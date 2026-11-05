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

export async function generateGame(topic: string): Promise<GenerateGameResponse> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}/generate-game`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ topic }),
    })
  } catch {
    throw new Error(
      `Unable to connect to the backend at ${API_BASE_URL}. Please ensure the server is running.`,
    )
  }

  if (!response.ok) {
    let errorDetail = `Generation failed (${response.status})`
    try {
      const data = await response.json()
      if (data && typeof data.detail === 'string') {
        errorDetail = data.detail
      }
    } catch {
      // Ignore JSON parse error on non-JSON response
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
      if (data && typeof data.detail === 'string') {
        errorDetail = data.detail
      }
    } catch {
      // Ignore JSON parse error on non-JSON response
    }
    throw new Error(errorDetail)
  }

  return response.json()
}

/**
 * Minimal typed-ish API client for the FastAPI backend.
 *
 * In development the Vite dev server proxies `/api` to
 * http://127.0.0.1:8000 (see vite.config.js), so a relative base works
 * without CORS configuration. For a production build, set
 * `VITE_API_BASE_URL` in a `.env` file.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'

class ApiError extends Error {
  constructor(message, { status, payload } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.payload = payload
  }
}

async function request(path, { method = 'GET', headers = {}, body } = {}) {
  const url = `${BASE_URL}${path}`

  const options = { method, headers: { accept: 'application/json', ...headers } }

  if (body instanceof FormData) {
    // Let the browser set the multipart boundary automatically.
    options.body = body
  } else if (body !== undefined) {
    options.headers['content-type'] = 'application/json'
    options.body = JSON.stringify(body)
  }

  let response
  try {
    response = await fetch(url, options)
  } catch (networkError) {
    throw new ApiError(`تعذر الاتصال بالخادم: ${networkError.message}`, { status: 0 })
  }

  if (!response.ok) {
    let payload = null
    try {
      payload = await response.json()
    } catch {
      payload = await response.text().catch(() => null)
    }
    throw new ApiError(payload?.detail ?? `خطأ من الخادم (${response.status})`, {
      status: response.status,
      payload,
    })
  }

  // 204 No Content — nothing to parse.
  if (response.status === 204) return null

  return response.json()
}

export const api = {
  /** Service liveness probe → { status, app, version, database, timestamp } */
  getHealth: () => request('/health'),

  get: (path) => request(path),
  post: (path, body) => request(path, { method: 'POST', body }),
  patch: (path, body) => request(path, { method: 'PATCH', body }),
  delete: (path) => request(path, { method: 'DELETE' }),

  /** Multipart upload (e.g. a lecture PDF/PPTX). */
  upload: (path, formData) => request(path, { method: 'POST', body: formData }),
}

export { ApiError }
export default api

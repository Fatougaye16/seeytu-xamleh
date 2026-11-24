import { ApiError, request } from './client'

export interface RegisterInput {
  firstName: string
  lastName: string
  username: string
  email: string
  password: string
}

export interface UserOut {
  id: number
  first_name: string
  last_name: string
  username: string
  email: string
  created_at: string
}

/**
 * POST /users/register.
 * The backend's UserCreate schema names the plain password `hashed_password` (it hashes it
 * server-side) and expects the client to send `created_at`.
 */
export async function register(input: RegisterInput): Promise<UserOut> {
  try {
    return await request<UserOut>('/users/register', {
      method: 'POST',
      body: {
        first_name: input.firstName,
        last_name: input.lastName,
        username: input.username,
        email: input.email,
        hashed_password: input.password,
        created_at: new Date().toISOString(),
      },
    })
  } catch (err) {
    // A duplicate username/email currently surfaces as an unhandled DB error (500).
    if (err instanceof ApiError && err.status === 500) {
      throw new ApiError('That username or email may already be taken.', 500)
    }
    throw err
  }
}

/**
 * POST /users/login.
 * The endpoint currently validates the full UserCreate body, so the unused fields are sent
 * empty; and a wrong password comes back as 200 with {error} rather than a 401.
 */
export async function login(username: string, password: string): Promise<string> {
  const res = await request<{ access_token?: string; error?: string }>('/users/login', {
    method: 'POST',
    body: {
      username,
      hashed_password: password,
      first_name: '',
      last_name: '',
      email: '',
      created_at: '',
    },
  })
  if (!res.access_token) throw new ApiError(res.error ?? 'Invalid username or password', 401)
  return res.access_token
}

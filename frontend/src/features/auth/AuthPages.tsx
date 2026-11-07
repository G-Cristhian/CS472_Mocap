import { useState, type FormEvent, type ReactNode } from 'react'
import { Link, Navigate, useLocation, useNavigate, useParams } from 'react-router-dom'
import { LogoMark } from '@/components/ui/Icons'
import { useAuth } from '@/app/AuthProvider'
import { confirmPasswordReset, requestPasswordReset } from '@/lib/auth'
import './auth.css'

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong. Try again.'
}

function AuthLayout({ title, footer, children }: { title: string; footer?: ReactNode; children: ReactNode }) {
  return (
    <main className="auth">
      <section className="card auth__card">
        <Link to="/" className="auth__brand">
          <LogoMark />
          <span>MotionBoxPro</span>
        </Link>
        <h1 className="auth__title">{title}</h1>
        {children}
        {footer && <p className="auth__footer">{footer}</p>}
      </section>
    </main>
  )
}

interface FieldProps {
  label: string
  type?: string
  value: string
  onChange: (value: string) => void
  autoComplete?: string
}

function Field({ label, type = 'text', value, onChange, autoComplete }: FieldProps) {
  return (
    <label className="field">
      <span className="field__label">{label}</span>
      <input
        className="input"
        type={type}
        value={value}
        autoComplete={autoComplete}
        required
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  )
}

export function LoginPage() {
  const { login, user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  // Where RequireAuth sent the visitor from, or the projects page if they came here directly
  const from = (location.state as { from?: { pathname: string } } | null)?.from?.pathname ?? '/projects'

  if (user) return <Navigate to={from} replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(email, password)
      navigate(from, { replace: true })
    } catch (err) {
      setError(messageOf(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout
      title="Log in"
      footer={
        <>
          <Link to="/forgot-password">Forgot password?</Link> · <Link to="/register">Create account</Link>
        </>
      }
    >
      <form className="auth__form" onSubmit={onSubmit}>
        <Field label="Email" type="email" autoComplete="email" value={email} onChange={setEmail} />
        <Field label="Password" type="password" autoComplete="current-password" value={password} onChange={setPassword} />
        {error && <p className="auth__error" role="alert">{error}</p>}
        <button className="btn btn--primary btn--block" type="submit" disabled={busy}>
          {busy ? 'Logging in…' : 'Log in'}
        </button>
      </form>
    </AuthLayout>
  )
}

export function RegisterPage() {
  const { register, user } = useAuth()
  const navigate = useNavigate()
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to="/projects" replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (password !== confirm) {
      setError("The two passwords don't match.")
      return
    }

    setBusy(true)
    setError(null)
    try {
      await register({ email, password, first_name: firstName, last_name: lastName })
      navigate('/projects', { replace: true })
    } catch (err) {
      setError(messageOf(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout title="Create account" footer={<>Already have an account? <Link to="/login">Log in</Link></>}>
      <form className="auth__form" onSubmit={onSubmit}>
        <Field label="First name" autoComplete="given-name" value={firstName} onChange={setFirstName} />
        <Field label="Last name" autoComplete="family-name" value={lastName} onChange={setLastName} />
        <Field label="Email" type="email" autoComplete="email" value={email} onChange={setEmail} />
        <Field label="Password" type="password" autoComplete="new-password" value={password} onChange={setPassword} />
        <Field label="Repeat password" type="password" autoComplete="new-password" value={confirm} onChange={setConfirm} />
        {error && <p className="auth__error" role="alert">{error}</p>}
        <button className="btn btn--primary btn--block" type="submit" disabled={busy}>
          {busy ? 'Creating account…' : 'Create account'}
        </button>
      </form>
    </AuthLayout>
  )
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      setMessage(await requestPasswordReset(email))
    } catch (err) {
      setError(messageOf(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout title="Forgot password" footer={<Link to="/login">Back to log in</Link>}>
      {message ? (
        <p className="auth__footer" role="status">{message}</p>
      ) : (
        <form className="auth__form" onSubmit={onSubmit}>
          <p className="auth__hint">Enter your email and we'll send you a link to choose a new password.</p>
          <Field label="Email" type="email" autoComplete="email" value={email} onChange={setEmail} />
          {error && <p className="auth__error" role="alert">{error}</p>}
          <button className="btn btn--primary btn--block" type="submit" disabled={busy}>
            {busy ? 'Sending…' : 'Send reset link'}
          </button>
        </form>
      )}
    </AuthLayout>
  )
}

export function ResetPasswordPage() {
  const { uid = '', token = '' } = useParams()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [done, setDone] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (password !== confirm) {
      setError("The two passwords don't match.")
      return
    }

    setBusy(true)
    setError(null)
    try {
      setDone(await confirmPasswordReset(uid, token, password))
    } catch (err) {
      setError(messageOf(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout title="Choose a new password" footer={done ? <Link to="/login">Go to log in</Link> : undefined}>
      {done ? (
        <p className="auth__footer" role="status">{done}</p>
      ) : (
        <form className="auth__form" onSubmit={onSubmit}>
          <Field label="New password" type="password" autoComplete="new-password" value={password} onChange={setPassword} />
          <Field label="Repeat password" type="password" autoComplete="new-password" value={confirm} onChange={setConfirm} />
          {error && <p className="auth__error" role="alert">{error}</p>}
          <button className="btn btn--primary btn--block" type="submit" disabled={busy}>
            {busy ? 'Saving…' : 'Save new password'}
          </button>
        </form>
      )}
    </AuthLayout>
  )
}

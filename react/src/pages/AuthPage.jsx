import { useState } from 'react'
import { ArrowRight, CheckCircle2, Lock, ShieldCheck, Sprout, User } from 'lucide-react'

function AuthPage({ t, onAuthSuccess, setPage, defaultMode = 'login' }) {
  const [mode, setMode] = useState(defaultMode) // 'login' or 'signup'
  const [loading, setLoading] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')
  const [successMsg, setSuccessMsg] = useState('')

  // Login form state
  const [identifier, setIdentifier] = useState('')
  const [loginPassword, setLoginPassword] = useState('')

  // Signup form state
  const [firstName, setFirstName] = useState('')
  const [fatherName, setFatherName] = useState('')
  const [phone, setPhone] = useState('')
  const [faydaId, setFaydaId] = useState('')
  const [region, setRegion] = useState('Arsi')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  async function handleLogin(e) {
    e.preventDefault()
    setErrorMsg('')
    setSuccessMsg('')

    if (!identifier.trim() || !loginPassword.trim()) {
      setErrorMsg('Please enter your Phone, Fayda ID, and Password.')
      return
    }

    setLoading(true)
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          identifier: identifier.trim(),
          password: loginPassword,
        }),
      })

      const data = await response.json()
      if (!response.ok || !data.success) {
        throw new Error(data.message || 'Login failed. Please check your credentials.')
      }

      onAuthSuccess(data.user, data.accessToken)
      if (data.user.role === 'moderator') {
        setPage('moderator')
      } else {
        setPage('dashboard')
      }
    } catch (err) {
      setErrorMsg(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleSignup(e) {
    e.preventDefault()
    setErrorMsg('')
    setSuccessMsg('')

    if (!firstName.trim() || !fatherName.trim()) {
      setErrorMsg('Please enter both First Name and Father Name.')
      return
    }

    const cleanPhone = phone.trim()
    if (!cleanPhone || cleanPhone.length < 9) {
      setErrorMsg('Please enter a valid phone number (at least 9 digits).')
      return
    }

    const cleanFayda = faydaId.trim().replace(/\s+/g, '')
    if (!/^\d{16}$/.test(cleanFayda)) {
      setErrorMsg('Fayda identification number must be exactly 16 numeric digits.')
      return
    }

    if (!password || password.length < 6) {
      setErrorMsg('Password must be at least 6 characters long.')
      return
    }

    if (password !== confirmPassword) {
      setErrorMsg('Passwords do not match. Please re-enter.')
      return
    }

    setLoading(true)
    try {
      const response = await fetch('/api/auth/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          firstName: firstName.trim(),
          fatherName: fatherName.trim(),
          phone: cleanPhone,
          faydaId: cleanFayda,
          password,
          region,
        }),
      })

      const data = await response.json()
      if (!response.ok || !data.success) {
        throw new Error(data.message || 'Registration failed.')
      }

      setSuccessMsg('Account registered successfully! Logging you in...')
      setTimeout(() => {
        onAuthSuccess(data.user, data.accessToken)
        setPage('dashboard')
      }, 700)
    } catch (err) {
      setErrorMsg(err.message)
    } finally {
      setLoading(false)
    }
  }

  function fillModeratorDemo() {
    setIdentifier('0911000000')
    setLoginPassword('moderator123')
    setErrorMsg('')
  }

  return (
    <section className="setup-page" style={{ maxWidth: '640px', margin: '0 auto' }}>
      <div className="setup-heading">
        <p className="eyebrow">{mode === 'login' ? 'NEBULA AUTHENTICATION' : 'FARMER REGISTRATION'}</p>
        <h1>
          {mode === 'login' ? (
            <>
              Welcome back <User size={28} style={{ display: 'inline', verticalAlign: 'middle' }} />
            </>
          ) : (
            <>
              Join Nebula <Sprout size={28} style={{ display: 'inline', verticalAlign: 'middle' }} />
            </>
          )}
        </h1>
        <p>
          {mode === 'login'
            ? 'Sign in to access your farm telemetry or the moderator regional overview.'
            : 'Register with your Ethiopian Fayda 16-digit ID and phone number for tailored regional advice.'}
        </p>
      </div>

      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.5rem' }}>
        <button
          type="button"
          className={mode === 'login' ? 'primary-button' : 'secondary-button'}
          style={{ flex: 1 }}
          onClick={() => {
            setMode('login')
            setErrorMsg('')
          }}
        >
          <Lock size={18} /> {t.login}
        </button>
        <button
          type="button"
          className={mode === 'signup' ? 'primary-button' : 'secondary-button'}
          style={{ flex: 1 }}
          onClick={() => {
            setMode('signup')
            setErrorMsg('')
          }}
        >
          <User size={18} /> {t.signup}
        </button>
      </div>

      {mode === 'login' ? (
        <form className="form-card" onSubmit={handleLogin}>
          <div className="form-grid">
            <label className="field" style={{ gridColumn: '1 / -1' }}>
              <span>{t.phoneNumber} / {t.faydaId}</span>
              <input
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder="Phone (0911...) or 16-digit Fayda ID"
                required
              />
            </label>
            <label className="field" style={{ gridColumn: '1 / -1' }}>
              <span>{t.password}</span>
              <input
                type="password"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                placeholder="Enter your password"
                required
              />
            </label>
          </div>

          {errorMsg && (
            <p className="notice-message" style={{ color: '#b91c1c', borderColor: '#fecaca', background: '#fef2f2' }} role="alert">
              {errorMsg}
            </p>
          )}

          <div style={{ marginTop: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <button className="primary-button" type="submit" disabled={loading} style={{ width: '100%' }}>
              {loading ? 'Signing in...' : t.login} <ArrowRight size={18} />
            </button>

            <button
              type="button"
              className="secondary-button"
              onClick={fillModeratorDemo}
              style={{ fontSize: '0.85rem' }}
            >
              <ShieldCheck size={16} /> Quick Fill Demo Moderator (0911000000 / moderator123)
            </button>
          </div>
        </form>
      ) : (
        <form className="form-card" onSubmit={handleSignup}>
          <div className="form-grid">
            <label className="field">
              <span>{t.firstName}</span>
              <input
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                placeholder="e.g. Abebe"
                required
              />
            </label>
            <label className="field">
              <span>{t.fatherName}</span>
              <input
                value={fatherName}
                onChange={(e) => setFatherName(e.target.value)}
                placeholder="e.g. Bikila"
                required
              />
            </label>

            <label className="field">
              <span>{t.phoneNumber}</span>
              <input
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder={t.phonePlaceholder}
                required
              />
            </label>

            <label className="field">
              <span>
                {t.faydaId}{' '}
                <small style={{ color: faydaId.trim().length === 16 ? 'var(--green)' : 'var(--muted)' }}>
                  ({faydaId.trim().length}/16)
                </small>
              </span>
              <input
                value={faydaId}
                onChange={(e) => setFaydaId(e.target.value)}
                placeholder={t.faydaPlaceholder}
                maxLength={16}
                required
              />
            </label>

            <label className="field" style={{ gridColumn: '1 / -1' }}>
              <span>{t.region}</span>
              <select value={region} onChange={(e) => setRegion(e.target.value)}>
                <option value="Arsi">Arsi ({t.wheat})</option>
                <option value="Bale">Bale ({t.wheat})</option>
                <option value="Jimma">Jimma ({t.coffee})</option>
              </select>
            </label>

            <label className="field">
              <span>{t.password}</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Min. 6 characters"
                required
              />
            </label>

            <label className="field">
              <span>{t.confirmPassword}</span>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter password"
                required
              />
            </label>
          </div>

          {errorMsg && (
            <p className="notice-message" style={{ color: '#b91c1c', borderColor: '#fecaca', background: '#fef2f2' }} role="alert">
              {errorMsg}
            </p>
          )}

          {successMsg && (
            <p className="notice-message" style={{ color: '#15803d', borderColor: '#bbf7d0', background: '#f0fdf4' }}>
              <CheckCircle2 size={16} style={{ display: 'inline', marginRight: '6px' }} />
              {successMsg}
            </p>
          )}

          <div className="form-actions" style={{ marginTop: '1.25rem' }}>
            <button type="button" className="text-button" onClick={() => setPage('welcome')}>
              {t.back}
            </button>
            <button className="primary-button" type="submit" disabled={loading}>
              {loading ? 'Registering...' : t.signup} <ArrowRight size={18} />
            </button>
          </div>
        </form>
      )}
    </section>
  )
}

export default AuthPage

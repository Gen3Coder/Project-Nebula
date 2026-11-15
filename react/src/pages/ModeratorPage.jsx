import { useEffect, useState } from 'react'
import {
  ArrowLeft,
  CheckCircle2,
  CloudRain,
  Droplets,
  MessageSquare,
  PlusCircle,
  RefreshCw,
  Send,
  Shield,
  Sprout,
  Thermometer,
  UserCheck,
  Users,
  Wind,
} from 'lucide-react'

function ModeratorPage({ t, setPage, currentUser }) {
  const [regions, setRegions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showRegisterForm, setShowRegisterForm] = useState(false)
  const [farmers, setFarmers] = useState([])

  // Register farmer form state
  const [firstName, setFirstName] = useState('')
  const [fatherName, setFatherName] = useState('')
  const [phone, setPhone] = useState('')
  const [faydaId, setFaydaId] = useState('')
  const [region, setRegion] = useState('Arsi')
  const [assignedPassword, setAssignedPassword] = useState('')
  const [regLoading, setRegLoading] = useState(false)
  const [regError, setRegError] = useState('')
  const [regSuccess, setRegSuccess] = useState('')

  // SMS Broadcast state
  const [smsLoading, setSmsLoading] = useState(false)
  const [smsResult, setSmsResult] = useState(null)
  const [smsError, setSmsError] = useState('')

  async function handleSendSMS(regionId = null) {
    setSmsLoading(true)
    setSmsError('')
    setSmsResult(null)

    try {
      const response = await fetch('/api/crops/send-sms', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(regionId ? { regionId } : {}),
      })
      const data = await response.json()
      if (!response.ok || !data.success || data.data?.success === false) {
        throw new Error(data.message || data.error || data.data?.errors?.[0]?.error || 'Failed to dispatch SMS')
      }
      setSmsResult(data.data || data)
    } catch (err) {
      setSmsError(err.message)
    } finally {
      setSmsLoading(false)
    }
  }

  async function fetchSummary() {
    setLoading(true)
    setError('')
    try {
      const res = await fetch('/api/moderator/summary')
      const data = await res.json()
      if (data.success && data.regions) {
        setRegions(data.regions)
      } else {
        throw new Error('Could not load regional summary.')
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function fetchFarmers() {
    try {
      const res = await fetch('/api/auth/moderator/farmers')
      const data = await res.json()
      if (data.success && data.farmers) {
        setFarmers(data.farmers)
      }
    } catch {
      // Non-critical
    }
  }

  useEffect(() => {
    fetchSummary()
    fetchFarmers()
  }, [])

  async function handleRegisterFarmer(e) {
    e.preventDefault()
    setRegError('')
    setRegSuccess('')

    if (!firstName.trim() || !fatherName.trim()) {
      setRegError('Please enter both First Name and Father Name.')
      return
    }

    const cleanPhone = phone.trim()
    if (!cleanPhone || cleanPhone.length < 9) {
      setRegError('Please enter a valid phone number (at least 9 digits).')
      return
    }

    const cleanFayda = faydaId.trim().replace(/\s+/g, '')
    if (!/^\d{16}$/.test(cleanFayda)) {
      setRegError('Fayda identification number must be exactly 16 numeric digits.')
      return
    }

    if (!assignedPassword || assignedPassword.length < 6) {
      setRegError('Assigned password must be at least 6 characters long.')
      return
    }

    setRegLoading(true)
    try {
      const response = await fetch('/api/auth/moderator/register-farmer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          firstName: firstName.trim(),
          fatherName: fatherName.trim(),
          phone: cleanPhone,
          faydaId: cleanFayda,
          password: assignedPassword,
          region,
        }),
      })

      const data = await response.json()
      if (!response.ok || !data.success) {
        throw new Error(data.message || 'Failed to register farmer.')
      }

      setRegSuccess(`Farmer ${data.user?.fullName} registered successfully! Assigned password: ${assignedPassword}`)
      setFirstName('')
      setFatherName('')
      setPhone('')
      setFaydaId('')
      setAssignedPassword('')
      fetchFarmers()
    } catch (err) {
      setRegError(err.message)
    } finally {
      setRegLoading(false)
    }
  }

  return (
    <section className="dashboard-page" style={{ maxWidth: '1120px', margin: '0 auto', paddingBottom: '3rem' }}>
      {/* Header */}
      <div className="dashboard-heading" style={{ alignItems: 'flex-start' }}>
        <div>
          <p className="eyebrow">
            <Shield size={16} style={{ display: 'inline', verticalAlign: 'text-bottom', marginRight: '4px' }} />
            MODERATOR OPERATIONS
          </p>
          <h1>
            {t.moderatorOverview} <UserCheck size={28} aria-hidden="true" />
          </h1>
          <p className="location-line" style={{ maxWidth: '700px' }}>
            {t.moderatorOverviewSub}
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button
            className="primary-button"
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
            onClick={() => handleSendSMS(null)}
            disabled={smsLoading}
          >
            <Send size={18} />
            {smsLoading ? 'Sending SMS...' : `Send SMS to All Farmers (${farmers.length})`}
          </button>
          <button
            className="primary-button"
            onClick={() => {
              setShowRegisterForm((prev) => !prev)
              setRegError('')
              setRegSuccess('')
            }}
          >
            <PlusCircle size={18} /> {showRegisterForm ? 'Close Form' : t.registerFarmer}
          </button>
          <button className="secondary-button" onClick={fetchSummary} disabled={loading}>
            <RefreshCw size={18} /> Refresh Readings
          </button>
          <button className="secondary-button" onClick={() => setPage('welcome')}>
            <ArrowLeft size={18} /> Home
          </button>
        </div>
      </div>

      {/* SMS Status Banners */}
      {smsResult && (
        <div
          className="notice-message"
          style={{
            color: '#15803d',
            borderColor: '#bbf7d0',
            marginBottom: '1.5rem',
            background: '#f0fdf4',
          }}
        >
          <CheckCircle2 size={18} style={{ display: 'inline', marginRight: '6px', verticalAlign: 'text-bottom' }} />
          <strong>SMS Sent Successfully!</strong> Dispatched crop health reports to {smsResult.sentCount ?? farmers.length} farmers with personalized greetings, core telemetry, and agronomic optimization recommendations.
        </div>
      )}

      {smsError && (
        <div
          className="notice-message"
          style={{
            color: '#b91c1c',
            borderColor: '#fecaca',
            marginBottom: '1.5rem',
            background: '#fef2f2',
          }}
        >
          <strong>SMS Dispatch Alert:</strong> {smsError}
        </div>
      )}

      {/* Register Farmer Form (Toggled by Moderator) */}
      {showRegisterForm && (
        <div
          className="form-card"
          style={{
            marginBottom: '2rem',
            border: '2px solid var(--green)',
            boxShadow: '0 8px 30px rgba(184, 255, 26, 0.12)',
          }}
        >
          <div style={{ marginBottom: '1.25rem' }}>
            <h2 style={{ margin: '0 0 0.5rem 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Sprout size={24} style={{ color: 'var(--green)' }} />
              {t.registerFarmer} (Assigned Password Flow)
            </h2>
            <p style={{ margin: 0, color: 'var(--muted)', fontSize: '0.95rem' }}>
              Moderators can enroll local farmers directly into the system by provisioning their credentials.
            </p>
          </div>

          <form onSubmit={handleRegisterFarmer}>
            <div className="form-grid">
              <label className="field">
                <span>{t.firstName}</span>
                <input
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  placeholder="e.g. Almaz"
                  required
                />
              </label>

              <label className="field">
                <span>{t.fatherName}</span>
                <input
                  value={fatherName}
                  onChange={(e) => setFatherName(e.target.value)}
                  placeholder="e.g. Ayana"
                  required
                />
              </label>

              <label className="field">
                <span>{t.phoneNumber}</span>
                <input
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="09..."
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
                  placeholder="16-digit national ID"
                  maxLength={16}
                  required
                />
              </label>

              <label className="field">
                <span>{t.region}</span>
                <select value={region} onChange={(e) => setRegion(e.target.value)}>
                  <option value="Arsi">Arsi (Wheat)</option>
                  <option value="Bale">Bale (Wheat)</option>
                  <option value="Jimma">Jimma (Coffee)</option>
                </select>
              </label>

              <label className="field">
                <span>{t.assignedPassword}</span>
                <input
                  value={assignedPassword}
                  onChange={(e) => setAssignedPassword(e.target.value)}
                  placeholder="Assign initial password"
                  required
                />
              </label>
            </div>

            {regError && (
              <p className="notice-message" style={{ color: '#ff6b6b', borderColor: '#ff6b6b', marginTop: '1rem' }}>
                {regError}
              </p>
            )}

            {regSuccess && (
              <p className="notice-message" style={{ color: 'var(--green)', borderColor: 'var(--green)', marginTop: '1rem' }}>
                <CheckCircle2 size={16} style={{ display: 'inline', marginRight: '6px' }} />
                {regSuccess}
              </p>
            )}

            <div style={{ marginTop: '1.25rem', display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
              <button type="button" className="secondary-button" onClick={() => setShowRegisterForm(false)}>
                Cancel
              </button>
              <button type="submit" className="primary-button" disabled={regLoading}>
                {regLoading ? 'Registering...' : 'Complete Farmer Enrollment'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* 3 Regional Cards: Arsi, Bale, Jimma */}
      <h2 style={{ fontSize: '1.4rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <CloudRain size={22} style={{ color: 'var(--green)' }} />
        Regional Telemetry Cards (Arsi · Bale · Jimma)
      </h2>

      {loading && !regions.length ? (
        <p style={{ color: 'var(--muted)' }}>Loading regional telemetry...</p>
      ) : error ? (
        <p style={{ color: '#ff6b6b' }}>{error}</p>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem', marginBottom: '2.5rem' }}>
          {regions.map((r) => {
            const statusTone = r.status === 'Critical' ? 'critical' : r.status === 'Warning' ? 'warning' : 'healthy'
            return (
              <div
                key={r.region}
                className="crop-summary-card"
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  borderRadius: 'var(--radius-md)',
                  padding: '1.5rem',
                  background: 'var(--card)',
                  border: '1px solid var(--line)',
                }}
              >
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                    <span className="section-kicker" style={{ margin: 0 }}>{r.zone}</span>
                    <div className={`status-pill ${statusTone}`} style={{ margin: 0 }}>
                      <span className="status-dot"></span>
                      {r.status}
                    </div>
                  </div>

                  <h3 style={{ margin: '0 0 0.25rem 0', fontSize: '1.6rem' }}>{r.region}</h3>
                  <p style={{ color: 'var(--muted)', fontSize: '0.9rem', marginBottom: '1rem' }}>
                    Primary Crop: <strong style={{ color: 'var(--ink)' }}>{r.primaryCrop}</strong> · Score: {r.healthScore}/100
                  </p>

                  {/* Metrics grid */}
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '1fr 1fr',
                      gap: '0.75rem',
                      background: 'var(--page)',
                      padding: '1rem',
                      borderRadius: 'var(--radius-sm)',
                      marginBottom: '1rem',
                    }}
                  >
                    <div>
                      <small style={{ color: 'var(--muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <Droplets size={14} /> Soil Moisture
                      </small>
                      <strong style={{ fontSize: '1.1rem' }}>{r.metrics.soilMoisture}%</strong>
                    </div>

                    <div>
                      <small style={{ color: 'var(--muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <Thermometer size={14} /> Temperature
                      </small>
                      <strong style={{ fontSize: '1.1rem' }}>{r.metrics.temperature}°C</strong>
                    </div>

                    <div>
                      <small style={{ color: 'var(--muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <CloudRain size={14} /> Humidity
                      </small>
                      <strong style={{ fontSize: '1.1rem' }}>{r.metrics.humidity}%</strong>
                    </div>

                    <div>
                      <small style={{ color: 'var(--muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <Wind size={14} /> Rainfall
                      </small>
                      <strong style={{ fontSize: '1.1rem' }}>{r.metrics.rainfall} mm</strong>
                    </div>
                  </div>
                </div>

                <div
                  style={{
                    padding: '0.75rem 1rem',
                    borderRadius: 'var(--radius-sm)',
                    background: 'var(--card-muted)',
                    fontSize: '0.85rem',
                    borderLeft: `3px solid ${statusTone === 'critical' ? '#dc2626' : statusTone === 'warning' ? '#d97706' : '#16a34a'}`,
                  }}
                >
                  <strong style={{ display: 'block', marginBottom: '0.25rem' }}>Agronomic Recommendation:</strong>
                  <span style={{ color: 'var(--ink)' }}>{r.recommendation}</span>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* SMS Broadcast Action Card */}
      <div
        className="crop-summary-card"
        style={{
          marginBottom: '2rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '1rem',
          background: '#ffffff',
          border: '1px solid var(--line)',
          padding: '1.25rem 1.5rem',
        }}
      >
        <div>
          <h2 style={{ fontSize: '1.25rem', margin: '0 0 0.35rem 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <MessageSquare size={22} style={{ color: '#111111' }} />
            Crop Health SMS Service
          </h2>
          <p style={{ margin: 0, color: 'var(--muted)', fontSize: '0.9rem' }}>
            Broadcasts instant crop health updates to all {farmers.length} enrolled farmers via AfroMessage with personalized greetings, core telemetry data (Soil, Temp, Humidity, Rain), and optimization recommendations:
            <br />
            <em style={{ color: 'var(--ink)', fontSize: '0.85rem' }}>
              &quot;Greetings [Name], [Crop] Crop Health Report: Status | Core Data (Soil, Temp, Humidity, Rain) | Optimization: [Advice] | የእርሻ ምክር: [Amharic]&quot;
            </em>
          </p>
        </div>
        <button
          className="primary-button"
          style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
          onClick={() => handleSendSMS(null)}
          disabled={smsLoading || farmers.length === 0}
        >
          <Send size={18} />
          {smsLoading ? 'Sending SMS Broadcast...' : `Send SMS to All Farmers (${farmers.length})`}
        </button>
      </div>

      {/* Enrolled Farmers Table / List */}
      <div>
        <h2 style={{ fontSize: '1.3rem', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Users size={20} style={{ color: 'var(--green)' }} />
          Enrolled Farmers ({farmers.length})
        </h2>

        {farmers.length === 0 ? (
          <div className="message-card">
            <p>{t.noFarmersYet}</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table
              style={{
                width: '100%',
                borderCollapse: 'collapse',
                textAlign: 'left',
                background: 'var(--card)',
                borderRadius: 'var(--radius-sm)',
                overflow: 'hidden',
              }}
            >
              <thead>
                <tr style={{ background: 'var(--card-muted)', borderBottom: '1px solid var(--line)' }}>
                  <th style={{ padding: '0.75rem 1rem' }}>Farmer Name</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Phone</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Fayda ID</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Region</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Enrolled By</th>
                </tr>
              </thead>
              <tbody>
                {farmers.map((f) => (
                  <tr key={f.userId} style={{ borderBottom: '1px solid var(--line)' }}>
                    <td style={{ padding: '0.75rem 1rem', fontWeight: 600 }}>{f.fullName}</td>
                    <td style={{ padding: '0.75rem 1rem' }}>{f.phone}</td>
                    <td style={{ padding: '0.75rem 1rem', fontFamily: 'monospace' }}>{f.faydaId}</td>
                    <td style={{ padding: '0.75rem 1rem' }}>{f.region}</td>
                    <td style={{ padding: '0.75rem 1rem' }}>
                      <span
                        style={{
                          fontSize: '0.75rem',
                          padding: '3px 8px',
                          borderRadius: '12px',
                          background: f.registeredBy === 'moderator' ? 'rgba(184, 255, 26, 0.15)' : 'rgba(255, 255, 255, 0.1)',
                          color: f.registeredBy === 'moderator' ? 'var(--green)' : 'var(--khaki)',
                        }}
                      >
                        {f.registeredBy}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  )
}

export default ModeratorPage

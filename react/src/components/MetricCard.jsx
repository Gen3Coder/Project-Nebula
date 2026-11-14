function MetricCard({ metric, interpretation, sampleReadingLabel }) {
  const rawValue = metric.value ?? '—'

  return (
    <article className="metric-card">
      <span className="metric-icon">{metric.icon}</span>
      <p className="metric-label">{metric.label}</p>
      <p className="metric-value">{interpretation.label}</p>
      <div
        className="metric-progress"
        role="progressbar"
        aria-label={`${metric.label}: ${interpretation.label}`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={interpretation.progress}
      >
        <span style={{ width: `${interpretation.progress}%` }} />
      </div>
      <p className="metric-raw">
        {sampleReadingLabel}: {rawValue}
      </p>
    </article>
  )
}

export default MetricCard

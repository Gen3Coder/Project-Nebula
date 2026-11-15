import { CloudRain } from 'lucide-react'

const chartWidth = 760
const chartHeight = 180
const chartLeft = 8
const chartRight = 752
const baseline = 158
const plotHeight = 132

function RainChart({ values = [], labels }) {
  const safeValues = Array.isArray(values) && values.length > 0 ? values : [0, 0, 0, 0, 0, 0, 0]
  const count = safeValues.length
  const step = (chartRight - chartLeft) / count
  const barWidth = Math.min(28, Math.max(10, step * 0.55))

  const maxRain = Math.max(...safeValues)
  const scaleMaximum = Math.max(7, Math.ceil(maxRain / 5) * 5)
  const guideValues = [
    0,
    Math.round(scaleMaximum * 0.33),
    Math.round(scaleMaximum * 0.66),
    scaleMaximum,
  ]

  const highestIndex = safeValues.indexOf(maxRain)
  const thresholdValue = labels.threshold ?? 2
  const thresholdY = baseline - (thresholdValue / scaleMaximum) * plotHeight

  return (
    <section className="rain-chart-card" aria-labelledby="rain-chart-title">
      <div className="rain-chart-heading">
        <div className="icon-tile" aria-hidden="true">
          <CloudRain size={24} />
        </div>
        <div>
          <h2 id="rain-chart-title">{labels.title}</h2>
          {labels.sample && <p className="rain-chart-sample">{labels.sample}</p>}
        </div>
      </div>
      <p className="rain-chart-unit">{labels.unit}</p>
      <svg
        className="rain-chart"
        viewBox={`0 0 ${chartWidth} ${chartHeight}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={`${labels.title}. ${labels.unit}. ${labels.daysAgoAxis}. ${safeValues.map((value, index) => `${count - index} ${count - index === 1 ? labels.dayAgo : labels.daysAgo}: ${value} mm`).join('; ')}. ${labels.caption}`}
      >
        {guideValues.map((value) => {
          const y = baseline - (value / scaleMaximum) * plotHeight
          return (
            <line
              className="rain-chart-gridline"
              key={value}
              x1={chartLeft}
              y1={y}
              x2={chartRight}
              y2={y}
            />
          )
        })}
        <line
          className="rain-chart-threshold"
          x1={chartLeft}
          y1={thresholdY}
          x2={chartRight}
          y2={thresholdY}
        />
        {safeValues.map((value, index) => {
          const day = count - index
          const dayLabel = day === 1 ? labels.dayAgo : labels.daysAgo
          const x = chartLeft + index * step + (step - barWidth) / 2
          const height = Math.max(4, (value / scaleMaximum) * plotHeight)

          return (
            <g key={day}>
              <rect
                className={index === highestIndex && value > 0 ? 'rain-bar highest' : 'rain-bar'}
                x={x}
                y={baseline - height}
                width={barWidth}
                height={height}
                rx="6"
                style={{ '--index': index }}
              >
                <title>{`${day} ${dayLabel}: ${value} mm`}</title>
              </rect>
            </g>
          )
        })}
      </svg>
      <div className="rain-chart-days" aria-hidden="true">
        {safeValues.map((_, index) => (
          <span key={index}>{count - index}</span>
        ))}
      </div>
      <p className="rain-chart-days-label">{labels.daysAgoAxis}</p>
      <div className="rain-chart-legend">
        <span>
          <i className="rain-legend-bar" aria-hidden="true" />
          {labels.highestDay}
        </span>
        <span>
          <i className="rain-legend-threshold" aria-hidden="true" />
          {labels.reference} ({thresholdValue} mm)
        </span>
      </div>
      <p className="rain-chart-caption">{labels.caption}</p>
    </section>
  )
}

export default RainChart

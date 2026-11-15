import {
  Clock3,
  CloudRain,
  Coffee,
  Info,
  MapPin,
  RefreshCw,
  Sprout,
  Wheat,
} from 'lucide-react'
import PlantOrWait from '../components/PlantOrWait'
import RainChart from '../components/RainChart'
import MetricCard from '../components/MetricCard'

function DashboardPage({
  t,
  currentUser,
  locationSummary,
  setPage,
  selectedCrops,
  activeCrop,
  setActiveCrop,
  riskPreference,
  setRiskPreference,
  sampleDecision,
  decisionReason,
  riskOptions,
  sampleRainfall,
  sampleRainfallReference,
  crop,
  loading,
  error,
  setRefreshKey,
  rawStatus,
  statusLabel,
  statusTone,
  metrics,
  getMetricInterpretation,
  dateLocale,
}) {
  const farmerGreeting = currentUser?.firstName
    ? `${t.helloFarmer.replace(/!$/, '')} ${currentUser.firstName}!`
    : t.helloFarmer

  return (
    <section className="dashboard-page">
      <div className="dashboard-heading">
        <div>
          <p className="eyebrow">{t.dashboardEyebrow}</p>
          <h1>
            {farmerGreeting} <Sprout size={28} aria-hidden="true" />
          </h1>
          <p className="location-line">
            <MapPin size={18} aria-hidden="true" /> {locationSummary}
          </p>
        </div>
        <button className="secondary-button" onClick={() => setPage('location')}>
          {t.editLocation}
        </button>
      </div>

      <div className="crop-tabs" aria-label={t.myCrops}>
        {selectedCrops.map((name) => (
          <button
            key={name}
            className={activeCrop === name ? 'crop-tab active' : 'crop-tab'}
            onClick={() => setActiveCrop(name)}
          >
            {name === 'Wheat' ? (
              <Wheat size={18} aria-hidden="true" />
            ) : (
              <Coffee size={18} aria-hidden="true" />
            )}
            {name === 'Wheat' ? t.wheat : t.coffee}
          </button>
        ))}
      </div>

      <section className="decision-controls" aria-labelledby="outlook-title">
        <div className="outlook-summary">
          <div>
            <h2 id="outlook-title">{t.outlookHeading}</h2>
            <p className="outlook-risk">
              <span>{t.drySpellRisk}</span>
              <strong>{t.riskMedium}</strong>
            </p>
            <p className="outlook-note">{t.outlookDemoNote}</p>
          </div>
          <span className="icon-tile" aria-hidden="true">
            <CloudRain size={24} />
          </span>
        </div>
        <div className="risk-control">
          <h3>{t.riskSelectorHeading}</h3>
          <div className="risk-options" role="group" aria-label={t.riskSelectorHeading}>
            {riskOptions.map((option) => (
              <button
                className={riskPreference === option.value ? 'risk-option selected' : 'risk-option'}
                key={option.value}
                type="button"
                aria-pressed={riskPreference === option.value}
                onClick={() => setRiskPreference(option.value)}
              >
                <span className="risk-option-label">{option.label}</span>
                <span className="risk-option-description">{option.description}</span>
              </button>
            ))}
          </div>
          <p className="risk-selection-note">{t.riskSelectionNote}</p>
        </div>
      </section>

      {/* TODO: Replace the sample risk and decision with forecast-backed data. */}
      <PlantOrWait
        decision={sampleDecision}
        labels={{
          question: t.verdictQuestion,
          plant: t.plantNow,
          wait: t.wait,
          reason: decisionReason,
          sample: t.sampleData,
        }}
      />
      <RainChart
        values={sampleRainfall}
        labels={{
          title: t.rainHistory,
          caption: t.rainChartCaption,
          unit: t.rainUnit,
          daysAgoAxis: t.chartDaysAgo,
          reference: t.chartReference,
          highestDay: t.highestRainfallDay,
          threshold: sampleRainfallReference,
          dayAgo: t.dayAgo,
          daysAgo: t.daysAgo,
          sample: t.sampleData,
        }}
      />

      {activeCrop === 'Wheat' && (
        <>
          <div className="crop-summary-card">
            <div>
              <p className="section-kicker">{t.monitoring}</p>
              <h2>{t.wheat}</h2>
              <p>{t.readingsIntro}</p>
            </div>
            <div className={`status-pill ${statusTone}`}>
              <span className="status-dot"></span>
              {crop ? statusLabel : t.checkingStatus}
            </div>
          </div>

          {loading && !crop && (
            <div className="message-card">
              <span className="icon-tile">
                <Sprout size={28} aria-hidden="true" />
              </span>
              <h3>{t.loadingTitle}</h3>
              <p>{t.loadingText}</p>
            </div>
          )}

          {error && !crop && (
            <div className="message-card">
              <span className="icon-tile">
                <Info size={28} aria-hidden="true" />
              </span>
              <h3>{t.loadErrorTitle}</h3>
              <p>{t.loadErrorText}</p>
              <button
                className="primary-button"
                onClick={() => setRefreshKey((value) => value + 1)}
              >
                {t.tryAgain}
              </button>
            </div>
          )}

          {crop && (
            <>
              {rawStatus.includes('critical') && (
                <div className="attention-banner">
                  <span className="banner-icon">
                    <Info size={20} aria-hidden="true" />
                  </span>
                  <div>
                    <strong>{t.criticalTitle}</strong>
                    <p>{t.criticalText}</p>
                  </div>
                </div>
              )}

              {crop.recommendation && (
                <div className="guidance-card" style={{ marginBottom: '1rem' }}>
                  <span className="guidance-icon">
                    <Sprout size={22} aria-hidden="true" />
                  </span>
                  <div>
                    <h3>{t.recommendation || 'Recommendation'}</h3>
                    <p>{crop.recommendation}</p>
                  </div>
                </div>
              )}

              <div className="section-heading">
                <div>
                  <h2>{t.wheatReadings}</h2>
                  <p>{t.readingsText}</p>
                </div>
                <button
                  className="secondary-button"
                  onClick={() => setRefreshKey((value) => value + 1)}
                  disabled={loading}
                >
                  {loading ? (
                    t.refreshing
                  ) : (
                    <>
                      <RefreshCw size={18} aria-hidden="true" /> {t.refresh}
                    </>
                  )}
                </button>
              </div>

              <div className="metrics-grid">
                {metrics.map((metric) => (
                  <MetricCard
                    key={metric.label}
                    metric={metric}
                    interpretation={getMetricInterpretation(metric)}
                    sampleReadingLabel={t.sampleReading}
                  />
                ))}
              </div>

              <div className="data-footer">
                <span>
                  <Clock3 size={18} aria-hidden="true" />
                </span>
                <p>
                  {t.lastUpdated}{' '}
                  {crop.lastUpdated && !Number.isNaN(Date.parse(crop.lastUpdated))
                    ? new Date(crop.lastUpdated).toLocaleString(dateLocale)
                    : '—'}
                </p>
              </div>
              <p className="small-note">{t.sampleNote}</p>
            </>
          )}
        </>
      )}

      {activeCrop === 'Coffee' && (
        <div className="message-card coffee-message">
          <span className="icon-tile">
            <Coffee size={28} aria-hidden="true" />
          </span>
          <p className="eyebrow">{t.coffeeEyebrow}</p>
          <h2>{t.coffeeTitle}</h2>
          <p>{t.coffeeText}</p>
          <button className="secondary-button" onClick={() => setPage('guidance')}>
            {t.seeNext}
          </button>
        </div>
      )}
    </section>
  )
}

export default DashboardPage

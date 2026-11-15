import { CloudRain, Info, Search, Sprout } from 'lucide-react'

function GuidancePage({ t, activeCrop, crop, setPage }) {
  return (
    <section className="guidance-page">
      <div className="setup-heading">
        <p className="eyebrow">{t.guidanceEyebrow}</p>
        <h1>{t.guidanceTitle}</h1>
        <p>{t.guidanceIntro}</p>
      </div>

      {activeCrop === 'Wheat' && crop ? (
        <div className="guidance-card">
          <span className="guidance-icon">
            <Search size={22} aria-hidden="true" />
          </span>
          <div>
            <h2>{t.checkWheat}</h2>
            <p>
              {t.wheatGuidance} "{crop.status}".
            </p>
            {crop.recommendation && (
              <p style={{ fontWeight: 600, marginTop: '0.5rem' }}>
                {crop.recommendation}
              </p>
            )}
            <p>{t.wheatGuidance2}</p>
            <p>{t.wheatGuidance3}</p>
          </div>
        </div>
      ) : (
        <div className="guidance-card">
          <span className="guidance-icon">
            <Sprout size={22} aria-hidden="true" />
          </span>
          <div>
            <h2>{t.guidanceNotReady}</h2>
            <p>{t.guidanceNotReadyText}</p>
          </div>
        </div>
      )}

      <h2 className="guidance-section-title">{t.howNebulaHelps}</h2>

      <div className="guidance-list">
        <article>
          <span>
            <Info size={22} aria-hidden="true" />
          </span>
          <div>
            <h3>{t.understandNumbers}</h3>
            <p>{t.understandNumbersText}</p>
          </div>
        </article>
        <article>
          <span>
            <CloudRain size={22} aria-hidden="true" />
          </span>
          <div>
            <h3>{t.localConditions}</h3>
            <p>{t.localConditionsText}</p>
          </div>
        </article>
        <article>
          <span>
            <Sprout size={22} aria-hidden="true" />
          </span>
          <div>
            <h3>{t.askForHelp}</h3>
            <p>{t.askForHelpText}</p>
          </div>
        </article>
      </div>

      <button className="primary-button" onClick={() => setPage('dashboard')}>
        {t.backToCrops}
      </button>
    </section>
  )
}

export default GuidancePage

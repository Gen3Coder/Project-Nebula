import { ArrowRight } from 'lucide-react'
import plantingImage from '../assets/planting.jpg'

function WelcomePage({ setPage, t }) {
  return (
    <section className="welcome-page">
      <div
        className="welcome-hero"
        style={{
          backgroundImage: `linear-gradient(180deg, rgb(11 11 12 / 0%) 16%, rgb(11 11 12 / 24%) 46%, rgb(11 11 12 / 88%) 100%), url("${plantingImage}")`,
        }}
      >
        <div className="welcome-copy">
          <p className="eyebrow">{t.welcomeEyebrow}</p>
          <h1>
            {t.welcomeTitle1}
            <br />
            <span>{t.welcomeTitle2}</span>
          </h1>
          <p className="lead">{t.welcomeText}</p>
          <button
            className="primary-button large-button"
            onClick={() => setPage('location')}
          >
            {t.setupFarm}
            <ArrowRight size={20} aria-hidden="true" />
          </button>
        </div>
      </div>
      <p className="hero-photo-credit">{t.photoCredit}</p>

      <section className="welcome-process" aria-labelledby="welcome-process-title">
        <div className="welcome-process-heading">
          <h2 id="welcome-process-title">{t.howItWorks}</h2>
        </div>
        <div className="welcome-benefits">
          <article>
            <span className="process-step" aria-hidden="true">1</span>
            <h3>{t.addLocation}</h3>
            <p>{t.addLocationText}</p>
          </article>
          <span className="process-connector" aria-hidden="true">
            <ArrowRight size={28} />
          </span>
          <article>
            <span className="process-step" aria-hidden="true">2</span>
            <h3>{t.understandReadings}</h3>
            <p>{t.understandReadingsText}</p>
          </article>
        </div>
      </section>
    </section>
  )
}

export default WelcomePage

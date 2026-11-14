import { Info, Languages, Wheat } from 'lucide-react'

function Header({ page, setPage, language, toggleLanguage, t }) {
  return (
    <header className="topbar">
      <button
        className="brand"
        onClick={() => setPage('welcome')}
        aria-label="Nebula home"
      >
        <span className="brand-mark">N</span>
        <span>
          <strong className="brand-name">NEBULA</strong>
          <span className="brand-subtitle">{t.farmCompanion}</span>
        </span>
      </button>

      <div className="topbar-right">
        {(page === 'dashboard' || page === 'guidance') && (
          <nav className="main-nav" aria-label="Main navigation">
            <button
              className={page === 'dashboard' ? 'nav-link active' : 'nav-link'}
              onClick={() => setPage('dashboard')}
            >
              <Wheat className="nav-icon" size={19} aria-hidden="true" />
              {t.myCrops}
            </button>
            <button
              className={page === 'guidance' ? 'nav-link active' : 'nav-link'}
              onClick={() => setPage('guidance')}
            >
              <Info className="nav-icon" size={19} aria-hidden="true" />
              {t.help}
            </button>
          </nav>
        )}

        <button
          className="language-button"
          onClick={toggleLanguage}
          aria-label={language === 'en' ? 'Switch to Amharic' : 'ወደ እንግሊዝኛ ቀይር'}
        >
          <Languages className="language-icon" size={19} aria-hidden="true" />
          {t.switchLanguage}
        </button>
      </div>
    </header>
  )
}

export default Header

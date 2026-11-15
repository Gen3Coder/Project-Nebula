import { Info, Languages, LogIn, LogOut, Shield, User, Wheat } from 'lucide-react'

function Header({ page, setPage, language, toggleLanguage, t, currentUser, onLogout }) {
  return (
    <header className="topbar">
      <button
        className="brand"
        onClick={() => setPage(currentUser?.role === 'moderator' ? 'moderator' : 'welcome')}
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

        {currentUser?.role === 'moderator' && (
          <button
            className={page === 'moderator' ? 'nav-link active' : 'nav-link'}
            onClick={() => setPage('moderator')}
            style={{ fontWeight: 700, color: 'var(--green)' }}
          >
            <Shield className="nav-icon" size={19} aria-hidden="true" />
            {t.moderatorPanel}
          </button>
        )}

        <button
          className="language-button"
          onClick={toggleLanguage}
          aria-label={language === 'en' ? 'Switch to Amharic' : 'ወደ እንግሊዝኛ ቀይር'}
        >
          <Languages className="language-icon" size={19} aria-hidden="true" />
          {t.switchLanguage}
        </button>

        {currentUser ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span
              style={{
                fontSize: '0.85rem',
                color: 'var(--muted)',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              <User size={15} /> {currentUser.firstName}
              <small style={{ color: 'var(--green)', fontWeight: 600 }}>({currentUser.role})</small>
            </span>
            <button
              className="text-button"
              onClick={onLogout}
              style={{ fontSize: '0.85rem', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
              title={t.logout}
            >
              <LogOut size={16} /> {t.logout}
            </button>
          </div>
        ) : (
          <button
            className="secondary-button"
            onClick={() => setPage('auth')}
            style={{ padding: '8px 14px', fontSize: '0.88rem' }}
          >
            <LogIn size={16} /> {t.login}
          </button>
        )}
      </div>
    </header>
  )
}

export default Header

import { ArrowRight, MapPin } from 'lucide-react'

function LocationPage({
  farmLocation,
  updateLocation,
  useCurrentLocation,
  continueFromLocation,
  coordinates,
  locationMessage,
  setPage,
  t,
}) {
  return (
    <section className="setup-page">
      <div className="setup-heading">
        <p className="eyebrow">{t.locationEyebrow}</p>
        <h1>{t.locationTitle}</h1>
        <p>{t.locationText}</p>
      </div>

      <div className="step-track">
        <span className="step done">1</span>
        <span className="step-line"></span>
        <span className="step">2</span>
      </div>

      <form className="form-card" onSubmit={continueFromLocation}>
        <div className="form-grid">
          <label className="field">
            <span>{t.region}</span>
            <input
              list="ethiopian-regions"
              value={farmLocation.region}
              onChange={(event) => updateLocation('region', event.target.value)}
              placeholder={t.regionHint || 'e.g. Jimma, Arsi, Bale'}
            />
            <datalist id="ethiopian-regions">
              <option value="Jimma">Jimma (Coffee)</option>
              <option value="Arsi">Arsi (Wheat)</option>
              <option value="Bale">Bale (Wheat)</option>
            </datalist>
          </label>
          <label className="field">
            <span>{t.cropType}</span>
            <select
              value={farmLocation.cropType}
              onChange={(event) => updateLocation('cropType', event.target.value)}
            >
              <option value="Wheat">{t.wheat}</option>
              <option value="Coffee">{t.coffee}</option>
              <option value="Teff" disabled>{t.teff} ({t.comingSoon})</option>
            </select>
          </label>
          <label className="field">
            <span>{t.latitude}</span>
            <input
              value={farmLocation.latitude}
              onChange={(event) => updateLocation('latitude', event.target.value)}
              placeholder={t.latitudeHint}
            />
          </label>
          <label className="field">
            <span>{t.longitude}</span>
            <input
              value={farmLocation.longitude}
              onChange={(event) => updateLocation('longitude', event.target.value)}
              placeholder={t.longitudeHint}
            />
          </label>
        </div>

        <div className="location-option">
          <div className="location-option-icon">
            <MapPin size={24} aria-hidden="true" />
          </div>
          <div className="location-option-copy">
            <strong>{t.atFarm}</strong>
            <p>{t.atFarmText}</p>
            {coordinates && (
              <p className="location-success">{t.locationSavedCoordinates}</p>
            )}
          </div>
          <button
            type="button"
            className="secondary-button"
            onClick={useCurrentLocation}
          >
            {t.useLocation}
          </button>
        </div>

        {locationMessage && (
          <p className="notice-message" role="status">
            {t[locationMessage]}
          </p>
        )}

        <p className="privacy-note">{t.locationPrivacy}</p>

        <div className="form-actions">
          <button
            type="button"
            className="text-button"
            onClick={() => setPage('welcome')}
          >
            {t.back}
          </button>
          <button className="primary-button" type="submit">
            {t.continueCrops} <ArrowRight size={20} aria-hidden="true" />
          </button>
        </div>
      </form>
    </section>
  )
}

export default LocationPage

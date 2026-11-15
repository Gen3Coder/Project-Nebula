import { useEffect, useState } from 'react'
import { CloudRain, Droplets, Thermometer, Wind } from 'lucide-react'
import './App.css'
import Header from './components/Header'
import Footer from './components/Footer'
import WelcomePage from './pages/WelcomePage'
import LocationPage from './pages/LocationPage'
import DashboardPage from './pages/DashboardPage'
import GuidancePage from './pages/GuidancePage'
import AuthPage from './pages/AuthPage'
import ModeratorPage from './pages/ModeratorPage'
import translations from './locales'
import {
  buildCropHealthURL,
  sampleDrySpellRisk,
  sampleRainfallReference,
} from './constants/farmConfig'

function App() {
  const [language, setLanguage] = useState(() => {
    return localStorage.getItem('nebula-language') || 'en'
  })

  function toggleLanguage() {
    const nextLanguage = language === 'en' ? 'am' : 'en'
    localStorage.setItem('nebula-language', nextLanguage)
    setLanguage(nextLanguage)
  }

  const t = translations[language]

  const [page, setPage] = useState('welcome')
  const [riskPreference, setRiskPreference] = useState('balanced')

  // Logged-in user state (Farmer or Moderator)
  const [currentUser, setCurrentUser] = useState(() => {
    try {
      const saved = localStorage.getItem('nebula-user')
      return saved ? JSON.parse(saved) : null
    } catch {
      return null
    }
  })

  function getRegionDefaultCrop(region) {
    if (!region) return 'Wheat'
    const clean = String(region).trim().toLowerCase()
    return clean === 'jimma' ? 'Coffee' : 'Wheat'
  }

  const initialRegion = currentUser?.region || ''
  const initialCrop = getRegionDefaultCrop(initialRegion)

  const [farmLocation, setFarmLocation] = useState(() => ({
    region: initialRegion,
    cropType: initialCrop,
    latitude: '',
    longitude: '',
  }))

  const [coordinates, setCoordinates] = useState('')
  const [locationMessage, setLocationMessage] = useState('')
  const [selectedCrops, setSelectedCrops] = useState([initialCrop])
  const [activeCrop, setActiveCrop] = useState(initialCrop)
  const [crop, setCrop] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)

  // Sync crop whenever currentUser changes or loads from localStorage
  useEffect(() => {
    if (currentUser?.region) {
      const userCrop = getRegionDefaultCrop(currentUser.region)
      setFarmLocation((prev) => ({
        ...prev,
        region: currentUser.region,
        cropType: userCrop,
      }))
      setSelectedCrops([userCrop])
      setActiveCrop(userCrop)
    }
  }, [currentUser?.region])

  function handleAuthSuccess(user, token) {
    setCurrentUser(user)
    localStorage.setItem('nebula-user', JSON.stringify(user))
    if (token) localStorage.setItem('nebula-token', token)
    if (user?.region) {
      const userCrop = getRegionDefaultCrop(user.region)
      setFarmLocation((prev) => ({
        ...prev,
        region: user.region,
        cropType: userCrop,
      }))
      setSelectedCrops([userCrop])
      setActiveCrop(userCrop)
    }
  }

  function handleLogout() {
    setCurrentUser(null)
    localStorage.removeItem('nebula-user')
    localStorage.removeItem('nebula-token')
    setFarmLocation({
      region: '',
      cropType: 'Wheat',
      latitude: '',
      longitude: '',
    })
    setSelectedCrops(['Wheat'])
    setActiveCrop('Wheat')
    setPage('welcome')
  }

  useEffect(() => {
    if (page === 'location' && !farmLocation.latitude && !farmLocation.longitude) {
      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          (position) => {
            const latitude = position.coords.latitude.toFixed(4)
            const longitude = position.coords.longitude.toFixed(4)
            setCoordinates(`${latitude}, ${longitude}`)
            setFarmLocation((previous) => ({
              ...previous,
              latitude: String(latitude),
              longitude: String(longitude),
            }))
            setLocationMessage('coordinatesCaptured')
          },
          () => {},
          { enableHighAccuracy: false, timeout: 8000 }
        )
      }
    }
  }, [page, farmLocation.latitude, farmLocation.longitude])

  useEffect(() => {
    if (page !== 'dashboard') return

    let cancelled = false

    async function loadCrop() {
      setLoading(true)
      setError(false)

      try {
        const regionToQuery = farmLocation.region || currentUser?.region || 'Arsi'
        const cropToQuery = activeCrop || farmLocation.cropType || getRegionDefaultCrop(regionToQuery)
        const url = buildCropHealthURL(
          regionToQuery,
          cropToQuery
        )
        const response = await fetch(url)

        if (!response.ok) {
          throw new Error('Request failed')
        }

        const result = await response.json()

        if (!result.success || !result.data) {
          throw new Error('No crop data')
        }

        if (!cancelled) setCrop(result.data)
      } catch {
        if (!cancelled) setError(true)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    loadCrop()

    return () => {
      cancelled = true
    }
  }, [page, activeCrop, refreshKey, farmLocation.region, farmLocation.cropType, currentUser?.region])

  function updateLocation(field, value) {
    setFarmLocation((previous) => {
      const next = {
        ...previous,
        [field]: value,
      }
      if (field === 'region') {
        const regionalCrop = getRegionDefaultCrop(value)
        next.cropType = regionalCrop
        setSelectedCrops([regionalCrop])
        setActiveCrop(regionalCrop)
      } else if (field === 'cropType') {
        setSelectedCrops([value])
        setActiveCrop(value)
      }
      return next
    })
  }

  function useCurrentLocation() {
    setLocationMessage('')

    if (!navigator.geolocation) {
      setLocationMessage('locationUnavailable')
      return
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const latitude = position.coords.latitude.toFixed(4)
        const longitude = position.coords.longitude.toFixed(4)
        setCoordinates(`${latitude}, ${longitude}`)
        setFarmLocation((previous) => ({
          ...previous,
          latitude: String(latitude),
          longitude: String(longitude),
        }))
        setLocationMessage('coordinatesCaptured')
      },
      () => setLocationMessage('locationDenied'),
      { enableHighAccuracy: false, timeout: 10000 }
    )
  }

  function continueFromLocation(event) {
    event.preventDefault()

    const hasCoords =
      farmLocation.latitude.trim() && farmLocation.longitude.trim()
    const hasManualLocation = farmLocation.region.trim() && hasCoords

    if (!hasManualLocation && !coordinates) {
      setLocationMessage('locationRequired')
      return
    }

    setSelectedCrops([farmLocation.cropType])
    setActiveCrop(farmLocation.cropType)
    setCrop(null)
    setPage('dashboard')
  }

  const locationCoords =
    farmLocation.latitude && farmLocation.longitude
      ? `${farmLocation.latitude}, ${farmLocation.longitude}`
      : coordinates

  const locationParts = [
    farmLocation.region || currentUser?.region,
    locationCoords,
  ].filter((part) => part && part.trim())

  const locationSummary =
    locationParts.join(' · ') ||
    (locationCoords ? t.deviceLocationRecorded : t.noLocation)

  const rawStatus = String(crop?.status || '').toLowerCase()
  const statusLabel = rawStatus.includes('critical')
    ? t.needsAttention
    : rawStatus.includes('warning')
      ? t.checkConditions
      : rawStatus.includes('healthy')
        ? t.reportedHealthy
        : t.statusUnknown

  const statusTone = rawStatus.includes('critical')
    ? 'critical'
    : rawStatus.includes('warning')
      ? 'warning'
      : rawStatus.includes('healthy')
        ? 'healthy'
        : 'unknown'

  const metrics = crop
    ? [
        { label: t.soilMoisture, value: crop.metrics?.soilMoisture, scale: 100, levels: [[30, 'metricDry'], [70, 'metricGood'], [Infinity, 'metricWet']], icon: <Droplets size={23} aria-hidden="true" /> },
        { label: t.temperature, value: crop.metrics?.temprature ?? crop.metrics?.temperature, scale: 60, levels: [[15, 'metricCool'], [30, 'metricGood'], [40, 'metricWarm'], [Infinity, 'metricVeryWarm']], icon: <Thermometer size={23} aria-hidden="true" /> },
        { label: t.humidity, value: crop.metrics?.humidity, scale: 100, levels: [[30, 'metricDry'], [70, 'metricGood'], [Infinity, 'metricHumid']], icon: <CloudRain size={23} aria-hidden="true" /> },
        { label: t.windSpeed, value: crop.metrics?.windSpeed, scale: 60, levels: [[10, 'metricCalm'], [30, 'metricModerate'], [Infinity, 'metricStrong']], icon: <Wind size={23} aria-hidden="true" /> },
        { label: t.rainfall, value: crop.metrics?.rainFall ?? crop.metrics?.rainfall, scale: 20, levels: [[2, 'metricLow'], [10, 'metricModerate'], [Infinity, 'metricHigh']], icon: <CloudRain size={23} aria-hidden="true" /> },
      ]
    : []

  function getMetricInterpretation(metric) {
    if (metric.value === null || metric.value === undefined || metric.value === '') {
      return { label: t.statusUnknown, progress: 0 }
    }

    const value = Number(metric.value)
    if (!Number.isFinite(value)) {
      return { label: t.statusUnknown, progress: 0 }
    }

    const level = metric.levels.find(([threshold]) => value <= threshold)
    return {
      label: level ? t[level[1]] : t.statusUnknown,
      progress: Math.min(100, Math.max(0, (value / metric.scale) * 100)),
    }
  }

  const dateLocale = language === 'am' ? 'am-ET' : 'en-US'
  const sampleDecision =
    riskPreference === 'bold' && sampleDrySpellRisk === 'medium' ? 'PLANT' : 'WAIT'
  const decisionReason = {
    bold: t.boldDecisionReason,
    balanced: t.balancedDecisionReason,
    careful: t.carefulDecisionReason,
  }[riskPreference]
  const riskOptions = [
    { value: 'bold', label: t.riskBold, description: t.riskBoldDescription },
    { value: 'balanced', label: t.riskBalanced, description: t.riskBalancedDescription },
    { value: 'careful', label: t.riskCareful, description: t.riskCarefulDescription },
  ]

  return (
    <div className="app-shell" lang={language === 'am' ? 'am' : 'en'}>
      <Header
        page={page}
        setPage={setPage}
        language={language}
        toggleLanguage={toggleLanguage}
        t={t}
        currentUser={currentUser}
        onLogout={handleLogout}
      />

      <main className="main-content">
        {page === 'welcome' && <WelcomePage setPage={setPage} t={t} />}

        {page === 'auth' && (
          <AuthPage
            t={t}
            setPage={setPage}
            onAuthSuccess={handleAuthSuccess}
          />
        )}

        {page === 'moderator' && (
          <ModeratorPage
            t={t}
            setPage={setPage}
            currentUser={currentUser}
          />
        )}

        {page === 'location' && (
          <LocationPage
            farmLocation={farmLocation}
            updateLocation={updateLocation}
            useCurrentLocation={useCurrentLocation}
            continueFromLocation={continueFromLocation}
            coordinates={coordinates}
            locationMessage={locationMessage}
            setPage={setPage}
            t={t}
          />
        )}

        {page === 'dashboard' && (
          <DashboardPage
            t={t}
            currentUser={currentUser}
            locationSummary={locationSummary}
            setPage={setPage}
            selectedCrops={selectedCrops}
            activeCrop={activeCrop}
            setActiveCrop={setActiveCrop}
            riskPreference={riskPreference}
            setRiskPreference={setRiskPreference}
            sampleDecision={sampleDecision}
            decisionReason={decisionReason}
            riskOptions={riskOptions}
            rainfallHistory={crop?.rainfallHistory || []}
            sampleRainfallReference={sampleRainfallReference}
            crop={crop}
            loading={loading}
            error={error}
            setRefreshKey={setRefreshKey}
            rawStatus={rawStatus}
            statusLabel={statusLabel}
            statusTone={statusTone}
            metrics={metrics}
            getMetricInterpretation={getMetricInterpretation}
            dateLocale={dateLocale}
          />
        )}

        {page === 'guidance' && (
          <GuidancePage
            t={t}
            activeCrop={activeCrop}
            crop={crop}
            setPage={setPage}
          />
        )}
      </main>

      <Footer t={t} />
    </div>
  )
}

export default App

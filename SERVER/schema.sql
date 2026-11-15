-- ============================================================================
-- NASA Space Apps Challenge - Project Nebula Database Schema
-- Ethiopian Smallholder Farmer Crop Health & Regional Climate Monitoring
-- Target Regions: Arsi (Wheat), Bale (Wheat), Jimma (Coffee)
-- Database: PostgreSQL 14+
-- ============================================================================

\c projectnebula;

-- ----------------------------------------------------------------------------
-- 1. REGIONS
-- High-level Ethiopian agro-ecological zones with representative coordinates
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS regions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,         
    primary_crop VARCHAR(50) NOT NULL,          -- 'Wheat' for Arsi/Bale, 'Coffee' for Jimma
    climate_zone VARCHAR(100) NOT NULL,
    center_latitude DECIMAL(9, 6) NOT NULL CHECK (center_latitude BETWEEN -90 AND 90),
    center_longitude DECIMAL(9, 6) NOT NULL CHECK (center_longitude BETWEEN -180 AND 180),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_regions_name ON regions(name);

-- ----------------------------------------------------------------------------
-- 2. USERS & AUTHENTICATION
-- Multi-role authentication framework for 'farmer' and 'moderator'
-- Supports 16-digit Ethiopian Fayda national ID and phone-based logins
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    father_name VARCHAR(100) NOT NULL,
    phone VARCHAR(30) NOT NULL UNIQUE,
    fayda_id VARCHAR(16) NOT NULL UNIQUE CHECK (fayda_id ~ '^[0-9]{16}$'),
    email VARCHAR(150),
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'farmer' CHECK (role IN ('farmer', 'moderator')),
    region VARCHAR(50) DEFAULT 'Arsi',
    registered_by VARCHAR(20) DEFAULT 'self',   -- 'self', 'moderator', or 'system'
    refresh_token_hash VARCHAR(255),
    is_banned BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone);
CREATE INDEX IF NOT EXISTS idx_users_fayda ON users(fayda_id);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_region ON users(region);

-- ----------------------------------------------------------------------------
-- 3. REGIONAL HEALTH LOGS (Primary Area-Level Telemetry)
-- Fast live telemetry logs evaluated from API / satellite data
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS regional_health_logs (
    id BIGSERIAL PRIMARY KEY,
    region_id INTEGER NOT NULL REFERENCES regions(id) ON DELETE CASCADE,
    crop VARCHAR(50) NOT NULL,
    temperature DECIMAL(5, 2) NOT NULL,
    humidity DECIMAL(5, 2) NOT NULL,
    soil_moisture DECIMAL(5, 2) NOT NULL,
    rainfall DECIMAL(6, 2) NOT NULL DEFAULT 0.0,
    vegetation_coverage DECIMAL(5, 2) NOT NULL,
    ndvi DECIMAL(4, 3) NOT NULL,
    health_score DECIMAL(5, 2) NOT NULL,
    status VARCHAR(20) NOT NULL,                -- 'HEALTHY', 'STRESSED', 'FAILING' (mapped to 'Healthy', 'Warning', 'Critical' in API)
    primary_stress_factor VARCHAR(50) DEFAULT 'NONE',
    recommendation TEXT,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_regional_health_recent ON regional_health_logs(region_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_regional_health_crop ON regional_health_logs(crop);

-- ----------------------------------------------------------------------------
-- 4. FALSE START LOGS
-- Early planting season false-start risk evaluations (Belg/Kiremt seasons)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS false_start (
    id SERIAL PRIMARY KEY,
    region_id INTEGER NOT NULL REFERENCES regions(id) ON DELETE CASCADE,
    season_name VARCHAR(50) NOT NULL,         
    is_false_start BOOLEAN NOT NULL,          
    confidence DECIMAL(5, 2) NOT NULL CHECK (confidence BETWEEN 0.00 AND 100.00),        
    dry_spell_risk_days INTEGER NOT NULL CHECK (dry_spell_risk_days >= 0),     
    cumulative_rain_mm DECIMAL(6, 2) NOT NULL CHECK (cumulative_rain_mm >= 0),
    recommendation TEXT NOT NULL, 
    assessed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_false_start_region_recent ON false_start(region_id, assessed_at DESC);

-- ----------------------------------------------------------------------------
-- 5. FARMS
-- Individual farmer plots registered within a designated region
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS farms (
    id SERIAL PRIMARY KEY,
    region_id INTEGER NOT NULL REFERENCES regions(id) ON DELETE CASCADE,
    farmer_id INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    name VARCHAR(100) NOT NULL,               
    crop_type VARCHAR(50) NOT NULL,             -- 'Wheat' or 'Coffee'
    center_latitude DECIMAL(9, 6) NOT NULL CHECK (center_latitude BETWEEN -90 AND 90),
    center_longitude DECIMAL(9, 6) NOT NULL CHECK (center_longitude BETWEEN -180 AND 180),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Ensure farmer_id exists if farms was created in an earlier migration
ALTER TABLE farms ADD COLUMN IF NOT EXISTS farmer_id INTEGER REFERENCES users(user_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_farms_region ON farms(region_id);
CREATE INDEX IF NOT EXISTS idx_farms_farmer ON farms(farmer_id);

-- ----------------------------------------------------------------------------
-- 6. GRIDS (Sub-Farm 100m x 100m Resolution Cells)
-- Prepared for high-resolution satellite raster pipelines
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS grids (
    id SERIAL PRIMARY KEY,
    farm_id INTEGER NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
    grid_code VARCHAR(20) NOT NULL,           
    min_lat DECIMAL(9, 6) NOT NULL CHECK (min_lat BETWEEN -90 AND 90),
    max_lat DECIMAL(9, 6) NOT NULL CHECK (max_lat BETWEEN -90 AND 90),
    min_lon DECIMAL(9, 6) NOT NULL CHECK (min_lon BETWEEN -180 AND 180),
    max_lon DECIMAL(9, 6) NOT NULL CHECK (max_lon BETWEEN -180 AND 180),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_grid_bounds CHECK (min_lat <= max_lat AND min_lon <= max_lon)
);

CREATE INDEX IF NOT EXISTS idx_grids_farm ON grids(farm_id);
CREATE INDEX IF NOT EXISTS idx_grids_code ON grids(grid_code);

-- ----------------------------------------------------------------------------
-- 7. CROP HEALTH LOGS (Grid-Level Telemetry)
-- Deep telemetry stored per sub-grid cell
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS crop_health_logs (
    id BIGSERIAL PRIMARY KEY,
    grid_id INTEGER NOT NULL REFERENCES grids(id) ON DELETE CASCADE,
    temperature DECIMAL(5, 2) NOT NULL,
    humidity DECIMAL(5, 2) NOT NULL CHECK (humidity >= 0 AND humidity <= 100),
    soil_moisture DECIMAL(5, 2) NOT NULL CHECK (soil_moisture >= 0 AND soil_moisture <= 100),
    rainfall DECIMAL(6, 2) NOT NULL CHECK (rainfall >= 0),
    vegetation_coverage DECIMAL(5, 2) NOT NULL CHECK (vegetation_coverage >= 0 AND vegetation_coverage <= 100),
    ndvi DECIMAL(4, 3) NOT NULL CHECK (ndvi >= -1.000 AND ndvi <= 1.000),
    health_score DECIMAL(5, 2) NOT NULL CHECK (health_score >= 0.00 AND health_score <= 100.00),

    status VARCHAR(20) NOT NULL DEFAULT 'HEALTHY' 
        CHECK (status IN ('HEALTHY', 'STRESSED', 'FAILING')),

    primary_stress_factor VARCHAR(50) DEFAULT 'NONE'
        CHECK (primary_stress_factor IN (
            'NONE',           -- Healthy
            'DROUGHT',        -- Low soil moisture and rainfall
            'HEAT STRESS',    -- High temperatures hurting crops
            'WATERLOGGING',   -- Excess rainfall or saturated soil suffocating roots
            'LOW VEGETATION', -- Low NDVI or stunted coverage
            'FUNGAL RISK'     -- High humidity and moderate heat (Coffee Berry Disease)
        )),

    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_crop_health_grid_recent ON crop_health_logs(grid_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_crop_health_status ON crop_health_logs(status);

-- ============================================================================
-- SEED DATA & INITIALIZATION
-- ============================================================================

-- 1. Seed Initial Ethiopian Regions
INSERT INTO regions (id, name, primary_crop, climate_zone, center_latitude, center_longitude)
VALUES 
  (1, 'Arsi', 'Wheat', 'Highland / Cool Sub-humid', 7.500000, 39.200000),
  (2, 'Jimma', 'Coffee', 'Highland / Humid Tropical Forest', 7.673400, 36.834400),
  (3, 'Bale', 'Wheat', 'Highland / Semi-arid Plateau', 6.800000, 40.000000)
ON CONFLICT (name) DO UPDATE 
SET primary_crop = EXCLUDED.primary_crop,
    climate_zone = EXCLUDED.climate_zone,
    center_latitude = EXCLUDED.center_latitude,
    center_longitude = EXCLUDED.center_longitude;

-- Reset sequence to continue after seed IDs
SELECT setval('regions_id_seq', COALESCE((SELECT MAX(id) FROM regions), 1));

-- 2. Seed Hardcoded Demo Moderator (password: moderator123)
-- Phone: 0911000000 | Fayda ID: 1111222233334444 | Role: moderator
INSERT INTO users (first_name, father_name, phone, fayda_id, email, password_hash, role, region, registered_by)
VALUES (
    'Moderator',
    'Admin',
    '0911000000',
    '1111222233334444',
    'moderator@nebula.com',
    '$2b$10$b9/afgmT.7mXtczjqgfNMe2mQGGUwHeUkLCvCiDQLKGiTjeYuuOIu',
    'moderator',
    'Arsi',
    'system'
)
ON CONFLICT (phone) DO UPDATE 
SET role = 'moderator',
    password_hash = EXCLUDED.password_hash,
    fayda_id = EXCLUDED.fayda_id;

-- Reset users sequence
SELECT setval('users_user_id_seq', COALESCE((SELECT MAX(user_id) FROM users), 1));

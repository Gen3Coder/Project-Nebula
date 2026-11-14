CREATE DATABASE projectNebula;
\c projectNebula;

CREATE TABLE regions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,         
    primary_crop VARCHAR(50),                   -- Optional or primary crop for the region
    climate_zone VARCHAR(100) NOT NULL,
    center_latitude DECIMAL(9, 6) NOT NULL CHECK (center_latitude BETWEEN -90 AND 90),
    center_longitude DECIMAL(9, 6) NOT NULL CHECK (center_longitude BETWEEN -180 AND 180),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE false_start (
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

CREATE TABLE farms (
    id SERIAL PRIMARY KEY,
    region_id INTEGER NOT NULL REFERENCES regions(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,               
    crop_type VARCHAR(50) NOT NULL,  
    center_latitude DECIMAL(9, 6) NOT NULL CHECK (center_latitude BETWEEN -90 AND 90),
    center_longitude DECIMAL(9, 6) NOT NULL CHECK (center_longitude BETWEEN -180 AND 180),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE grids (
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

CREATE TABLE crop_health_logs (
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
            'FUNGAL RISK'     -- High humidity and moderate heat
        )),

    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

--Query Optimization
CREATE INDEX idx_false_start_region_recent ON false_start(region_id, assessed_at DESC);
CREATE INDEX idx_farms_region ON farms(region_id);
CREATE INDEX idx_grids_farm ON grids(farm_id);
CREATE INDEX idx_crop_health_grid_recent ON crop_health_logs(grid_id, recorded_at DESC);
CREATE INDEX idx_crop_health_status ON crop_health_logs(status);
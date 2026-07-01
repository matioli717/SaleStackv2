-- Neon PostgreSQL schema for Sales Prospecting
-- Run this in Neon SQL Editor after creating project

CREATE TABLE IF NOT EXISTS leads (
    id VARCHAR(100) PRIMARY KEY,
    lead_name VARCHAR(200) NOT NULL,
    business_type VARCHAR(100) NOT NULL,
    location VARCHAR(200) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    email VARCHAR(200),
    website VARCHAR(500),
    address TEXT,
    coordinates JSONB,
    osm_type VARCHAR(50),
    osm_id VARCHAR(100),
    source VARCHAR(50),
    category VARCHAR(50),
    status VARCHAR(20) DEFAULT 'new',
    raw_tags JSONB,
    tenant_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS proposals (
    id VARCHAR(100) PRIMARY KEY,
    lead_id VARCHAR(100) REFERENCES leads(id),
    lead_name VARCHAR(200),
    product VARCHAR(50),
    proposal TEXT,
    subject VARCHAR(300),
    status VARCHAR(20) DEFAULT 'pending',
    date TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_leads_category ON leads(category);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_tenant_id ON leads(tenant_id);
CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at);
CREATE INDEX IF NOT EXISTS idx_proposals_lead_id ON proposals(lead_id);
CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status);
CREATE INDEX IF NOT EXISTS idx_proposals_created_at ON proposals(created_at);
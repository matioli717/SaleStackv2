"""
Neon PostgreSQL database layer for Sales Prospecting
Replaces JSON file storage with persistent PostgreSQL
"""

import os
import json
import threading
from contextlib import contextmanager
from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool
    PG_AVAILABLE = True
except ImportError:
    PG_AVAILABLE = False

# Global pool - lazy initialization
_pool: Optional[ConnectionPool] = None
_pool_lock = threading.Lock()
_pool_initialized = False
_init_error: Optional[Exception] = None


def get_database_url() -> str:
    """Get DATABASE_URL from environment."""
    url = os.getenv("DATABASE_URL") or os.getenv("NEON_DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL or NEON_DATABASE_URL not set")
    # Ensure sslmode=require for Neon
    if "sslmode" not in url:
        url += "&sslmode=require" if "?" in url else "?sslmode=require"
    return url


def get_pool() -> Optional[ConnectionPool]:
    """Get or create connection pool (lazy init). Returns None if init failed."""
    global _pool, _pool_initialized, _init_error
    
    if _pool is not None:
        return _pool
    
    if _pool_initialized:
        # Already tried and failed
        return None
    
    with _pool_lock:
        if _pool is not None:
            return _pool
        if _pool_initialized:
            return None
        
        try:
            _pool = ConnectionPool(
                get_database_url(),
                min_size=0,  # Don't create connections at startup
                max_size=5,
                kwargs={"row_factory": dict_row},
                timeout=10,  # Connection timeout
                max_idle=300,
            )
            # Test connection
            with _pool.connection() as conn:
                conn.execute("SELECT 1")
            _pool_initialized = True
            return _pool
        except Exception as e:
            _init_error = e
            _pool_initialized = True
            _pool = None
            print(f"[WARN] Neon connection failed: {e}")
            return None


def is_neon_available() -> bool:
    """Check if Neon is available without blocking."""
    return get_pool() is not None


def init_db():
    """Initialize database tables."""
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            # Leads table
            cur.execute("""
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
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            # Proposals table
            cur.execute("""
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
                )
            """)
            # Indexes
            cur.execute("CREATE INDEX IF NOT EXISTS idx_leads_category ON leads(category)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_proposals_lead_id ON proposals(lead_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status)")
        conn.commit()


# ===== LEADS =====

def get_leads() -> List[Dict]:
    """Get all leads."""
    pool = get_pool()
    if pool is None:
        return []
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    id, lead_name, business_type, location, phone,
                    email, website, address, coordinates, osm_type,
                    osm_id, source, category, status, raw_tags,
                    to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') as created_at,
                    to_char(updated_at, 'YYYY-MM-DD HH24:MI:SS') as updated_at
                FROM leads ORDER BY created_at DESC
            """)
            return cur.fetchall()


def get_lead(lead_id: str) -> Optional[Dict]:
    """Get single lead by ID."""
    pool = get_pool()
    if pool is None:
        return None
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    id, lead_name, business_type, location, phone,
                    email, website, address, coordinates, osm_type,
                    osm_id, source, category, status, raw_tags,
                    to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') as created_at,
                    to_char(updated_at, 'YYYY-MM-DD HH24:MI:SS') as updated_at
                FROM leads WHERE id = %s
            """, (lead_id,))
            return cur.fetchone()


def upsert_leads(leads: List[Dict]) -> int:
    """Insert or update multiple leads. Returns count saved."""
    if not leads:
        return 0
    
    pool = get_pool()
    if pool is None:
        return 0
    
    saved = 0
    with pool.connection() as conn:
        with conn.cursor() as cur:
            for lead in leads:
                lead_id = lead.get("id") or lead.get("osm_id")
                if not lead_id:
                    continue
                
                # Check if exists
                cur.execute("SELECT id FROM leads WHERE id = %s", (lead_id,))
                exists = cur.fetchone()
                
                now = datetime.now()
                if exists:
                    # Update
                    cur.execute("""
                        UPDATE leads SET
                            lead_name = %s, business_type = %s, location = %s,
                            phone = %s, email = %s, website = %s, address = %s,
                            coordinates = %s, osm_type = %s, osm_id = %s,
                            source = %s, category = %s, status = %s,
                            raw_tags = %s, updated_at = %s
                        WHERE id = %s
                    """, (
                        lead.get("lead_name"), lead.get("business_type"),
                        lead.get("location"), lead.get("phone"),
                        lead.get("email"), lead.get("website"),
                        lead.get("address"), json.dumps(lead.get("coordinates")),
                        lead.get("osm_type"), lead.get("osm_id"),
                        lead.get("source"), lead.get("category"),
                        lead.get("status", "new"),
                        json.dumps(lead.get("raw_tags")),
                        now, lead_id
                    ))
                else:
                    # Insert
                    cur.execute("""
                        INSERT INTO leads (
                            id, lead_name, business_type, location, phone,
                            email, website, address, coordinates, osm_type,
                            osm_id, source, category, status, raw_tags,
                            created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        lead_id, lead.get("lead_name"), lead.get("business_type"),
                        lead.get("location"), lead.get("phone"),
                        lead.get("email"), lead.get("website"),
                        lead.get("address"), json.dumps(lead.get("coordinates")),
                        lead.get("osm_type"), lead.get("osm_id"),
                        lead.get("source"), lead.get("category"),
                        lead.get("status", "new"),
                        json.dumps(lead.get("raw_tags")),
                        now, now
                    ))
                saved += 1
        conn.commit()
    return saved


# ===== PROPOSALS =====

def get_proposals() -> List[Dict]:
    """Get all proposals."""
    pool = get_pool()
    if pool is None:
        return []
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    id, lead_id, lead_name, product, proposal,
                    subject, status, date,
                    to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') as created_at,
                    to_char(updated_at, 'YYYY-MM-DD HH24:MI:SS') as updated_at
                FROM proposals ORDER BY created_at DESC
            """)
            return cur.fetchall()


def get_proposal(proposal_id: str) -> Optional[Dict]:
    """Get single proposal by ID."""
    pool = get_pool()
    if pool is None:
        return None
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    id, lead_id, lead_name, product, proposal,
                    subject, status, date,
                    to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') as created_at,
                    to_char(updated_at, 'YYYY-MM-DD HH24:MI:SS') as updated_at
                FROM proposals WHERE id = %s
            """, (proposal_id,))
            return cur.fetchone()


def upsert_proposals(proposals: List[Dict]) -> int:
    """Insert or update multiple proposals. Returns count saved."""
    if not proposals:
        return 0
    
    pool = get_pool()
    if pool is None:
        return 0
    
    saved = 0
    with pool.connection() as conn:
        with conn.cursor() as cur:
            for prop in proposals:
                prop_id = prop.get("id")
                if not prop_id:
                    continue
                
                cur.execute("SELECT id FROM proposals WHERE id = %s", (prop_id,))
                exists = cur.fetchone()
                
                now = datetime.now()
                if exists:
                    cur.execute("""
                        UPDATE proposals SET
                            lead_id = %s, lead_name = %s, product = %s,
                            proposal = %s, subject = %s, status = %s,
                            date = %s, updated_at = %s
                        WHERE id = %s
                    """, (
                        prop.get("lead_id"), prop.get("lead_name"),
                        prop.get("product"), prop.get("proposal"),
                        prop.get("subject"), prop.get("status", "pending"),
                        prop.get("date"), now, prop_id
                    ))
                else:
                    cur.execute("""
                        INSERT INTO proposals (
                            id, lead_id, lead_name, product, proposal,
                            subject, status, date, created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        prop_id, prop.get("lead_id"), prop.get("lead_name"),
                        prop.get("product"), prop.get("proposal"),
                        prop.get("subject"), prop.get("status", "pending"),
                        prop.get("date") or now, now, now
                    ))
                saved += 1
        conn.commit()
    return saved


def get_stats() -> Dict:
    """Get aggregated stats."""
    pool = get_pool()
    if pool is None:
        return {
            "total_leads": 0,
            "total_proposals": 0,
            "categories": {},
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as count FROM leads")
            total_leads = cur.fetchone()["count"]
            
            cur.execute("SELECT COUNT(*) as count FROM proposals")
            total_proposals = cur.fetchone()["count"]
            
            cur.execute("SELECT category, COUNT(*) as count FROM leads GROUP BY category")
            categories = {row["category"] or "null": row["count"] for row in cur.fetchall()}
            
            return {
                "total_leads": total_leads,
                "total_proposals": total_proposals,
                "categories": categories,
                "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }


def close_pool():
    """Close connection pool."""
    global _pool
    if _pool:
        _pool.close()
        _pool = None
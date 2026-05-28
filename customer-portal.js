/**
 * Customer portal — magic-link auth + cloud lead sync + dashboard API
 * Adds /api/portal/* endpoints alongside the existing /api/customer/* (license-key-based) routes.
 */
const crypto = require('crypto');
const https  = require('https');

const RESEND_API_KEY = process.env.RESEND_API_KEY || '';
const JWT_SECRET     = process.env.JWT_SECRET || 'portal-jwt-2026-leadripper';
const TOKEN_TTL      = 15 * 60;          // magic link: 15 min
const JWT_TTL        = 30 * 24 * 3600;  // session: 30 days

const PRODUCT_DOMAINS = {
  'lead-scraper-pro': 'https://leadripper.com',
  'discovery1':       'https://discoveryoneleads.com',
  'prospecthunter':   'https://leadripper.com',
  'atomicscraper':    'https://atomicscraper.com',
  'leadsbaby':        'https://leads.baby',
};

const PRODUCT_INFO = {
  'lead-scraper-pro': { name: 'Lead Scraper Pro',  color: '#4FC3F7', bg: '#0D0D1A', win: 'LeadScraperPro.exe', mac: 'LeadScraperPro.dmg', support: 'support@leadripper.com' },
  'discovery1':       { name: 'Discovery1',         color: '#E67E22', bg: '#0D0A05', win: 'Discovery1.exe',      mac: 'Discovery1.dmg',      support: 'support@discoveryoneleads.com' },
  'prospecthunter':   { name: 'ProspectHunter',     color: '#8E44AD', bg: '#0D0A10', win: 'ProspectHunter.exe',  mac: 'ProspectHunter.dmg',  support: 'support@leadripper.com' },
  'atomicscraper':    { name: 'AtomicScraper',      color: '#00BCD4', bg: '#050F10', win: 'AtomicScraper.exe',   mac: 'AtomicScraper.dmg',   support: 'support@atomicscraper.com' },
  'leadsbaby':        { name: 'Leads.Baby',          color: '#FF6B9D', bg: '#0D0608', win: 'LeadsBaby.exe',       mac: 'LeadsBaby.dmg',       support: 'support@leads.baby' },
};

const BASE_DL = 'https://github.com/bensblueprints/gmaps-scraper-suite/releases/latest/download/';

// ── JWT helpers ──────────────────────────────────────────────────────────────

function signJWT(payload) {
  const data = JSON.stringify({ ...payload, iat: Math.floor(Date.now() / 1000) });
  const b64  = Buffer.from(data).toString('base64url');
  const sig  = crypto.createHmac('sha256', JWT_SECRET).update(b64).digest('base64url');
  return `${b64}.${sig}`;
}

function verifyJWT(token) {
  if (!token || typeof token !== 'string') return null;
  const parts = token.split('.');
  if (parts.length !== 2) return null;
  const [b64, sig] = parts;
  const expected = crypto.createHmac('sha256', JWT_SECRET).update(b64).digest('base64url');
  try {
    if (sig.length !== expected.length) return null;
    if (!crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(expected))) return null;
    const payload = JSON.parse(Buffer.from(b64, 'base64url').toString());
    if (payload.exp && Math.floor(Date.now() / 1000) > payload.exp) return null;
    return payload;
  } catch { return null; }
}

function requirePortalAuth(req, res, next) {
  const auth  = (req.headers['authorization'] || '').trim();
  const token = auth.startsWith('Bearer ') ? auth.slice(7) : null;
  const payload = verifyJWT(token);
  if (!payload || !payload.email || !payload.license_key) {
    return res.status(401).json({ error: 'unauthorized' });
  }
  req.portalUser = payload;
  next();
}

// ── Resend email helper ───────────────────────────────────────────────────────

function sendEmail(to, subject, html) {
  if (!RESEND_API_KEY) { console.log('[PORTAL] No RESEND_API_KEY — email skipped'); return; }
  const body = JSON.stringify({ from: 'noreply@benjisaiempire.com', to: [to], subject, html });
  const req  = https.request({
    hostname: 'api.resend.com', path: '/emails', method: 'POST',
    headers: { 'Authorization': `Bearer ${RESEND_API_KEY}`, 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) },
  }, r => { let d = ''; r.on('data', c => d += c); r.on('end', () => console.log('[PORTAL] Email sent:', r.statusCode, to)); });
  req.on('error', e => console.error('[PORTAL] Email error:', e.message));
  req.write(body); req.end();
}

// ── Module export ─────────────────────────────────────────────────────────────

module.exports = function(app, db) {

  // Schema
  db.exec(`
    CREATE TABLE IF NOT EXISTS portal_users (
      email      TEXT PRIMARY KEY,
      created_at INTEGER DEFAULT (strftime('%s','now')),
      last_seen  INTEGER
    );
    CREATE TABLE IF NOT EXISTS portal_tokens (
      token      TEXT PRIMARY KEY,
      email      TEXT NOT NULL,
      created_at INTEGER DEFAULT (strftime('%s','now')),
      used       INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS portal_leads (
      id           INTEGER PRIMARY KEY AUTOINCREMENT,
      license_key  TEXT NOT NULL,
      product      TEXT NOT NULL,
      name         TEXT NOT NULL DEFAULT '',
      phone        TEXT DEFAULT '',
      email_addr   TEXT DEFAULT '',
      platform     TEXT DEFAULT '',
      address      TEXT DEFAULT '',
      city         TEXT DEFAULT '',
      state        TEXT DEFAULT '',
      website      TEXT DEFAULT '',
      category     TEXT DEFAULT '',
      rating       TEXT DEFAULT '',
      review_count TEXT DEFAULT '',
      industry     TEXT DEFAULT '',
      scraped_at   TEXT,
      synced_at    INTEGER DEFAULT (strftime('%s','now')),
      UNIQUE(license_key, name, phone)
    );
    CREATE INDEX IF NOT EXISTS idx_pl_license  ON portal_leads(license_key);
    CREATE INDEX IF NOT EXISTS idx_pl_industry ON portal_leads(industry);
    CREATE INDEX IF NOT EXISTS idx_pl_city     ON portal_leads(city);
  `);

  // ── POST /api/portal/request-login ─────────────────────────────────────────
  app.post('/api/portal/request-login', (req, res) => {
    const email = (req.body?.email || '').toLowerCase().trim();
    if (!email || !email.includes('@')) return res.status(400).json({ error: 'valid email required' });

    const lic = db.prepare(`SELECT * FROM licenses WHERE LOWER(customer_email) = ? AND status = 'active'`).get(email);
    if (!lic) {
      // Always 200 — don't reveal non-existence
      return res.json({ ok: true });
    }

    const info   = PRODUCT_INFO[lic.product] || PRODUCT_INFO['lead-scraper-pro'];
    const domain = PRODUCT_DOMAINS[lic.product] || 'https://leadripper.com';
    const token  = crypto.randomBytes(32).toString('hex');
    const exp    = Math.floor(Date.now() / 1000) + TOKEN_TTL;

    db.prepare(`INSERT OR REPLACE INTO portal_users (email) VALUES (?)`).run(email);
    db.prepare(`INSERT INTO portal_tokens (token, email) VALUES (?, ?)`).run(token, email);

    const loginUrl = `${domain}/dashboard.html?t=${token}`;
    sendEmail(email, `Sign in to ${info.name}`, `
      <!DOCTYPE html><html><head><meta charset="UTF-8"></head>
      <body style="margin:0;background:#0D0D0D;font-family:sans-serif">
      <div style="max-width:560px;margin:0 auto;padding:48px 24px">
        <h2 style="color:${info.color};margin:0 0 8px;font-size:26px">${info.name}</h2>
        <p style="color:#9E9E9E;margin:0 0 32px;font-size:13px">Customer Portal</p>
        <p style="color:#E0E0E0;margin:0 0 24px">Click below to sign in. This link expires in 15 minutes and can only be used once.</p>
        <a href="${loginUrl}" style="display:inline-block;background:${info.color};color:#000;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:700;font-size:15px">Sign In to Dashboard &rarr;</a>
        <p style="color:#424242;font-size:12px;margin-top:32px;border-top:1px solid #222;padding-top:16px">
          If you didn't request this, ignore it — your account is safe.<br>
          Need help? <a href="mailto:${info.support}" style="color:${info.color}">${info.support}</a>
        </p>
      </div></body></html>
    `);

    console.log(`[PORTAL] Login link sent to ${email} (${lic.product})`);
    res.json({ ok: true });
  });

  // ── GET /api/portal/verify-token?t=TOKEN ────────────────────────────────────
  app.get('/api/portal/verify-token', (req, res) => {
    const { t } = req.query;
    if (!t) return res.status(400).json({ error: 'token required' });

    const row = db.prepare(`SELECT * FROM portal_tokens WHERE token = ? AND used = 0`).get(t);
    if (!row) return res.status(401).json({ error: 'invalid or already-used link' });

    const age = Math.floor(Date.now() / 1000) - row.created_at;
    if (age > TOKEN_TTL) return res.status(401).json({ error: 'link expired — request a new one' });

    const lic = db.prepare(`SELECT * FROM licenses WHERE LOWER(customer_email) = ? AND status = 'active'`).get(row.email);
    if (!lic) return res.status(404).json({ error: 'no active license found for this email' });

    db.prepare(`UPDATE portal_tokens SET used = 1 WHERE token = ?`).run(t);
    db.prepare(`UPDATE portal_users SET last_seen = strftime('%s','now') WHERE email = ?`).run(row.email);

    const jwt = signJWT({
      email:       row.email,
      license_key: lic.license_key,
      product:     lic.product,
      exp:         Math.floor(Date.now() / 1000) + JWT_TTL,
    });

    res.json({ ok: true, jwt, email: row.email, product: lic.product });
  });

  // ── GET /api/portal/me ────────────────────────────────────────────────────
  app.get('/api/portal/me', requirePortalAuth, (req, res) => {
    const { email, license_key } = req.portalUser;
    const lic   = db.prepare(`SELECT * FROM licenses WHERE license_key = ? AND status = 'active'`).get(license_key);
    if (!lic) return res.status(404).json({ error: 'license not found' });

    const nodes      = db.prepare(`SELECT * FROM license_nodes WHERE license_key = ?`).all(license_key);
    const leadCount  = db.prepare(`SELECT COUNT(*) AS n FROM portal_leads WHERE license_key = ?`).get(license_key)?.n || 0;
    const info       = PRODUCT_INFO[lic.product] || PRODUCT_INFO['lead-scraper-pro'];

    db.prepare(`UPDATE portal_users SET last_seen = strftime('%s','now') WHERE email = ?`).run(email);

    res.json({
      email,
      license_key: lic.license_key,
      product:     lic.product,
      product_name: info.name,
      product_color: info.color,
      product_bg:   info.bg,
      plan:         lic.plan,
      max_nodes:    lic.max_nodes,
      nodes_used:   nodes.length,
      nodes,
      lead_count:   leadCount,
      downloads: {
        windows: BASE_DL + info.win,
        macos:   BASE_DL + info.mac,
      },
      created_at: lic.created_at,
    });
  });

  // ── GET /api/portal/leads ─────────────────────────────────────────────────
  app.get('/api/portal/leads', requirePortalAuth, (req, res) => {
    const { license_key } = req.portalUser;
    const page     = Math.max(1, parseInt(req.query.page  || '1'));
    const limit    = Math.min(500, parseInt(req.query.limit || '100'));
    const offset   = (page - 1) * limit;
    const search   = (req.query.search   || '').trim();
    const industry = (req.query.industry || '').trim();

    let where  = 'license_key = ?';
    const args = [license_key];
    if (industry) { where += ' AND industry = ?';           args.push(industry); }
    if (search)   {
      where += ' AND (name LIKE ? OR city LIKE ? OR email_addr LIKE ? OR website LIKE ?)';
      const s = `%${search}%`;
      args.push(s, s, s, s);
    }

    const total = db.prepare(`SELECT COUNT(*) AS n FROM portal_leads WHERE ${where}`).get(...args)?.n || 0;
    const leads = db.prepare(`SELECT * FROM portal_leads WHERE ${where} ORDER BY id DESC LIMIT ? OFFSET ?`).all(...args, limit, offset);

    res.json({ leads, total, page, pages: Math.ceil(total / limit) || 1 });
  });

  // ── GET /api/portal/leads/industries ─────────────────────────────────────
  app.get('/api/portal/leads/industries', requirePortalAuth, (req, res) => {
    const { license_key } = req.portalUser;
    const rows = db.prepare(`
      SELECT industry, COUNT(*) AS n FROM portal_leads
      WHERE license_key = ? AND industry != ''
      GROUP BY industry ORDER BY n DESC
    `).all(license_key);
    res.json(rows);
  });

  // ── GET /api/portal/leads/export ─────────────────────────────────────────
  app.get('/api/portal/leads/export', requirePortalAuth, (req, res) => {
    const { license_key } = req.portalUser;
    const industry = (req.query.industry || '').trim();
    let where = 'license_key = ?';
    const args = [license_key];
    if (industry) { where += ' AND industry = ?'; args.push(industry); }

    const rows = db.prepare(`SELECT * FROM portal_leads WHERE ${where} ORDER BY id DESC LIMIT 500000`).all(...args);
    const cols = ['name','phone','email_addr','platform','address','city','state','website','category','rating','review_count','industry','scraped_at'];
    const esc  = v => v == null ? '' : `"${String(v).replace(/"/g,'""')}"`;
    let csv    = cols.join(',') + '\n';
    for (const r of rows) csv += cols.map(c => esc(r[c])).join(',') + '\n';
    res.setHeader('Content-Type', 'text/csv');
    res.setHeader('Content-Disposition', `attachment; filename="leads-export-${Date.now()}.csv"`);
    res.send(csv);
  });

  // ── DELETE /api/portal/nodes/:machine_id ──────────────────────────────────
  app.delete('/api/portal/nodes/:machine_id', requirePortalAuth, (req, res) => {
    const { license_key } = req.portalUser;
    db.prepare(`DELETE FROM license_nodes WHERE license_key = ? AND machine_id = ?`).run(license_key, req.params.machine_id);
    res.json({ ok: true });
  });

  // ── POST /api/portal/sync-leads ───────────────────────────────────────────
  // Called by desktop app after each scrape. Auth via x-license-key header.
  app.post('/api/portal/sync-leads', (req, res) => {
    const licKey = (req.headers['x-license-key'] || '').trim();
    if (!licKey) return res.status(401).json({ error: 'x-license-key header required' });

    const lic = db.prepare(`SELECT product FROM licenses WHERE license_key = ? AND status = 'active'`).get(licKey);
    if (!lic) return res.status(403).json({ error: 'invalid license' });

    const leads = Array.isArray(req.body?.leads) ? req.body.leads : [];
    if (!leads.length) return res.json({ ok: true, inserted: 0 });

    const ins = db.prepare(`
      INSERT OR IGNORE INTO portal_leads
        (license_key, product, name, phone, email_addr, platform,
         address, city, state, website, category, rating, review_count, industry, scraped_at)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    `);

    let inserted = 0;
    const batch  = db.transaction(items => {
      for (const l of items) {
        const r = ins.run(
          licKey, lic.product,
          l.name || '', l.phone || '', l.email || '',
          l.platform || '', l.address || '', l.city || '', l.state || '',
          l.website || '', l.category || '', l.rating || '', l.review_count || '',
          l.industry || '', l.scraped_at || new Date().toISOString()
        );
        if (r.changes) inserted++;
      }
    });
    batch(leads.slice(0, 5000)); // cap at 5000 per request

    console.log(`[PORTAL] Synced ${inserted}/${leads.length} leads for ${licKey}`);
    res.json({ ok: true, inserted, total: leads.length });
  });

  console.log('[CustomerPortal] Routes registered');
};

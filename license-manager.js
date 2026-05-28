/**
 * License Manager — node-locked, multi-product licensing
 */
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const https = require('https');

const RESEND_API_KEY = process.env.RESEND_API_KEY || '';
const BASE_DL = 'https://github.com/bensblueprints/gmaps-scraper-suite/releases/latest/download/';

const PRODUCT_INFO = {
  'lead-scraper-pro': { win: 'LeadScraperPro.exe', mac: 'LeadScraperPro.dmg', name: 'Lead Scraper Pro',  color: '#4FC3F7', support: 'support@leadripper.com' },
  'discovery1':       { win: 'Discovery1.exe',      mac: 'Discovery1.dmg',     name: 'Discovery1',        color: '#E67E22', support: 'support@discoveryoneleads.com' },
  'prospecthunter':   { win: 'ProspectHunter.exe',  mac: 'ProspectHunter.dmg', name: 'ProspectHunter',    color: '#8E44AD', support: 'support@leadripper.com' },
  'atomicscraper':    { win: 'AtomicScraper.exe',   mac: 'AtomicScraper.dmg',  name: 'AtomicScraper',     color: '#00BCD4', support: 'support@atomicscraper.com' },
  'leadsbaby':        { win: 'LeadsBaby.exe',        mac: 'LeadsBaby.dmg',      name: 'Leads.Baby',        color: '#FF6B9D', support: 'support@leads.baby' },
};

function sendLicenseEmail(to, customerName, licenseKey, product, plan) {
  if (!RESEND_API_KEY || !to) {
    console.log('[EMAIL] Skipped — no Resend key or no email for:', to);
    return;
  }
  const info = PRODUCT_INFO[product] || PRODUCT_INFO['lead-scraper-pro'];
  const displayName = customerName || to.split('@')[0];
  const planLabel = plan === 'lifetime' ? 'Lifetime' : 'Monthly';

  const html = `<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0D0D0D;font-family:sans-serif">
<div style="max-width:600px;margin:0 auto;padding:40px 24px">
  <h1 style="color:${info.color};font-size:28px;margin:0 0 4px">${info.name}</h1>
  <p style="color:#616161;margin:0 0 32px">${planLabel} License — Activated</p>

  <p style="color:#E0E0E0;margin:0 0 24px">Hi ${displayName},</p>
  <p style="color:#9E9E9E;margin:0 0 32px">Your license is ready. Here is your key and download links.</p>

  <div style="background:#1A1A1A;border:2px solid ${info.color};border-radius:10px;padding:24px;margin-bottom:32px;text-align:center">
    <p style="color:#9E9E9E;font-size:12px;letter-spacing:2px;margin:0 0 10px;text-transform:uppercase">Your License Key</p>
    <p style="color:${info.color};font-size:24px;font-family:monospace;font-weight:900;letter-spacing:3px;margin:0">${licenseKey}</p>
  </div>

  <h3 style="color:#E0E0E0;margin:0 0 16px">Download Your Software</h3>
  <table style="width:100%;border-collapse:collapse;margin-bottom:32px">
    <tr>
      <td style="padding:8px 8px 8px 0">
        <a href="${BASE_DL}${info.win}" style="display:block;background:${info.color};color:#000;padding:14px 0;border-radius:8px;text-decoration:none;font-weight:700;font-size:15px;text-align:center">
          &#8659; Windows (.exe)
        </a>
      </td>
      <td style="padding:8px 0 8px 8px">
        <a href="${BASE_DL}${info.mac}" style="display:block;background:#2A2A2A;color:#E0E0E0;padding:14px 0;border-radius:8px;text-decoration:none;font-weight:700;font-size:15px;text-align:center;border:1px solid #444">
          &#8659; macOS (.dmg)
        </a>
      </td>
    </tr>
  </table>

  <div style="background:#1A1A1A;border-radius:10px;padding:24px;margin-bottom:32px">
    <h3 style="color:#E0E0E0;margin:0 0 16px;font-size:16px">Getting Started</h3>
    <ol style="color:#9E9E9E;padding-left:20px;margin:0;line-height:2">
      <li>Download and run the installer for your OS</li>
      <li>Windows: if SmartScreen appears, click <strong style="color:#E0E0E0">More info</strong> then <strong style="color:#E0E0E0">Run anyway</strong></li>
      <li>Paste your license key above and click <strong style="color:#E0E0E0">Activate</strong></li>
      <li>Select your industries, enter a city or state, click <strong style="color:${info.color}">Start Scrape</strong></li>
      <li>Leads appear in real time — export to CSV when done</li>
    </ol>
  </div>

  <div style="background:#111;border-radius:8px;padding:16px;margin-bottom:32px">
    <p style="color:#616161;font-size:13px;margin:0">
      <strong style="color:#9E9E9E">Your license covers 1 computer.</strong>
      Need to run on additional machines? Purchase extra nodes at $99 each — reply to this email to add them instantly.
    </p>
  </div>

  <p style="color:#616161;font-size:13px;border-top:1px solid #222;padding-top:20px;margin:0">
    Questions? Reply to this email or contact <a href="mailto:${info.support}" style="color:${info.color}">${info.support}</a>
  </p>
</div>
</body>
</html>`;

  const payload = JSON.stringify({
    from: `${info.name} <noreply@benjisaiempire.com>`,
    to: [to],
    subject: `Your ${info.name} License Key — ${licenseKey}`,
    html,
  });

  const req = https.request({
    hostname: 'api.resend.com',
    path: '/emails',
    method: 'POST',
    headers: {
      'Authorization': 'Bearer ' + RESEND_API_KEY,
      'Content-Type': 'application/json',
      'Content-Length': Buffer.byteLength(payload),
    },
  }, (res) => {
    let data = '';
    res.on('data', d => data += d);
    res.on('end', () => console.log('[EMAIL] Sent to', to, '— status:', res.statusCode));
  });
  req.on('error', e => console.error('[EMAIL] Error:', e.message));
  req.write(payload);
  req.end();
}

module.exports = function(app, db, isValidLicenseKey, requireAdmin) {

  db.exec(`
    CREATE TABLE IF NOT EXISTS licenses (
      id            INTEGER PRIMARY KEY AUTOINCREMENT,
      license_key   TEXT UNIQUE NOT NULL,
      product       TEXT NOT NULL DEFAULT 'lead-scraper-pro',
      plan          TEXT NOT NULL DEFAULT 'lifetime',
      max_nodes     INTEGER NOT NULL DEFAULT 1,
      customer_email TEXT,
      customer_name  TEXT,
      status        TEXT NOT NULL DEFAULT 'active',
      created_at    INTEGER DEFAULT (strftime('%s','now')),
      expires_at    INTEGER,
      payment_id    TEXT,
      notes         TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_licenses_key ON licenses(license_key);
    CREATE INDEX IF NOT EXISTS idx_licenses_product ON licenses(product);

    CREATE TABLE IF NOT EXISTS license_nodes (
      id            INTEGER PRIMARY KEY AUTOINCREMENT,
      license_key   TEXT NOT NULL,
      machine_id    TEXT NOT NULL,
      label         TEXT,
      registered_at INTEGER DEFAULT (strftime('%s','now')),
      last_seen     INTEGER,
      UNIQUE(license_key, machine_id)
    );
    CREATE INDEX IF NOT EXISTS idx_ln_key ON license_nodes(license_key);
    CREATE INDEX IF NOT EXISTS idx_ln_machine ON license_nodes(machine_id);
  `);

  const PREFIXES = {
    'lead-scraper-pro': 'LSP',
    'discovery1':       'D1',
    'prospecthunter':   'PH',
    'atomicscraper':    'AS',
    'leadsbaby':        'LB',
  };

  function generateKey(product) {
    const prefix = PREFIXES[product] || 'LIC';
    const rand = crypto.randomBytes(8).toString('hex').toUpperCase();
    return `${prefix}-${rand.slice(0,4)}-${rand.slice(4,8)}-${rand.slice(8,12)}-${rand.slice(12)}`;
  }

  function appendLicenseHash(key) {
    const hashPath = path.join(__dirname, 'license-hashes.json');
    let hashes = [];
    try { hashes = JSON.parse(fs.readFileSync(hashPath, 'utf8')); } catch {}
    const h = crypto.createHash('sha256').update(key.trim()).digest('hex');
    if (!hashes.includes(h)) {
      hashes.push(h);
      fs.writeFileSync(hashPath, JSON.stringify(hashes, null, 2));
    }
  }

  // Create a license key (admin — also sends email if customer_email provided)
  app.post('/api/licenses/create', requireAdmin, (req, res) => {
    const { product = 'lead-scraper-pro', plan = 'lifetime', max_nodes = 1,
            customer_email = '', customer_name = '', expires_at = null,
            payment_id = '', notes = '', send_email = true } = req.body || {};
    const key = generateKey(product);
    appendLicenseHash(key);
    db.prepare(`INSERT INTO licenses (license_key, product, plan, max_nodes, customer_email,
      customer_name, status, expires_at, payment_id, notes) VALUES (?,?,?,?,?,?,'active',?,?,?)`)
      .run(key, product, plan, max_nodes, customer_email, customer_name, expires_at, payment_id, notes);
    if (send_email && customer_email) {
      sendLicenseEmail(customer_email, customer_name, key, product, plan);
    }
    res.json({ ok: true, license_key: key, product, plan, max_nodes, customer_email });
  });

  // Add an extra node to a license
  app.post('/api/licenses/add-node', requireAdmin, (req, res) => {
    const { license_key, count = 1 } = req.body || {};
    if (!license_key) return res.status(400).json({ error: 'license_key required' });
    const lic = db.prepare('SELECT * FROM licenses WHERE license_key = ?').get(license_key);
    if (!lic) return res.status(404).json({ error: 'license not found' });
    db.prepare('UPDATE licenses SET max_nodes = max_nodes + ? WHERE license_key = ?').run(count, license_key);
    const updated = db.prepare('SELECT max_nodes FROM licenses WHERE license_key = ?').get(license_key);
    res.json({ ok: true, license_key, max_nodes: updated.max_nodes });
  });

  // List licenses (admin)
  app.get('/api/licenses/list', requireAdmin, (req, res) => {
    const { product, status = 'active', limit = 100 } = req.query;
    let q = 'SELECT * FROM licenses WHERE status = ?';
    const params = [status];
    if (product) { q += ' AND product = ?'; params.push(product); }
    q += ' ORDER BY created_at DESC LIMIT ?';
    params.push(Number(limit));
    res.json(db.prepare(q).all(...params));
  });

  // Get a single license (admin)
  app.get('/api/licenses/:key', requireAdmin, (req, res) => {
    const lic = db.prepare('SELECT * FROM licenses WHERE license_key = ?').get(req.params.key);
    if (!lic) return res.status(404).json({ error: 'not found' });
    const nodes = db.prepare('SELECT * FROM license_nodes WHERE license_key = ?').all(req.params.key);
    res.json({ ...lic, registered_nodes: nodes });
  });

  // Revoke a license (admin)
  app.post('/api/licenses/revoke', requireAdmin, (req, res) => {
    const { license_key } = req.body || {};
    db.prepare("UPDATE licenses SET status = 'revoked' WHERE license_key = ?").run(license_key);
    res.json({ ok: true });
  });

  // Resend license email manually (admin)
  app.post('/api/licenses/resend-email', requireAdmin, (req, res) => {
    const { license_key } = req.body || {};
    const lic = db.prepare('SELECT * FROM licenses WHERE license_key = ?').get(license_key);
    if (!lic) return res.status(404).json({ error: 'not found' });
    if (!lic.customer_email) return res.status(400).json({ error: 'no email on file' });
    sendLicenseEmail(lic.customer_email, lic.customer_name, lic.license_key, lic.product, lic.plan);
    res.json({ ok: true, sent_to: lic.customer_email });
  });

  // Checkout initiate — capture lead info, notify admin, return pending status
  db.exec(`
    CREATE TABLE IF NOT EXISTS pending_orders (
      id             INTEGER PRIMARY KEY AUTOINCREMENT,
      product        TEXT NOT NULL,
      plan           TEXT NOT NULL,
      customer_email TEXT NOT NULL,
      customer_name  TEXT,
      created_at     INTEGER DEFAULT (strftime('%s','now')),
      notified       INTEGER DEFAULT 0
    );
  `);

  app.post('/api/checkout/initiate', (req, res) => {
    const { product = 'leadsbaby', plan = 'lifetime',
            customer_email = '', customer_name = '' } = req.body || {};
    if (!customer_email || !customer_email.includes('@')) {
      return res.status(400).json({ error: 'valid email required' });
    }
    const info = PRODUCT_INFO[product] || PRODUCT_INFO['leadsbaby'];
    const planLabel = plan === 'lifetime' ? 'Lifetime ($997)' : 'Monthly ($297/mo)';

    db.prepare(`INSERT INTO pending_orders (product, plan, customer_email, customer_name) VALUES (?,?,?,?)`)
      .run(product, plan, customer_email, customer_name || customer_email.split('@')[0]);

    // Notify admin
    if (RESEND_API_KEY) {
      const payload = JSON.stringify({
        from: `${info.name} Orders <noreply@benjisaiempire.com>`,
        to: ['ben@advancedmarketing.co'],
        subject: `New Order: ${info.name} ${planLabel} — ${customer_email}`,
        html: `<p>New purchase request:</p><ul><li><b>Product:</b> ${info.name}</li><li><b>Plan:</b> ${planLabel}</li><li><b>Email:</b> ${customer_email}</li><li><b>Name:</b> ${customer_name || '—'}</li></ul><p>Create their license manually or set up Airwallex payment links.</p>`,
      });
      const req2 = https.request({
        hostname: 'api.resend.com', path: '/emails', method: 'POST',
        headers: { 'Authorization': 'Bearer ' + RESEND_API_KEY, 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(payload) },
      }, (r) => { let d = ''; r.on('data', x => d += x); r.on('end', () => console.log('[ORDER] Admin notified:', r.statusCode)); });
      req2.on('error', e => console.error('[ORDER] Email error:', e.message));
      req2.write(payload);
      req2.end();
    }

    console.log(`[ORDER] ${product} ${plan} from ${customer_email}`);
    res.json({ ok: true, pending: true, message: 'Order received — check your email shortly.' });
  });

  // Airwallex webhook — auto-create license on successful payment
  app.post('/api/webhook/airwallex', (req, res) => {
    const body = req.body || {};
    const event = body.name || body.type || '';
    if (event.includes('succeeded') || event.includes('completed') || event.includes('paid')) {
      const meta      = body.data?.object?.metadata || body.metadata || {};
      const product   = meta.product   || 'lead-scraper-pro';
      const plan      = meta.plan      || 'lifetime';
      const max_nodes = parseInt(meta.max_nodes || '1', 10);
      const email     = body.data?.object?.customer_email || meta.email || '';
      const name      = body.data?.object?.customer_name  || meta.customer_name || '';
      const paymentId = body.data?.object?.id || body.id || '';
      const key = generateKey(product);
      appendLicenseHash(key);
      db.prepare(`INSERT OR IGNORE INTO licenses
        (license_key, product, plan, max_nodes, customer_email, customer_name, status, payment_id)
        VALUES (?,?,?,?,?,?,'active',?)`)
        .run(key, product, plan, max_nodes, email, name, paymentId);
      console.log(`[LICENSE] Created ${key} for ${email} (${product} ${plan})`);
      sendLicenseEmail(email, name, key, product, plan);
    }
    res.json({ ok: true });
  });

  console.log('[LicenseManager] Routes registered');
  return { generateKey, appendLicenseHash };
};

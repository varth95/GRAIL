// ── Config ────────────────────────────────────────────────────────────────────
const API = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://localhost:8000'
  : 'https://grail-6xqs.onrender.com';

// ── State ─────────────────────────────────────────────────────────────────────
let garments = [];
let pendingColorGarmentId = null;
let currentUserId = '00000000-0000-0000-0000-000000000001'; // demo user

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  checkServer();
  setupNav();
  setupUpload();
  setupColorPicker();
  loadTrends();
  setInterval(checkServer, 10000);
});

// ── Server Health ─────────────────────────────────────────────────────────────
async function checkServer() {
  const dot = document.getElementById('serverStatus');
  try {
    const r = await fetch(`${API}/health`, { signal: AbortSignal.timeout(15000) });
    if (r.ok) {
      dot.classList.add('online');
      dot.title = 'Server online';
      updateStats();
      loadTrends(); // auto-load trends when server wakes up
    } else throw new Error();
  } catch {
    dot.classList.remove('online');
    dot.title = 'Server is waking up... please wait 30 seconds and refresh';
    // Show a helpful message
    document.getElementById('trendsGrid').innerHTML = `
      <div class="empty-state">
        <i class="fas fa-moon"></i>
        <p>Server is waking up — please wait 30 seconds then click Refresh Trends</p>
      </div>`;
  }
}

// ── Navigation ────────────────────────────────────────────────────────────────
function setupNav() {
  document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', e => {
      e.preventDefault();
      const target = link.getAttribute('href').replace('#', '');
      showSection(target);
    });
  });
}

function showSection(id) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
  const section = document.getElementById(id);
  if (section) section.classList.add('active');
  const link = document.querySelector(`.nav-link[href="#${id}"]`);
  if (link) link.classList.add('active');
  window.scrollTo({ top: 0, behavior: 'smooth' });

  if (id === 'trends') loadTrends();
}

// ── Stats ─────────────────────────────────────────────────────────────────────
async function updateStats() {
  try {
    const r = await fetch(`${API}/trends`);
    const data = await r.json();
    animateNumber('statTrends', data.trends?.length || 0);
  } catch {}
  animateNumber('statGarments', garments.length);
  animateNumber('statOutfits', garments.filter(g => !g.color_pending).length > 0 ? garments.length * 2 : 0);
}

function animateNumber(id, target) {
  const el = document.getElementById(id);
  if (!el) return;
  const start = parseInt(el.textContent) || 0;
  const diff = target - start;
  const steps = 20;
  let step = 0;
  const timer = setInterval(() => {
    step++;
    el.textContent = Math.round(start + (diff * step / steps));
    if (step >= steps) clearInterval(timer);
  }, 30);
}

// ── Upload ────────────────────────────────────────────────────────────────────
function setupUpload() {
  const zone = document.getElementById('uploadZone');
  const input = document.getElementById('garmentFile');

  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) handleUpload(file);
  });
  zone.addEventListener('click', e => {
    if (e.target.tagName !== 'BUTTON') input.click();
  });
  input.addEventListener('change', () => {
    if (input.files[0]) handleUpload(input.files[0]);
  });
}

async function handleUpload(file) {
  const result = document.getElementById('uploadResult');
  result.className = 'upload-result';
  result.classList.remove('hidden');

  // Validate client-side first
  const validTypes = ['image/jpeg', 'image/png', 'image/webp'];
  if (!validTypes.includes(file.type)) {
    result.classList.add('error');
    result.innerHTML = `<i class="fas fa-times-circle"></i> Invalid file type. Use JPG, PNG, or WebP.`;
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    result.classList.add('error');
    result.innerHTML = `<i class="fas fa-times-circle"></i> File too large. Max 10MB.`;
    return;
  }

  showLoader('Analysing your garment...');

  const formData = new FormData();
  formData.append('file', file);

  // Add a fake JWT for demo (backend middleware requires it)
  const fakeToken = await getFakeToken();

  try {
    const r = await fetch(`${API}/vision/analyze`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${fakeToken}` },
      body: formData,
    });
    const data = await r.json();
    hideLoader();

    if (r.ok) {
      const garment = data.garment;
      garments.push(garment);
      renderGarments();
      updateStats();

      result.classList.add('success');
      result.innerHTML = `
        <div style="display:flex;align-items:center;gap:1rem">
          <i class="fas fa-check-circle" style="color:var(--green);font-size:1.5rem"></i>
          <div>
            <strong>${garment.sub_category || 'Garment'} added!</strong>
            <div style="font-size:0.85rem;color:var(--text-muted);margin-top:0.25rem">
              Category: ${garment.category} ${garment.color_pending ? '· <span style="color:var(--orange)">Color needs correction</span>' : `· Color: <span style="color:${garment.color_hex}">${garment.color_hex}</span>`}
            </div>
          </div>
        </div>`;

      if (data.color_pending) {
        setTimeout(() => openColorModal(garment.id), 1000);
      }
      toast('Garment added to your Vault!', 'success');
    } else {
      result.classList.add('error');
      result.innerHTML = `<i class="fas fa-times-circle"></i> ${data.detail || 'Upload failed'}`;
      toast(data.detail || 'Upload failed', 'error');
    }
  } catch (err) {
    hideLoader();
    result.classList.add('error');
    result.innerHTML = `<i class="fas fa-wifi"></i> Cannot reach server. Make sure it's running.`;
    toast('Server not reachable', 'error');
  }
}

// ── Garment Rendering ─────────────────────────────────────────────────────────
function renderGarments() {
  const grid = document.getElementById('garmentGrid');
  const empty = document.getElementById('vaultEmpty');

  if (garments.length === 0) {
    if (empty) empty.style.display = 'block';
    return;
  }
  if (empty) empty.style.display = 'none';

  // Remove existing cards (keep empty state)
  grid.querySelectorAll('.garment-card').forEach(c => c.remove());

  garments.forEach(g => {
    const card = document.createElement('div');
    card.className = 'garment-card';
    card.innerHTML = `
      ${g.color_pending ? '<div class="pending-badge"><i class="fas fa-exclamation"></i> Color?</div>' : ''}
      <div class="garment-img">
        <i class="fas fa-tshirt"></i>
      </div>
      <div class="garment-info">
        <div class="garment-category">${g.category?.replace('_', ' ') || 'Unknown'}</div>
        <div class="garment-name">${g.sub_category || 'Garment'}</div>
        <div class="garment-color">
          <div class="color-dot" style="background:${g.color_pending ? '#888' : g.color_hex}"></div>
          <span>${g.color_pending ? 'Tap to set color' : g.color_hex}</span>
        </div>
      </div>`;
    if (g.color_pending) {
      card.addEventListener('click', () => openColorModal(g.id));
    }
    grid.appendChild(card);
  });
}

// ── Outfit Generation ─────────────────────────────────────────────────────────
async function generateOutfits() {
  showLoader('Generating your outfits...');
  const fakeToken = await getFakeToken();

  try {
    const r = await fetch(`${API}/recommend/outfits`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${fakeToken}`,
      },
      body: JSON.stringify({ user_id: currentUserId }),
    });
    const outfits = await r.json();
    hideLoader();
    renderOutfits(outfits);
  } catch {
    hideLoader();
    toast('Could not reach server', 'error');
    // Show demo outfits
    renderOutfits(getDemoOutfits());
  }
}

function renderOutfits(outfits) {
  const grid = document.getElementById('outfitGrid');
  const empty = document.getElementById('stylistEmpty');
  grid.querySelectorAll('.outfit-card').forEach(c => c.remove());

  if (!outfits || outfits.length === 0) {
    if (empty) empty.style.display = 'block';
    toast('No outfits yet — add garments to your Vault first!', 'info');
    return;
  }
  if (empty) empty.style.display = 'none';

  const colors = [
    ['#667eea','#764ba2'], ['#f093fb','#f5576c'], ['#4facfe','#00f2fe'],
    ['#43e97b','#38f9d7'], ['#fa709a','#fee140'], ['#a18cd1','#fbc2eb'],
    ['#ffecd2','#fcb69f'], ['#ff9a9e','#fecfef'], ['#a1c4fd','#c2e9fb'],
    ['#d4fc79','#96e6a1'],
  ];

  outfits.forEach((outfit, i) => {
    const c1 = colors[i % colors.length];
    const c2 = colors[(i + 3) % colors.length];
    const totalPct = Math.round((outfit.total_score || 0) * 100);
    const trendPct = Math.round((outfit.trend_score || 0) * 100);
    const harmonyPct = Math.round((outfit.harmony_score || 0) * 100);

    const card = document.createElement('div');
    card.className = 'outfit-card';
    card.innerHTML = `
      <div class="outfit-visual">
        <div class="outfit-upper" style="background:linear-gradient(135deg,${c1[0]},${c1[1]})">
          <i class="fas fa-tshirt" style="color:rgba(255,255,255,0.6)"></i>
        </div>
        <div class="outfit-lower" style="background:linear-gradient(135deg,${c2[0]},${c2[1]})">
          <i class="fas fa-socks" style="color:rgba(255,255,255,0.6)"></i>
        </div>
      </div>
      <div class="outfit-meta">
        <div class="outfit-scores">
          <div class="score-chip score-total"><i class="fas fa-fire"></i> ${totalPct}%</div>
          <div class="score-chip score-trend"><i class="fas fa-chart-line"></i> ${trendPct}%</div>
          <div class="score-chip score-harmony"><i class="fas fa-palette"></i> ${harmonyPct}%</div>
        </div>
        <div class="outfit-label">Outfit #${i + 1} · ${totalPct >= 80 ? '🔥 Fire look' : totalPct >= 60 ? '✨ Solid pick' : '👍 Good combo'}</div>
      </div>`;
    grid.appendChild(card);
  });

  toast(`${outfits.length} outfit${outfits.length !== 1 ? 's' : ''} generated!`, 'success');
  animateNumber('statOutfits', outfits.length);
}

function getDemoOutfits() {
  return Array.from({ length: 6 }, (_, i) => ({
    total_score: 0.95 - i * 0.08,
    trend_score: 0.9 - i * 0.1,
    harmony_score: 0.85 - i * 0.05,
  }));
}

// ── Trends ────────────────────────────────────────────────────────────────────
async function loadTrends() {
  const grid = document.getElementById('trendsGrid');
  const staleBadge = document.getElementById('staleBadge');

  try {
    const r = await fetch(`${API}/trends`);
    const data = await r.json();

    if (data.trends_stale) staleBadge.classList.remove('hidden');
    else staleBadge.classList.add('hidden');

    renderTrends(data.trends || []);
  } catch {
    // Show demo trends when server is offline
    renderTrends(getDemoTrends());
    staleBadge.classList.remove('hidden');
  }
}

function renderTrends(trends) {
  const grid = document.getElementById('trendsGrid');
  grid.innerHTML = '';

  if (!trends || trends.length === 0) {
    grid.innerHTML = '<div class="empty-state"><i class="fas fa-globe"></i><p>No trend data available</p></div>';
    return;
  }

  trends.forEach(t => {
    const pct = Math.round((t.score || 0) * 100);
    const card = document.createElement('div');
    card.className = 'trend-card glass-card';
    card.innerHTML = `
      <div class="trend-color-block" style="background:${t.color_hex || '#888'}"></div>
      <div class="trend-info">
        <div class="trend-category">${t.category || 'Fashion'}</div>
        <div class="trend-name">${t.color_name || t.color_hex || 'Trending'}</div>
        <div class="trend-bar-wrap">
          <div class="trend-bar" style="width:0%" data-width="${pct}%"></div>
        </div>
        <div class="trend-score-label">${pct}% trend strength</div>
        <div class="trend-source"><i class="fas fa-signal"></i> ${t.source || 'Global'}</div>
      </div>`;
    grid.appendChild(card);
  });

  // Animate bars
  setTimeout(() => {
    grid.querySelectorAll('.trend-bar').forEach(bar => {
      bar.style.width = bar.dataset.width;
    });
  }, 100);

  animateNumber('statTrends', trends.length);
}

function getDemoTrends() {
  return [
    { category: 'Lower Body - Trousers', color_hex: '#3D5A80', color_name: 'Steel Blue', score: 0.88, source: 'Instagram' },
    { category: 'Upper Torso - Jacket', color_hex: '#C8A96E', color_name: 'Warm Camel', score: 0.76, source: 'Pinterest' },
    { category: 'Upper Torso - T-Shirt', color_hex: '#E8D5B7', color_name: 'Oat Cream', score: 0.65, source: 'TikTok' },
    { category: 'Lower Body - Skirt', color_hex: '#FF6B9D', color_name: 'Hot Pink', score: 0.82, source: 'Vogue' },
    { category: 'Upper Torso - Hoodie', color_hex: '#2D3436', color_name: 'Charcoal', score: 0.71, source: 'Hypebeast' },
    { category: 'Lower Body - Jeans', color_hex: '#74B9FF', color_name: 'Sky Wash', score: 0.79, source: 'WGSN' },
  ];
}

// ── Missing Links ─────────────────────────────────────────────────────────────
async function loadMissingLinks() {
  showLoader('Finding your missing links...');
  const fakeToken = await getFakeToken();

  try {
    const r = await fetch(`${API}/recommend/missing-links`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${fakeToken}`,
      },
      body: JSON.stringify({ user_id: currentUserId }),
    });
    const items = await r.json();
    hideLoader();
    renderMissingLinks(items);
  } catch {
    hideLoader();
    renderMissingLinks(getDemoMissingLinks());
  }
}

function renderMissingLinks(items) {
  const grid = document.getElementById('missingGrid');
  const empty = document.getElementById('shopEmpty');
  grid.querySelectorAll('.missing-card').forEach(c => c.remove());

  if (!items || items.length === 0) {
    if (empty) empty.style.display = 'block';
    toast('No missing links found — add more garments!', 'info');
    return;
  }
  if (empty) empty.style.display = 'none';

  items.forEach(item => {
    const card = document.createElement('div');
    card.className = 'missing-card';
    card.innerHTML = `
      <div class="missing-header">
        <div class="missing-color" style="background:${item.color_hex || '#888'}"></div>
        <div>
          <div class="missing-title">${item.suggested_item || 'Trending Item'}</div>
          <div class="missing-category">${item.category?.replace('_', ' ') || 'Fashion'}</div>
        </div>
      </div>
      <div class="unlock-count">
        <i class="fas fa-unlock"></i>
        Unlocks <strong>${item.unlock_count || 0}</strong> new outfit${item.unlock_count !== 1 ? 's' : ''}
      </div>`;
    grid.appendChild(card);
  });

  toast(`Found ${items.length} missing link${items.length !== 1 ? 's' : ''}!`, 'success');
}

function getDemoMissingLinks() {
  return [
    { suggested_item: 'Steel Blue Trousers', category: 'LOWER_BODY', color_hex: '#3D5A80', unlock_count: 8 },
    { suggested_item: 'Warm Camel Jacket', category: 'UPPER_TORSO', color_hex: '#C8A96E', unlock_count: 6 },
    { suggested_item: 'Hot Pink Skirt', category: 'LOWER_BODY', color_hex: '#FF6B9D', unlock_count: 4 },
  ];
}

// ── Color Correction ──────────────────────────────────────────────────────────
function openColorModal(garmentId) {
  pendingColorGarmentId = garmentId;
  document.getElementById('colorModal').classList.remove('hidden');
}

function closeColorModal() {
  document.getElementById('colorModal').classList.add('hidden');
  pendingColorGarmentId = null;
}

function setupColorPicker() {
  const picker = document.getElementById('colorPicker');
  const display = document.getElementById('colorHexDisplay');
  picker.addEventListener('input', () => {
    display.textContent = picker.value.toUpperCase();
  });
}

function setSwatch(hex) {
  document.getElementById('colorPicker').value = hex;
  document.getElementById('colorHexDisplay').textContent = hex.toUpperCase();
}

async function submitColorCorrection() {
  if (!pendingColorGarmentId) return;
  const hex = document.getElementById('colorPicker').value.toUpperCase();
  const fakeToken = await getFakeToken();

  showLoader('Saving color...');
  try {
    const r = await fetch(`${API}/vision/garments/${pendingColorGarmentId}/color`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${fakeToken}`,
      },
      body: JSON.stringify({ color_hex: hex }),
    });
    hideLoader();
    if (r.ok) {
      const updated = await r.json();
      const idx = garments.findIndex(g => g.id === pendingColorGarmentId);
      if (idx !== -1) {
        garments[idx].color_hex = hex;
        garments[idx].color_pending = false;
      }
      renderGarments();
      closeColorModal();
      toast(`Color updated to ${hex}!`, 'success');
    } else {
      toast('Invalid color format', 'error');
    }
  } catch {
    hideLoader();
    toast('Server not reachable', 'error');
  }
}

// ── Auth Helper (demo token) ──────────────────────────────────────────────────
async function getFakeToken() {
  // For demo: get a token from the server using a test endpoint
  // In production this would be a real Google OAuth token
  try {
    // Try to use a cached token
    if (window._demoToken) return window._demoToken;
    // Generate a simple demo token via the auth service directly
    // Since we don't have real OAuth, we'll use a workaround
    return 'demo-token-placeholder';
  } catch {
    return 'demo-token-placeholder';
  }
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function toast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  const icons = { success: 'fa-check-circle', error: 'fa-times-circle', info: 'fa-info-circle' };
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.innerHTML = `<i class="fas ${icons[type]}"></i><span>${message}</span>`;
  container.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; t.style.transform = 'translateX(100%)'; t.style.transition = '0.3s'; setTimeout(() => t.remove(), 300); }, 3500);
}

// ── Loader ────────────────────────────────────────────────────────────────────
function showLoader(text = 'Loading...') {
  document.getElementById('loaderText').textContent = text;
  document.getElementById('loader').classList.remove('hidden');
}
function hideLoader() {
  document.getElementById('loader').classList.add('hidden');
}

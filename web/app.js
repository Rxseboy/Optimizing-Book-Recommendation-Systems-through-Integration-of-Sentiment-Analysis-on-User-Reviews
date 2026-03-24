/**
 * NovelSense – App Logic
 * Loads pre-exported JSON data and powers the interactive UI.
 */

'use strict';

// ── State
let booksData   = [];
let recsData    = {};
let metricsData = {};
let activeUser  = null;

// ── DOM helpers
const $  = id  => document.getElementById(id);
const $$ = sel => document.querySelectorAll(sel);

// ── Fetch all data in parallel
async function init() {
  try {
    const [books, recs, metrics] = await Promise.all([
      fetch('data/books_metadata.json').then(r => r.json()),
      fetch('data/recommendations.json').then(r => r.json()),
      fetch('data/metrics.json').then(r => r.json()),
    ]);
    booksData   = books;
    recsData    = recs;
    metricsData = metrics;

    applyMetrics(metricsData);
    animateHeroKPI();
    renderCatalog(booksData);
    buildUserChips(Object.keys(recsData));
    animateSentimentBars();
    $('catalog-loader').style.display = 'none';
  } catch (err) {
    console.error('Failed to load data:', err);
    $('catalog-loader').innerHTML =
      `<p style="color:#f87171">⚠ Could not load data. Make sure you run <code>python export_app_data.py</code> first.</p>`;
  }
}

// ════════════════════════════════════════════
//  HERO – animated count-up
// ════════════════════════════════════════════
function applyMetrics(m) {
  if (!m) return;
  // Update Hero KPIs
  const kpis = $$('#heroKPI .kpi-n');
  if (kpis.length >= 4) {
    kpis[0].dataset.target = m.total_reviews;
    kpis[1].dataset.target = m.unique_users;
    kpis[2].dataset.target = m.unique_books;
    kpis[3].dataset.target = (m.knn_accuracy * 100).toFixed(2);
  }

  // Update Metrics Cards
  if ($('mc-acc'))  $('mc-acc').innerHTML  = `${(m.knn_accuracy * 100).toFixed(2)}<span class="mc-unit">%</span>`;
  if ($('mc-f1'))   $('mc-f1').textContent   = m.knn_f1.toFixed(4);
  if ($('mc-sens')) $('mc-sens').textContent = m.knn_sensitivity.toFixed(4);
  if ($('mc-spec')) $('mc-spec').textContent = m.knn_specificity.toFixed(4);
  if ($('mc-rmse')) $('mc-rmse').textContent = m.rmse.toFixed(4);
  if ($('mc-mae'))  $('mc-mae').textContent  = m.mae.toFixed(4);

  // Update Sentiment Distribution
  if (m.sentiment_distribution) {
    const sd = m.sentiment_distribution;
    const fillers = $$('.sent-fill');
    const pcts    = $$('.sent-pct');
    if (fillers.length >= 3 && pcts.length >= 3) {
      fillers[0].dataset.w = sd.positive;
      pcts[0].textContent  = `${sd.positive}%`;
      fillers[1].dataset.w = sd.negative;
      pcts[1].textContent  = `${sd.negative}%`;
      fillers[2].dataset.w = sd.undecided;
      pcts[2].textContent  = `${sd.undecided}%`;
    }
  }
}

function animateHeroKPI() {
  const nodes = $$('.kpi-n');
  nodes.forEach(el => {
    let target = parseFloat(el.dataset.target);
    if (isNaN(target)) return;
    
    const isPct   = el.classList.contains('kpi-pct');
    const isFloat = target % 1 !== 0 || isPct;
    const dur     = 1800;
    const step    = 16;
    const steps   = dur / step;
    let current   = 0;
    const increment = target / steps;
    const timer = setInterval(() => {
      current = Math.min(current + increment, target);
      el.textContent = isFloat
        ? current.toFixed(2)
        : Math.floor(current).toLocaleString();
      if (current >= target) clearInterval(timer);
    }, step);
  });
}

// ════════════════════════════════════════════
//  CATALOG
// ════════════════════════════════════════════
function renderCatalog(books) {
  const grid = $('booksGrid');
  grid.innerHTML = '';
  if (!books.length) {
    grid.innerHTML = '<p style="color:var(--muted);text-align:center;padding:3rem">No books found.</p>';
    return;
  }
  books.forEach((b, i) => {
    const card = document.createElement('div');
    card.className = 'book-card';
    card.style.animationDelay = `${i * 40}ms`;

    const cover   = b.cover_url || 'https://via.placeholder.com/230x340/161625/d4a843?text=No+Cover';
    const rating  = b.rating ? b.rating.toFixed(2) : '–';
    const reviews = b.dataset_review_count ? b.dataset_review_count.toLocaleString() : '–';
    const seriesTag = b.series
      ? `<span class="book-series-tag">${b.series.replace(/The War of Lost Hearts/,'WoLH').replace(/Crowns of Nyaxia/,'CoN')}</span>`
      : '';

    card.innerHTML = `
      <div class="book-cover-wrap">
        <img class="book-cover" src="${cover}" alt="${b.title}" loading="lazy"
             onerror="this.src='https://via.placeholder.com/230x340/161625/d4a843?text=No+Cover'">
        <div class="book-cover-overlay"></div>
        ${seriesTag}
      </div>
      <div class="book-info">
        <h3 class="book-title">${b.title}</h3>
        <div class="book-meta">
          <div class="book-rating"><i class="fa-solid fa-star"></i>${rating}</div>
          <div class="book-reviews">${reviews} reviews</div>
        </div>
      </div>`;

    card.addEventListener('click', () => openModal(b));
    grid.appendChild(card);
  });
}

// Filter
$$('.fbtn').forEach(btn => {
  btn.addEventListener('click', e => {
    $$('.fbtn').forEach(b => b.classList.remove('active'));
    e.currentTarget.classList.add('active');
    const f = e.currentTarget.dataset.filter;
    if (f === 'all') return renderCatalog(booksData);
    if (f === 'standalone') return renderCatalog(booksData.filter(b => !b.series));
    renderCatalog(booksData.filter(b => b.series && b.series.includes(f)));
  });
});

// ════════════════════════════════════════════
//  MODAL
// ════════════════════════════════════════════
function openModal(b) {
  $('mImg').src  = b.cover_url || '';
  $('mLink').href = b.goodreads_url || '#';
  $('mTitle').textContent  = b.title;
  $('mAuthor').textContent = `By ${b.author}`;
  $('mSeries').textContent = b.series || 'Standalone';
  $('mSeries').style.display = b.series ? '' : 'none';

  $('mRating').textContent = b.rating ? `${b.rating.toFixed(2)} ★ (${(b.ratings_count||0).toLocaleString()})` : '–';
  $('mPages').textContent  = b.pages ? `${b.pages} pages` : '– pages';
  $('mPub').textContent    = b.publication_date || '–';

  $('mRevCount').textContent  = (b.dataset_review_count  || 0).toLocaleString();
  $('mReviewers').textContent = (b.dataset_unique_reviewers || 0).toLocaleString();
  $('mDesc').textContent      = b.description || 'No synopsis available.';

  const gWrap = $('mGenres');
  gWrap.innerHTML = (b.genres || []).slice(0, 6)
    .map(g => `<span class="mgr">${g}</span>`).join('');

  $('modal').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  $('modal').classList.remove('open');
  document.body.style.overflow = '';
}
$('modalClose').addEventListener('click', closeModal);
$('modal').addEventListener('click', e => { if (e.target === $('modal')) closeModal(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

// ════════════════════════════════════════════
//  METRICS – sentiment bars
// ════════════════════════════════════════════
function animateSentimentBars() {
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      $$('.sent-fill').forEach(el => {
        el.style.width = el.dataset.w + '%';
      });
      observer.disconnect();
    });
  }, { threshold: 0.3 });
  const section = document.getElementById('metrics');
  if (section) observer.observe(section);
}

// ════════════════════════════════════════════
//  DEMO – user chips + recommendations
// ════════════════════════════════════════════
function buildUserChips(users) {
  const wrap = $('userChips');
  users.forEach(u => {
    const chip = document.createElement('button');
    chip.className = 'u-chip';
    chip.textContent = u;
    chip.addEventListener('click', () => {
      $$('.u-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      loadRecommendations(u);
    });
    wrap.appendChild(chip);
  });
}

// Build a title→book lookup
function bookByTitle(title) {
  return booksData.find(b => b.title === title) || null;
}

function loadRecommendations(username) {
  activeUser = username;
  const recs = recsData[username];
  const panel = $('demoResults');

  if (!recs || !recs.length) {
    panel.innerHTML = `
      <div class="empty-state">
        <i class="fa-solid fa-face-meh"></i>
        <p>No recommendations available for <strong>${username}</strong>.</p>
      </div>`;
    return;
  }

  const listHtml = recs.map((r, i) => {
    const book  = bookByTitle(r.book_name);
    const cover = r.cover_url || (book && book.cover_url) || 'https://via.placeholder.com/52x76/161625/d4a843?text=?';
    const delay = i * 80;

    const pr  = (r.predicted_rating  / 5 * 100).toFixed(1);
    const ss  = (r.sentiment_score   / 5 * 100).toFixed(1);
    const rs  = (r.ranking_score     / 5 * 100).toFixed(1);

    return `
      <div class="rec-card" style="animation-delay:${delay}ms" data-title="${r.book_name}">
        <div class="rec-rank">#${i+1}</div>
        <img class="rec-img" src="${cover}" alt="${r.book_name}"
             onerror="this.src='https://via.placeholder.com/52x76/161625/d4a843?text=?'">
        <div class="rec-info">
          <div class="rec-title">${r.book_name}</div>
          <div class="rec-scores">
            <div class="rec-bar-wrap">
              <span class="rec-bar-lbl">Predicted</span>
              <div class="rec-bar-track"><div class="rec-bar-fill bar-pr" style="width:${pr}%"></div></div>
              <span class="rec-bar-val">${r.predicted_rating.toFixed(2)}</span>
            </div>
            <div class="rec-bar-wrap">
              <span class="rec-bar-lbl">Sentiment</span>
              <div class="rec-bar-track"><div class="rec-bar-fill bar-ss" style="width:${ss}%"></div></div>
              <span class="rec-bar-val">${r.sentiment_score.toFixed(2)}</span>
            </div>
            <div class="rec-bar-wrap">
              <span class="rec-bar-lbl">Final Score</span>
              <div class="rec-bar-track"><div class="rec-bar-fill bar-rs" style="width:${rs}%"></div></div>
              <span class="rec-bar-val">${r.ranking_score.toFixed(2)}</span>
            </div>
          </div>
        </div>
      </div>`;
  }).join('');

  panel.innerHTML = `
    <div class="rec-header">
      <h3>Top Recommendations</h3>
      <span class="rec-user-badge"><i class="fa-solid fa-user"></i> ${username}</span>
    </div>
    <div class="rec-grid">${listHtml}</div>`;

  // make rec cards clickable to open modal
  panel.querySelectorAll('.rec-card').forEach(card => {
    card.style.cursor = 'pointer';
    card.addEventListener('click', () => {
      const title = card.dataset.title;
      const book  = bookByTitle(title);
      if (book) openModal(book);
    });
  });
}

// ════════════════════════════════════════════
//  NAV – scroll shadow + hamburger
// ════════════════════════════════════════════
window.addEventListener('scroll', () => {
  document.getElementById('navbar').classList.toggle('scrolled', window.scrollY > 30);
}, { passive: true });

$('navHamburger').addEventListener('click', () => {
  const nl = document.querySelector('.nav-links');
  nl.style.display = nl.style.display === 'flex' ? 'none' : 'flex';
  nl.style.flexDirection = 'column';
  nl.style.position      = 'absolute';
  nl.style.top           = '60px';
  nl.style.left          = '0';
  nl.style.right         = '0';
  nl.style.background    = '#0f0f1a';
  nl.style.padding       = '1rem 2rem';
  nl.style.borderBottom  = '1px solid rgba(255,255,255,.07)';
  nl.style.gap           = '1.2rem';
});

// ── BOOT
init();

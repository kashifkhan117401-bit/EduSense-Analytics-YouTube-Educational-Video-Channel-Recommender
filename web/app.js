/* ==========================================================================
   MarketSense Analytics - Frontend Interactive Engine & Visual Graphs
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const form = document.getElementById('analyze-form');
  const urlInput = document.getElementById('video-url-input');
  const commentsLimit = document.getElementById('comments-limit');
  const analyzeBtn = document.getElementById('analyze-btn');
  const btnText = analyzeBtn.querySelector('.btn-text');
  const btnLoader = analyzeBtn.querySelector('.btn-loader');

  const loadingState = document.getElementById('loading-state');
  const resultsSection = document.getElementById('results-section');
  const errorBanner = document.getElementById('error-banner');
  const errorText = document.getElementById('error-text');
  const errorCloseBtn = document.getElementById('error-close-btn');

  // API Base URL (handles file:// or localhost)
  const API_BASE = (window.location.protocol === 'file:' || !window.location.port)
    ? 'http://127.0.0.1:5000'
    : '';

  // Chart instances
  let donutChartInstance = null;
  let signalsChartInstance = null;
  let phrasesChartInstance = null;

  // Active data cache for filtering & export
  let currentAnalysisData = null;
  let activeFilter = 'all';

  // ---------------------------------------------------------------------------
  // CORE ANALYSIS
  // ---------------------------------------------------------------------------

  async function executeAnalysis(url) {
    if (!url) return;
    url = url.trim();

    hideError();
    setLoading(true);
    resultsSection.style.display = 'none';

    try {
      const response = await fetch(`${API_BASE}/api/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: url,
          max_comments: parseInt(commentsLimit.value, 10) || 2000
        })
      });

      const data = await response.json().catch(() => null);

      if (!response.ok || !data || data.error) {
        showError((data && data.error)
          ? data.error
          : `HTTP ${response.status}: Failed to analyze video.`);
        setLoading(false);
        return;
      }

      currentAnalysisData = data;
      renderDashboard(data);
      setLoading(false);

      // Smooth scroll to results
      resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

    } catch (err) {
      console.error('Fetch error:', err);
      showError('⚠️ Cannot connect to local server at http://127.0.0.1:5000. Please ensure "python gui_server.py" is running in your terminal.');
      setLoading(false);
    }
  }

  // ---------------------------------------------------------------------------
  // SAMPLE CHIP BUTTONS
  // ---------------------------------------------------------------------------

  document.querySelectorAll('.chip-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const url = btn.getAttribute('data-url') || btn.dataset.url;
      if (url) {
        urlInput.value = url;
        executeAnalysis(url);
      }
    });
  });

  // Error Close Handler
  errorCloseBtn.addEventListener('click', () => {
    errorBanner.style.display = 'none';
  });

  // Form Submit Handler
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const url = urlInput.value.trim();
    if (url) {
      executeAnalysis(url);
    }
  });

  // ---------------------------------------------------------------------------
  // LOADING / ERROR STATE
  // ---------------------------------------------------------------------------

  function setLoading(isLoading) {
    if (isLoading) {
      btnText.style.display = 'none';
      btnLoader.style.display = 'inline-block';
      analyzeBtn.disabled = true;
      loadingState.style.display = 'block';
    } else {
      btnText.style.display = 'inline-block';
      btnLoader.style.display = 'none';
      analyzeBtn.disabled = false;
      loadingState.style.display = 'none';
    }
  }

  function showError(msg) {
    errorText.textContent = msg;
    errorBanner.style.display = 'flex';
  }

  function hideError() {
    errorBanner.style.display = 'none';
  }

  // ---------------------------------------------------------------------------
  // HELPERS
  // ---------------------------------------------------------------------------

  function formatNum(num) {
    return new Intl.NumberFormat('en-US').format(num);
  }

  function formatDate(isoStr) {
    if (!isoStr) return '';
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
    } catch {
      return isoStr;
    }
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // ---------------------------------------------------------------------------
  // MAIN RENDER
  // ---------------------------------------------------------------------------

  function renderDashboard(data) {
    const { video, analysis, warning } = data;

    if (warning) {
      showError(warning);
    }

    // 1. Video Meta
    document.getElementById('video-thumb').src = video.thumbnail_url || 'https://via.placeholder.com/640x360?text=No+Thumbnail';
    document.getElementById('video-yt-link').href = `https://www.youtube.com/watch?v=${video.video_id}`;
    document.getElementById('video-title').textContent = video.title;
    document.getElementById('channel-name').textContent = video.channel_title;
    document.getElementById('upload-date').textContent = formatDate(video.published_at);
    document.getElementById('video-desc').textContent = video.description || 'No description provided.';
    document.getElementById('view-count').textContent = formatNum(video.view_count);
    document.getElementById('like-count').textContent = formatNum(video.like_count);
    document.getElementById('comment-count').textContent = formatNum(video.comment_count);
    document.getElementById('analyzed-count').textContent = formatNum(analysis.total_comments);

    // 2. KPIs & Radial Score
    const mktgScore = analysis.product_score ?? analysis.marketing_score ?? analysis.edu_score ?? 0;
    animateScore(mktgScore);

    // Confidence Badge
    const confBadge = document.getElementById('confidence-badge');
    confBadge.textContent = `${analysis.confidence} Confidence`;
    confBadge.className = 'confidence-badge ' + (
      analysis.confidence === 'High' ? 'confidence-high' :
        analysis.confidence === 'Medium' ? 'confidence-med' : 'confidence-low'
    );

    // Score Caption
    const captionEl = document.getElementById('score-caption');
    if (mktgScore >= 75) {
      captionEl.textContent = '🌟 Exceptional product reception! High purchase intent, strong viewer praise, and minimal complaints.';
    } else if (mktgScore >= 60) {
      captionEl.textContent = '👍 Favorable product reception with generally positive consumer feedback.';
    } else {
      captionEl.textContent = '⚠️ Noticeable consumer complaints, friction, or skepticism flagged in comments.';
    }

    // Like-Weighted Sentiment
    const lwSentiment = analysis.lw_sentiment;
    const sentNumEl = document.getElementById('sentiment-val-num');
    sentNumEl.textContent = (lwSentiment > 0 ? '+' : '') + lwSentiment.toFixed(2);

    const sentIndicator = document.getElementById('sentiment-indicator');
    if (lwSentiment >= 0.15) {
      sentIndicator.textContent = 'Positive';
      sentIndicator.className = 'sentiment-indicator confidence-high';
    } else if (lwSentiment <= -0.1) {
      sentIndicator.textContent = 'Critical';
      sentIndicator.className = 'sentiment-indicator confidence-low';
    } else {
      sentIndicator.textContent = 'Neutral';
      sentIndicator.className = 'sentiment-indicator confidence-med';
    }

    // Sentiment Bar Fill (maps [-1, 1] to [0%, 100%])
    const sentPct = Math.max(0, Math.min(100, ((lwSentiment + 1) / 2) * 100));
    document.getElementById('sentiment-bar-fill').style.width = `${sentPct}%`;

    // Purchase Intent & Friction Signals
    const intentPct   = analysis.signals_summary.intent_pct   ?? analysis.signals_summary.helped_pct   ?? 0;
    const intentCount = analysis.signals_summary.intent_count ?? analysis.signals_summary.helped_count ?? 0;
    const frictionPct   = analysis.signals_summary.friction_pct   ?? analysis.signals_summary.confused_pct   ?? 0;
    const frictionCount = analysis.signals_summary.friction_count ?? analysis.signals_summary.confused_count ?? 0;

    document.getElementById('helped-pct-num').textContent   = `${intentPct}%`;
    document.getElementById('helped-count-num').textContent = `${intentCount} of ${analysis.total_comments}`;

    document.getElementById('confused-pct-num').textContent   = `${frictionPct}%`;
    document.getElementById('confused-count-num').textContent = `${frictionCount} of ${analysis.total_comments}`;

    // 3. Visual Graphs
    renderDonutChart(analysis.sentiment_summary);
    renderSignalsChart({ intent_pct: intentPct, friction_pct: frictionPct });
    renderPhrasesChart(analysis.top_phrases);

    // 4. Evidence Lists & Tabs
    const topIntentList   = analysis.top_intent   || analysis.top_helped   || [];
    const topFrictionList = analysis.top_friction || analysis.top_confused || [];
    renderEvidenceList(topIntentList,   'helped-comments-list',  'card-helped');
    renderEvidenceList(topFrictionList, 'confused-comments-list','card-confused');

    document.getElementById('tab-helped-count').textContent  = topIntentList.length;
    document.getElementById('tab-confused-count').textContent = topFrictionList.length;
    document.getElementById('tab-all-count').textContent      = analysis.comments.length;

    renderAllCommentsTable(analysis.comments);

    // 5. Follower vs Non-Follower breakdown
    renderFollowerAnalysis(analysis.follower_analysis);

    // Show section
    resultsSection.style.display = 'block';
  }

  // ---------------------------------------------------------------------------
  // ANIMATED SCORE COUNTER
  // ---------------------------------------------------------------------------

  function animateScore(targetScore) {
    const numEl    = document.getElementById('edu-score-num');
    const circleEl = document.querySelector('.score-circle');
    let current = 0;
    const duration = 1200;
    const stepTime = 20;
    const steps = duration / stepTime;
    const increment = targetScore / steps;

    let color = '#10b981';
    if (targetScore < 50)      color = '#f43f5e';
    else if (targetScore < 65) color = '#f59e0b';
    else if (targetScore < 80) color = '#6366f1';

    circleEl.style.borderColor = color;
    circleEl.style.boxShadow   = `0 0 25px ${color}55`;

    const timer = setInterval(() => {
      current += increment;
      if (current >= targetScore) {
        current = targetScore;
        clearInterval(timer);
      }
      numEl.textContent = current.toFixed(1);
    }, stepTime);
  }

  // ---------------------------------------------------------------------------
  // CHARTS (Chart.js)
  // ---------------------------------------------------------------------------

  function renderDonutChart(summary) {
    const ctx = document.getElementById('sentiment-donut-chart').getContext('2d');
    if (donutChartInstance) donutChartInstance.destroy();

    const dataValues = [summary.positive_count, summary.neutral_count, summary.negative_count];
    const hasData = dataValues.some(v => v > 0);

    donutChartInstance = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['Positive', 'Neutral', 'Negative'],
        datasets: [{
          data: hasData ? dataValues : [1, 1, 1],
          backgroundColor: ['#10b981', '#f59e0b', '#f43f5e'],
          borderColor: '#0f172a',
          borderWidth: 4,
          hoverOffset: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '72%',
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (context) => {
                const total = summary.positive_count + summary.neutral_count + summary.negative_count;
                const val = context.raw;
                const pct = total > 0 ? ((val / total) * 100).toFixed(1) : 0;
                return ` ${context.label}: ${val} (${pct}%)`;
              }
            }
          }
        }
      }
    });

    const legendEl = document.getElementById('sentiment-legend');
    legendEl.innerHTML = `
      <div class="legend-item"><span class="legend-color" style="background:#10b981"></span> Positive: ${summary.positive_pct}%</div>
      <div class="legend-item"><span class="legend-color" style="background:#f59e0b"></span> Neutral: ${summary.neutral_pct}%</div>
      <div class="legend-item"><span class="legend-color" style="background:#f43f5e"></span> Negative: ${summary.negative_pct}%</div>
    `;
  }

  function renderSignalsChart(signals) {
    const ctx = document.getElementById('signals-bar-chart').getContext('2d');
    if (signalsChartInstance) signalsChartInstance.destroy();

    const intentVal   = parseFloat(signals.intent_pct   ?? signals.helped_pct   ?? 0) || 0;
    const frictionVal = parseFloat(signals.friction_pct ?? signals.confused_pct ?? 0) || 0;
    const rawMax = Math.max(intentVal, frictionVal);
    const maxVal = isNaN(rawMax) ? 100 : Math.max(50, Math.ceil(rawMax / 10) * 10 + 10);

    signalsChartInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: ['Purchase Intent & Praise', 'Complaints & Friction'],
        datasets: [{
          label: 'Percentage of Comments',
          data: [intentVal, frictionVal],
          backgroundColor: ['rgba(16, 185, 129, 0.85)', 'rgba(244, 63, 94, 0.85)'],
          borderColor: ['#10b981', '#f43f5e'],
          borderWidth: 2,
          borderRadius: 8,
          barThickness: 42
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: { label: (ctx) => ` ${ctx.raw}% of analyzed comments` }
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            max: maxVal,
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: { color: '#94a3b8', callback: (val) => `${val}%` }
          },
          x: {
            grid: { display: false },
            ticks: { color: '#f8fafc', font: { weight: '600' } }
          }
        }
      }
    });
  }

  function renderPhrasesChart(phrases) {
    const ctx = document.getElementById('phrases-horizontal-chart').getContext('2d');
    if (phrasesChartInstance) phrasesChartInstance.destroy();

    const labels = phrases.length > 0 ? phrases.map(p => `"${p.phrase}"`) : ['No explicit signals'];
    const counts = phrases.length > 0 ? phrases.map(p => p.count) : [0];

    phrasesChartInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Occurrences in Comments',
          data: counts,
          backgroundColor: 'rgba(99, 102, 241, 0.85)',
          borderColor: '#818cf8',
          borderWidth: 1.5,
          borderRadius: 6,
          barThickness: 20
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: { label: (ctx) => ` Found in ${ctx.raw} comments` }
          }
        },
        scales: {
          x: {
            beginAtZero: true,
            ticks: { precision: 0, color: '#94a3b8' },
            grid: { color: 'rgba(255, 255, 255, 0.05)' }
          },
          y: {
            grid: { display: false },
            ticks: { color: '#e2e8f0', font: { size: 12 } }
          }
        }
      }
    });
  }

  // ---------------------------------------------------------------------------
  // FOLLOWER vs NON-FOLLOWER ANALYSIS PANEL
  // ---------------------------------------------------------------------------

  function renderFollowerAnalysis(followerAnalysis) {
    if (!followerAnalysis) return;
    const panel = document.getElementById('follower-analysis-panel');
    if (!panel) return;

    panel.style.display = 'block';

    const { followers, non_followers, follower_count, non_follower_count } = followerAnalysis;
    const totalForPercent = (follower_count + non_follower_count) || 1;
    const followerPct    = ((follower_count     / totalForPercent) * 100).toFixed(1);
    const nonFollowerPct = ((non_follower_count / totalForPercent) * 100).toFixed(1);

    function segmentBlock(title, icon, accentColor, stats, count, pct) {
      const intentPct   = stats.signals_summary?.intent_pct   ?? stats.signals_summary?.helped_pct   ?? 0;
      const frictionPct = stats.signals_summary?.friction_pct ?? stats.signals_summary?.confused_pct ?? 0;
      const posPct  = stats.sentiment_summary?.positive_pct ?? 0;
      const negPct  = stats.sentiment_summary?.negative_pct ?? 0;
      const scoreVal = stats.product_score ?? stats.marketing_score ?? stats.edu_score ?? 0;
      const conf    = stats.confidence ?? 'Low';

      return `
        <div style="flex:1; min-width:260px; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08);
                    border-radius:14px; padding:22px; position:relative; overflow:hidden;">
          <div style="position:absolute;top:0;left:0;right:0;height:3px;background:${accentColor};"></div>
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px;">
            <span style="font-size:1.6rem;">${icon}</span>
            <div>
              <div style="font-size:1rem;font-weight:700;color:#f8fafc;">${title}</div>
              <div style="font-size:0.78rem;color:#94a3b8;">${count} comments &nbsp;·&nbsp; ${pct}% of total</div>
            </div>
          </div>
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">
            <span style="font-size:0.8rem;color:#94a3b8;">Product Score</span>
            <span style="font-size:1.4rem;font-weight:800;color:${accentColor};">${scoreVal}</span>
          </div>
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">
            <span style="font-size:0.8rem;color:#94a3b8;">Confidence</span>
            <span class="confidence-badge confidence-${conf.toLowerCase()}">${conf}</span>
          </div>
          <div style="margin-bottom:10px;">
            <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
              <span style="font-size:0.78rem;color:#94a3b8;">Positive</span>
              <span style="font-size:0.78rem;color:#10b981;font-weight:600;">${posPct}%</span>
            </div>
            <div style="height:6px;background:rgba(255,255,255,0.07);border-radius:3px;overflow:hidden;">
              <div style="width:${posPct}%;height:100%;background:#10b981;border-radius:3px;transition:width 0.6s ease;"></div>
            </div>
          </div>
          <div style="margin-bottom:10px;">
            <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
              <span style="font-size:0.78rem;color:#94a3b8;">Negative</span>
              <span style="font-size:0.78rem;color:#f43f5e;font-weight:600;">${negPct}%</span>
            </div>
            <div style="height:6px;background:rgba(255,255,255,0.07);border-radius:3px;overflow:hidden;">
              <div style="width:${negPct}%;height:100%;background:#f43f5e;border-radius:3px;transition:width 0.6s ease;"></div>
            </div>
          </div>
          <div style="display:flex;gap:12px;margin-top:14px;">
            <div style="flex:1;background:rgba(16,185,129,0.1);border-radius:8px;padding:10px;text-align:center;">
              <div style="font-size:1.1rem;font-weight:700;color:#10b981;">${intentPct}%</div>
              <div style="font-size:0.7rem;color:#94a3b8;">Purchase Intent</div>
            </div>
            <div style="flex:1;background:rgba(244,63,94,0.1);border-radius:8px;padding:10px;text-align:center;">
              <div style="font-size:1.1rem;font-weight:700;color:#f43f5e;">${frictionPct}%</div>
              <div style="font-size:0.7rem;color:#94a3b8;">Ad Friction</div>
            </div>
          </div>
        </div>
      `;
    }

    panel.innerHTML = `
      <div style="margin-bottom:20px;">
        <h2 style="font-size:1.15rem;font-weight:700;color:#f8fafc;margin:0 0 4px;">
          👥 Brand Follower vs Casual Prospect Breakdown
        </h2>
        <p style="font-size:0.8rem;color:#64748b;margin:0;">
          Proxy-based segmentation. <strong>Brand Followers (Proxy)</strong> = commenters who posted multiple times
          or received ≥5 likes (likely active subscribers/advocates). <strong>Casual Prospects</strong> = one-time or casual viewers.
          YouTube API does not expose direct subscriber status per comment.
        </p>
      </div>
      <div style="display:flex;gap:16px;flex-wrap:wrap;">
        ${segmentBlock('Brand Followers (Proxy)', '🌟', '#6366f1', followers, follower_count, followerPct)}
        ${segmentBlock('Casual Prospects / Viewers', '👁️', '#f59e0b', non_followers, non_follower_count, nonFollowerPct)}
      </div>
      <div style="margin-top:20px;">
        <div style="display:flex;justify-content:space-between;margin-bottom:6px;font-size:0.8rem;color:#94a3b8;">
          <span>🌟 Brand Followers ${followerPct}%</span>
          <span>👁️ Casual Prospects ${nonFollowerPct}%</span>
        </div>
        <div style="height:10px;background:rgba(255,255,255,0.07);border-radius:5px;overflow:hidden;display:flex;">
          <div style="width:${followerPct}%;background:linear-gradient(90deg,#6366f1,#818cf8);transition:width 0.8s ease;"></div>
          <div style="flex:1;background:linear-gradient(90deg,#f59e0b,#fbbf24);"></div>
        </div>
      </div>
    `;
  }

  // ---------------------------------------------------------------------------
  // EVIDENCE LIST RENDERING
  // ---------------------------------------------------------------------------

  function renderEvidenceList(comments, containerId, extraClass) {
    const container = document.getElementById(containerId);
    if (!comments || comments.length === 0) {
      container.innerHTML = `
        <div style="text-align:center; padding:30px 10px; color:#64748b;">
          No flagged comments found in this category.
        </div>
      `;
      return;
    }

    container.innerHTML = comments.map(c => {
      const phrases = [...(c.matched_helped || []), ...(c.matched_confused || [])];
      return `
        <div class="comment-evidence-card ${extraClass}">
          <div class="comment-evidence-top">
            <div class="comment-author-box">
              <img src="${c.author_avatar || 'https://via.placeholder.com/28'}" alt="${escapeHtml(c.author)}" class="author-avatar" onerror="this.src='https://via.placeholder.com/28'">
              <span class="author-name">${escapeHtml(c.author)}</span>
            </div>
            <div class="comment-badges-box">
              <span class="like-badge">👍 ${formatNum(c.likes)}</span>
              <span class="sentiment-pill ${c.sentiment_label}">${c.sentiment_label} (${c.sentiment_score > 0 ? '+' : ''}${c.sentiment_score})</span>
            </div>
          </div>
          <p class="comment-body">${escapeHtml(c.text)}</p>
          ${phrases.length > 0 ? `
            <div class="matched-pills-row">
              ${phrases.map(p => `<span class="phrase-pill">"${escapeHtml(p)}"</span>`).join('')}
            </div>
          ` : ''}
        </div>
      `;
    }).join('');
  }

  // ---------------------------------------------------------------------------
  // ALL COMMENTS TABLE & FILTERING
  // ---------------------------------------------------------------------------

  const filterInput = document.getElementById('comment-filter-input');
  const filterPills = document.querySelectorAll('.filter-pill');

  filterInput.addEventListener('input', () => {
    if (currentAnalysisData) filterAndRenderComments();
  });

  filterPills.forEach(pill => {
    pill.addEventListener('click', () => {
      filterPills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      activeFilter = pill.dataset.filter;
      if (currentAnalysisData) filterAndRenderComments();
    });
  });

  function filterAndRenderComments() {
    if (!currentAnalysisData) return;
    const query = filterInput.value.toLowerCase().trim();
    let filtered = currentAnalysisData.analysis.comments;

    if (activeFilter === 'positive') {
      filtered = filtered.filter(c => c.sentiment_label === 'positive');
    } else if (activeFilter === 'neutral') {
      filtered = filtered.filter(c => c.sentiment_label === 'neutral');
    } else if (activeFilter === 'negative') {
      filtered = filtered.filter(c => c.sentiment_label === 'negative');
    } else if (activeFilter === 'intent' || activeFilter === 'helped') {
      filtered = filtered.filter(c => c.is_intent || c.is_helped);
    } else if (activeFilter === 'friction' || activeFilter === 'confused') {
      filtered = filtered.filter(c => c.is_friction || c.is_confused);
    } else if (activeFilter === 'followers') {
      filtered = filtered.filter(c => c.audience_segment === 'follower');
    } else if (activeFilter === 'non_followers') {
      filtered = filtered.filter(c => c.audience_segment === 'non_follower');
    }

    if (query) {
      filtered = filtered.filter(c =>
        c.text.toLowerCase().includes(query) ||
        c.author.toLowerCase().includes(query)
      );
    }

    renderAllCommentsTable(filtered);
  }

  function renderAllCommentsTable(comments) {
    const tbody = document.getElementById('all-comments-tbody');
    if (!comments || comments.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6" style="text-align:center; padding:30px; color:#64748b;">
            No matching comments found.
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = comments.map(c => {
      const signals = [];
      if (c.is_intent   || c.is_helped)   signals.push('<span class="icon-tag green">🛒 Intent</span>');
      if (c.is_friction || c.is_confused) signals.push('<span class="icon-tag rose">⚠️ Friction</span>');

      const segBadge = c.audience_segment === 'follower'
        ? '<span class="icon-tag" style="background:rgba(99,102,241,0.18);color:#818cf8;border:1px solid rgba(99,102,241,0.3);">🌟 Follower</span>'
        : '<span class="icon-tag" style="background:rgba(245,158,11,0.12);color:#fbbf24;border:1px solid rgba(245,158,11,0.3);">👁️ Prospect</span>';

      return `
        <tr>
          <td><strong>👍 ${formatNum(c.likes)}</strong></td>
          <td>
            <div style="display:flex; align-items:center; gap:8px;">
              <img src="${c.author_avatar || 'https://via.placeholder.com/20'}" class="author-avatar" style="width:20px;height:20px;" onerror="this.src='https://via.placeholder.com/20'">
              <span style="font-size:0.82rem;font-weight:600;">${escapeHtml(c.author)}</span>
            </div>
          </td>
          <td><span class="sentiment-pill ${c.sentiment_label}">${c.sentiment_label}</span></td>
          <td>${segBadge}</td>
          <td>${signals.join(' ') || '<span style="color:#64748b;">-</span>'}</td>
          <td style="max-width:440px; word-break:break-word;">${escapeHtml(c.text)}</td>
        </tr>
      `;
    }).join('');
  }

  // ---------------------------------------------------------------------------
  // TABS CONTROLLER
  // ---------------------------------------------------------------------------

  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const targetPane = document.getElementById(btn.dataset.tab);
      if (targetPane) targetPane.classList.add('active');
    });
  });

  // ---------------------------------------------------------------------------
  // CSV EXPORT
  // ---------------------------------------------------------------------------

  document.getElementById('export-csv-btn').addEventListener('click', () => {
    if (!currentAnalysisData || !currentAnalysisData.analysis.comments.length) {
      alert('No data available to export.');
      return;
    }

    const videoTitle = currentAnalysisData.video.title
      .replace(/[^\w\s-]/g, '').trim().substring(0, 30);
    const comments = currentAnalysisData.analysis.comments;

    const headers = [
      'Comment ID', 'Author', 'Likes', 'Published At',
      'Sentiment Label', 'Sentiment Score',
      'Is Purchase Intent', 'Is Ad Friction', 'Audience Segment', 'Comment Text'
    ];

    const rows = comments.map(c => [
      c.id,
      `"${(c.author || '').replace(/"/g, '""')}"`,
      c.likes,
      c.published_at,
      c.sentiment_label,
      c.sentiment_score,
      (c.is_intent || c.is_helped)   ? 'TRUE' : 'FALSE',
      (c.is_friction || c.is_confused) ? 'TRUE' : 'FALSE',
      c.audience_segment || 'non_follower',
      `"${(c.text || '').replace(/"/g, '""')}"`
    ]);

    const csvContent = 'data:text/csv;charset=utf-8,'
      + [headers.join(','), ...rows.map(e => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `${videoTitle || 'marketing_review'}_sentiment_analysis.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  });

}); // END DOMContentLoaded

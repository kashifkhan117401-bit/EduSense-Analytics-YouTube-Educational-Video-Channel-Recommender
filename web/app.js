/* ==========================================================================
   EduSense Analytics - Frontend Interactive Engine & Visual Graphs
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

  // Chart instances
  let donutChartInstance = null;
  let signalsChartInstance = null;
  let phrasesChartInstance = null;

  // Active data cache for filtering & export
  let currentAnalysisData = null;
  let activeFilter = 'all';

  // Sample Chips Click Handlers
  document.querySelectorAll('.chip-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      urlInput.value = btn.dataset.url;
      form.dispatchEvent(new Event('submit'));
    });
  });

  // Error Close Handler
  errorCloseBtn.addEventListener('click', () => {
    errorBanner.style.display = 'none';
  });

  // Form Submit Handler
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const url = urlInput.value.trim();
    if (!url) return;

    hideError();
    setLoading(true);
    resultsSection.style.display = 'none';

    try {
      const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: url,
          max_comments: parseInt(commentsLimit.value, 10) || 100
        })
      });

      const data = await response.json();

      if (!response.ok || data.error) {
        showError(data.error || 'Failed to analyze video. Please verify the link.');
        setLoading(false);
        return;
      }

      currentAnalysisData = data;
      renderDashboard(data);
      setLoading(false);

      // Smooth scroll to results
      resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

    } catch (err) {
      console.error(err);
      showError('Network error connecting to local analytics server.');
      setLoading(false);
    }
  });

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

  // Number Formatter
  function formatNum(num) {
    return new Intl.NumberFormat('en-US').format(num);
  }

  // Format ISO Date
  function formatDate(isoStr) {
    if (!isoStr) return '';
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
    } catch {
      return isoStr;
    }
  }

  // Main Render Function
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
    animateScore(analysis.edu_score);
    
    // Confidence Badge
    const confBadge = document.getElementById('confidence-badge');
    confBadge.textContent = `${analysis.confidence} Confidence`;
    confBadge.className = 'confidence-badge ' + (
      analysis.confidence === 'High' ? 'confidence-high' :
      analysis.confidence === 'Medium' ? 'confidence-med' : 'confidence-low'
    );

    // Score Caption
    const captionEl = document.getElementById('score-caption');
    if (analysis.edu_score >= 75) {
      captionEl.textContent = '🌟 Excellent viewer reception and high concept clarity.';
    } else if (analysis.edu_score >= 60) {
      captionEl.textContent = '👍 Favorable response with constructive comments.';
    } else {
      captionEl.textContent = '⚠️ Mixed response or noticeable confusion flagged in comments.';
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

    // Helped Me & Confused Signals
    document.getElementById('helped-pct-num').textContent = `${analysis.signals_summary.helped_pct}%`;
    document.getElementById('helped-count-num').textContent = `${analysis.signals_summary.helped_count} of ${analysis.total_comments}`;

    document.getElementById('confused-pct-num').textContent = `${analysis.signals_summary.confused_pct}%`;
    document.getElementById('confused-count-num').textContent = `${analysis.signals_summary.confused_count} of ${analysis.total_comments}`;

    // 3. Render Visual Graphs
    renderDonutChart(analysis.sentiment_summary);
    renderSignalsChart(analysis.signals_summary);
    renderPhrasesChart(analysis.top_phrases);

    // 4. Render Evidence Lists & Tabs
    renderEvidenceList(analysis.top_helped, 'helped-comments-list', 'card-helped');
    renderEvidenceList(analysis.top_confused, 'confused-comments-list', 'card-confused');
    
    document.getElementById('tab-helped-count').textContent = analysis.top_helped.length;
    document.getElementById('tab-confused-count').textContent = analysis.top_confused.length;
    document.getElementById('tab-all-count').textContent = analysis.comments.length;

    renderAllCommentsTable(analysis.comments);

    // Show section
    resultsSection.style.display = 'block';
  }

  // Smooth counter animation for Education Score
  function animateScore(targetScore) {
    const numEl = document.getElementById('edu-score-num');
    const circleEl = document.querySelector('.score-circle');
    let current = 0;
    const duration = 1200;
    const stepTime = 20;
    const steps = duration / stepTime;
    const increment = targetScore / steps;

    // Color tone
    let color = '#10b981';
    if (targetScore < 50) color = '#f43f5e';
    else if (targetScore < 65) color = '#f59e0b';
    else if (targetScore < 80) color = '#6366f1';
    circleEl.style.borderColor = color;
    circleEl.style.boxShadow = `0 0 25px ${color}55`;

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
          backgroundColor: [
            '#10b981', // Emerald
            '#f59e0b', // Amber
            '#f43f5e'  // Coral Rose
          ],
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

    // Custom Legend
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

    signalsChartInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: ['Helped Me (Comprehension)', 'Confused (Friction/Doubts)'],
        datasets: [{
          label: 'Percentage of Comments',
          data: [signals.helped_pct, signals.confused_pct],
          backgroundColor: [
            'rgba(16, 185, 129, 0.85)',
            'rgba(244, 63, 94, 0.85)'
          ],
          borderColor: [
            '#10b981',
            '#f43f5e'
          ],
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
            callbacks: {
              label: (ctx) => ` ${ctx.raw}% of analyzed comments`
            }
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            max: Math.max(50, Math.ceil(Math.max(signals.helped_pct, signals.confused_pct) / 10) * 10 + 10),
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: {
              color: '#94a3b8',
              callback: (val) => `${val}%`
            }
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
        labels: labels,
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
            callbacks: {
              label: (ctx) => ` Found in ${ctx.raw} comments`
            }
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
    if (currentAnalysisData) {
      filterAndRenderComments();
    }
  });

  filterPills.forEach(pill => {
    pill.addEventListener('click', () => {
      filterPills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      activeFilter = pill.dataset.filter;
      if (currentAnalysisData) {
        filterAndRenderComments();
      }
    });
  });

  function filterAndRenderComments() {
    if (!currentAnalysisData) return;
    const query = filterInput.value.toLowerCase().trim();
    let filtered = currentAnalysisData.analysis.comments;

    // Filter by category
    if (activeFilter === 'positive') {
      filtered = filtered.filter(c => c.sentiment_label === 'positive');
    } else if (activeFilter === 'neutral') {
      filtered = filtered.filter(c => c.sentiment_label === 'neutral');
    } else if (activeFilter === 'negative') {
      filtered = filtered.filter(c => c.sentiment_label === 'negative');
    } else if (activeFilter === 'helped') {
      filtered = filtered.filter(c => c.is_helped);
    } else if (activeFilter === 'confused') {
      filtered = filtered.filter(c => c.is_confused);
    }

    // Filter by text / author query
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
          <td colspan="5" style="text-align:center; padding:30px; color:#64748b;">
            No matching comments found.
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = comments.map(c => {
      const signals = [];
      if (c.is_helped) signals.push('<span class="icon-tag green">Helped Me</span>');
      if (c.is_confused) signals.push('<span class="icon-tag rose">Confused</span>');

      return `
        <tr>
          <td><strong>👍 ${formatNum(c.likes)}</strong></td>
          <td>
            <div style="display:flex; align-items:center; gap:8px;">
              <img src="${c.author_avatar || 'https://via.placeholder.com/20'}" class="author-avatar" style="width:20px;height:20px;" onerror="this.src='https://via.placeholder.com/20'">
              <span style="font-size:0.82rem;font-weight:600;">${escapeHtml(c.author)}</span>
            </div>
          </td>
          <td>
            <span class="sentiment-pill ${c.sentiment_label}">${c.sentiment_label}</span>
          </td>
          <td>${signals.join(' ') || '<span style="color:#64748b;">-</span>'}</td>
          <td style="max-width:480px; word-break:break-word;">${escapeHtml(c.text)}</td>
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
      const targetId = btn.dataset.tab;
      const targetPane = document.getElementById(targetId);
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

    const videoTitle = currentAnalysisData.video.title.replace(/[^\w\s-]/g, '').trim().substring(0, 30);
    const comments = currentAnalysisData.analysis.comments;
    
    const headers = ['Comment ID', 'Author', 'Likes', 'Published At', 'Sentiment Label', 'Sentiment Score', 'Is Helped', 'Is Confused', 'Comment Text'];
    
    const rows = comments.map(c => [
      c.id,
      `"${c.author.replace(/"/g, '""')}"`,
      c.likes,
      c.published_at,
      c.sentiment_label,
      c.sentiment_score,
      c.is_helped ? 'TRUE' : 'FALSE',
      c.is_confused ? 'TRUE' : 'FALSE',
      `"${c.text.replace(/"/g, '""')}"`
    ]);

    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map(e => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `${videoTitle || 'youtube'}_sentiment_analysis.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  });

  // Utility HTML Escape
  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
});

/* ============================================================
   CodeSathi AI — Main JavaScript
   ============================================================ */

document.addEventListener('DOMContentLoaded', function () {

  /* ---- Sidebar toggle (desktop) ---- */
  const sidebar = document.getElementById('sidebar');
  const mainContent = document.getElementById('mainContent');
  const sidebarToggle = document.getElementById('sidebarToggle');
  const mobileSidebarToggle = document.getElementById('mobileSidebarToggle');
  const sidebarOverlay = document.getElementById('sidebarOverlay');

  if (sidebarToggle) {
    sidebarToggle.addEventListener('click', function () {
      sidebar.classList.toggle('collapsed');
      mainContent.classList.toggle('sidebar-collapsed');
    });
  }

  // Mobile sidebar
  function openSidebar() {
    sidebar.classList.add('open');
    sidebarOverlay.classList.add('show');
    document.body.style.overflow = 'hidden';
  }

  function closeSidebar() {
    sidebar.classList.remove('open');
    sidebarOverlay.classList.remove('show');
    document.body.style.overflow = '';
  }

  if (mobileSidebarToggle) {
    mobileSidebarToggle.addEventListener('click', openSidebar);
  }

  if (sidebarOverlay) {
    sidebarOverlay.addEventListener('click', closeSidebar);
  }

  /* ---- Syntax Highlighting ---- */
  if (typeof hljs !== 'undefined') {
    document.querySelectorAll('pre code').forEach(function (block) {
      hljs.highlightElement(block);
    });
  }

  /* ---- Copy Code Buttons ---- */
  document.querySelectorAll('.copy-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const target = btn.closest('.code-block-wrapper');
      const code = target ? target.querySelector('code') : null;
      if (!code) return;
      navigator.clipboard.writeText(code.textContent).then(function () {
        btn.textContent = '✓ Copied!';
        btn.classList.add('copied');
        setTimeout(function () {
          btn.textContent = 'Copy';
          btn.classList.remove('copied');
        }, 2000);
      });
    });
  });

  /* ---- Loading Overlay ---- */
  window.showLoading = function (msg) {
    let overlay = document.getElementById('loadingOverlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'loadingOverlay';
      overlay.className = 'loading-overlay';
      overlay.innerHTML = `
        <div class="loading-spinner"></div>
        <div class="loading-text" id="loadingMsg">Processing…</div>
      `;
      document.body.appendChild(overlay);
    }
    document.getElementById('loadingMsg').textContent = msg || 'Processing…';
    overlay.classList.add('show');
  };

  window.hideLoading = function () {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) overlay.classList.remove('show');
  };

  /* ---- Form submit with loading ---- */
  document.querySelectorAll('form[data-loading]').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      const btn = form.querySelector('[type=submit]');
      if (btn) {
        btn.disabled = true;
        const original = btn.innerHTML;
        btn.innerHTML = '<span class="spinner-sm"></span> ' + (btn.dataset.loadingText || 'Processing…');
        // Re-enable after 30s safety timeout
        setTimeout(function () { btn.disabled = false; btn.innerHTML = original; }, 30000);
      }
      window.showLoading(form.dataset.loading || 'Processing…');
    });
  });

  /* ---- AJAX helper ---- */
  window.csrfToken = function () {
    const cookie = document.cookie.split(';').find(c => c.trim().startsWith('csrftoken='));
    return cookie ? cookie.split('=')[1].trim() : '';
  };

  window.postJSON = async function (url, data) {
    const body = new FormData();
    Object.entries(data).forEach(([k, v]) => body.append(k, v));
    body.append('csrfmiddlewaretoken', window.csrfToken());
    const resp = await fetch(url, { method: 'POST', body });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ error: 'Request failed' }));
      throw new Error(err.error || 'Request failed');
    }
    return resp.json();
  };

  /* ---- Toast notification ---- */
  window.showToast = function (msg, type) {
    type = type || 'info';
    const colorMap = { info: 'bg-info', success: 'bg-success', error: 'bg-danger', warning: 'bg-warning' };
    const toastContainer = document.getElementById('toastContainer') || createToastContainer();
    const div = document.createElement('div');
    div.className = 'toast align-items-center text-white border-0 show ' + (colorMap[type] || 'bg-info');
    div.innerHTML = `
      <div class="d-flex">
        <div class="toast-body">${msg}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
      </div>`;
    toastContainer.appendChild(div);
    setTimeout(function () { div.remove(); }, 5000);
  };

  function createToastContainer() {
    const c = document.createElement('div');
    c.id = 'toastContainer';
    c.style.cssText = 'position:fixed;top:72px;right:20px;z-index:9999;display:flex;flex-direction:column;gap:8px;';
    document.body.appendChild(c);
    return c;
  }

  /* ---- Animate stats on dashboard ---- */
  function animateCounter(el) {
    const target = parseInt(el.dataset.target || el.textContent, 10);
    if (isNaN(target)) return;
    let current = 0;
    const step = Math.max(1, Math.ceil(target / 40));
    const interval = setInterval(function () {
      current = Math.min(current + step, target);
      el.textContent = current;
      if (current >= target) clearInterval(interval);
    }, 20);
  }

  document.querySelectorAll('.stat-value[data-target]').forEach(animateCounter);

  /* ---- Bug DNA progress bars ---- */
  document.querySelectorAll('.bug-bar[data-pct]').forEach(function (bar) {
    const pct = parseFloat(bar.dataset.pct) || 0;
    setTimeout(function () {
      bar.style.width = pct + '%';
    }, 300);
  });

});

/* ============================================================
   Video Recommendation Helper
   ============================================================ */
window.VideoHelper = {
  container: null,

  renderVideos: function (data, container) {
    this.container = container;
    container.innerHTML = '';

    if (data.error) {
      container.innerHTML = `
        <div class="alert alert-warning">
          <i class="bi bi-exclamation-triangle"></i>
          ${data.error}
        </div>`;
    }

    if (!data.videos || data.videos.length === 0) {
      container.innerHTML += '<p class="text-muted">No videos found.</p>';
      return;
    }

    data.videos.forEach(function (video) {
      const card = document.createElement('div');
      card.className = 'video-card mb-3 fade-in';

      const thumbHtml = video.thumbnail_url
        ? `<img src="${video.thumbnail_url}" alt="${video.title}" class="video-card-thumb" loading="lazy">`
        : `<div class="video-card-thumb-placeholder"><i class="bi bi-play-circle-fill"></i></div>`;

      const embedBtn = video.embed_url
        ? `<button class="btn btn-sm btn-outline-primary" onclick="VideoHelper.embedVideo('${video.embed_url}', '${video.title}', this)">
             <i class="bi bi-play-fill"></i> Watch Here
           </button>`
        : '';

      card.innerHTML = `
        ${thumbHtml}
        <div class="p-3">
          <p class="fw-bold mb-1 fs-14">${video.title}</p>
          ${video.channel_name ? `<p class="fs-12 text-muted mb-2"><i class="bi bi-person-circle"></i> ${video.channel_name}</p>` : ''}
          ${video.relevance_note ? `<p class="fs-12 mb-2" style="color:var(--accent-secondary)"><i class="bi bi-stars"></i> ${video.relevance_note}</p>` : ''}
          ${video.description ? `<p class="fs-12 text-muted mb-3">${video.description.slice(0, 120)}${video.description.length > 120 ? '…' : ''}</p>` : ''}
          <div class="d-flex gap-2 flex-wrap">
            ${embedBtn}
            <a href="${video.watch_url}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-secondary">
              <i class="bi bi-youtube"></i> Open YouTube
            </a>
          </div>
          ${video.source === 'search_fallback' ? '<p class="fs-12 text-muted mt-2"><i class="bi bi-info-circle"></i> Search link — no API results available</p>' : ''}
          ${video.is_sample_data ? '<p class="fs-12 text-warning mt-2"><i class="bi bi-database"></i> Sample data — verify availability</p>' : ''}
        </div>`;

      container.appendChild(card);
    });
  },

  embedVideo: function (embedUrl, title, btn) {
    const container = btn.closest('.video-card');
    container.innerHTML = `
      <div class="p-3">
        <p class="fw-bold mb-2 fs-14">${title}</p>
        <iframe class="video-embed" src="${embedUrl}" allowfullscreen title="${title}"></iframe>
        <a href="${embedUrl.replace('/embed/', '/watch?v=')}" target="_blank" class="btn btn-sm btn-secondary mt-2">
          <i class="bi bi-box-arrow-up-right"></i> Open in YouTube
        </a>
      </div>`;
  },
};

/* ============================================================
   Knowledge Base Status Poller
   ============================================================ */
window.pollDocStatus = function (docId, statusUrl, badgeEl) {
  let attempts = 0;
  const interval = setInterval(async function () {
    attempts++;
    if (attempts > 60) { clearInterval(interval); return; }
    try {
      const resp = await fetch(statusUrl);
      const data = await resp.json();
      badgeEl.textContent = data.status;
      badgeEl.className = 'status-badge ' + data.status;
      if (data.status === 'indexed' || data.status === 'failed') {
        clearInterval(interval);
        if (data.status === 'indexed') {
          badgeEl.title = `${data.total_chunks} chunks from ${data.total_pages} pages`;
        } else {
          badgeEl.title = data.error_message;
        }
      }
    } catch (e) { /* ignore */ }
  }, 3000);
};

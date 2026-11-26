const state = {
  activeUserId: null,
  username: null,
  role: null,
  publisherId: null,
  publisherName: null,
  walletBalance: 0,
  activeRegion: {
    region_id: 1,
    country_name: "India",
    country_code: "IN",
    currency_code: "INR",
    currency_name: "Indian Rupee",
    symbol: "₹",
    minor_units: 2,
    rate_from_inr: 1,
  },
  meta: { publishers: [], developers: [], tags: [], sales: [], sale_items: [], currencies: [], regions: [] },
  games: [],
  library: [],
  orders: [],
  pendingRefundGameId: null,
  playTimerInterval: null,
  spotlightIdx: 0,
  cart: [],
  dbTables: [],
  selectedDbTable: "GAMES",
};

// Banners for games added later are matched by title, because their IDs can vary.
const TITLE_BANNERS = {
  "Red Dead Redemption 2": "red-dead-redemption-2",
  "Black Myth: Wukong": "black-myth-wukong",
  "Hollow Knight: Silksong": "hollow-knight-silksong",
  "Clair Obscur: Expedition 33": "clair-obscur",
  "Split Fiction": "split-fiction",
  "Kingdom Come: Deliverance II": "kingdom-come-2",
  "Resident Evil Requiem": "resident-evil-requiem",
  "Forza Horizon 6": "forza-horizon-6",
  "Stardew Valley": "stardew-valley",
  "Terraria": "terraria",
  "Palworld": "palworld",
  "Mount & Blade II: Bannerlord": "bannerlord",
};

function gameBannerUrl(gameId, title = "") {
  if (Object.prototype.hasOwnProperty.call(TITLE_BANNERS, title)) {
    return `/static/banners/${TITLE_BANNERS[title]}.svg`;
  }
  const id = Number(gameId || 0);
  if (id >= 1 && id <= 12) {
    return `/static/banners/game_${id}.svg`;
  }
  const palettes = [
    ["#1e1b4b", "#db2777"],
    ["#1f2937", "#f59e0b"],
    ["#0f172a", "#38bdf8"],
    ["#3b0764", "#f472b6"],
  ];
  const [c1, c2] = palettes[id % palettes.length];
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 640 220'><defs><linearGradient id='g' x1='0%' y1='0%' x2='100%' y2='100%'><stop offset='0%' stop-color='${c1}'/><stop offset='100%' stop-color='${c2}'/></linearGradient></defs><rect width='640' height='220' fill='url(#g)'/><circle cx='520' cy='110' r='70' fill='white' fill-opacity='0.14'/><text x='30' y='182' fill='white' font-size='12' font-weight='700' font-family='sans-serif'>${esc(title).slice(0, 28)}</text></svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

function showAccountBanner(res, messagePrefix = "Signed in!") {
  const el = document.getElementById("loginIdNotice");
  if (!el) return;
  const roleMap = { user: "User", publisher: "Publisher", admin: "Platform Admin" };
  const roleLabel = roleMap[res.role] || "User";
  const studioInfo = res.publisher_name ? ` · Studio: <strong>${esc(res.publisher_name)}</strong>` : "";
  el.innerHTML = `
    <div>
      <strong>${esc(messagePrefix)}</strong> Signed in as <code>${esc(res.username)}</code> (${roleLabel}${studioInfo}).
    </div>
    <button class="btn-sm btn-ghost" onclick="document.getElementById('loginIdNotice').classList.add('hidden')">Dismiss</button>
  `;
  el.classList.remove("hidden");
}

function esc(val) {
  if (val === null || val === undefined) return "";
  return String(val)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatCurrencyNumber(displayVal, symbol, minorUnits = 2) {
  const units = Math.max(0, Number(minorUnits ?? 2));
  const num = Number(displayVal || 0);
  const rounded = units === 0 ? Math.round(num) : Number(num.toFixed(units));
  const formatted = Math.abs(rounded).toLocaleString("en-US", {
    minimumFractionDigits: units,
    maximumFractionDigits: units,
  });
  return `${rounded < 0 ? "-" : ""}${symbol}${formatted}`;
}

function money(val) {
  const num = Number(val || 0);
  if (num === 0) return "Free";
  return moneyExact(num);
}

function moneyExact(val) {
  const reg = state.activeRegion || { symbol: "₹", minor_units: 2, rate_from_inr: 1 };
  const converted = Number(val || 0) * Number(reg.rate_from_inr || 1);
  return formatCurrencyNumber(converted, reg.symbol || "₹", reg.minor_units ?? 2);
}

function moneyRecorded(displayVal, fallbackInrVal, symbol, minorUnits) {
  const hasDisplay = displayVal !== null && displayVal !== undefined && Number(displayVal) !== 0;
  if (hasDisplay || Number(fallbackInrVal || 0) === 0) {
    return formatCurrencyNumber(displayVal || 0, symbol || "₹", minorUnits ?? 2);
  }
  return moneyExact(fallbackInrVal);
}

function updateRegionUI() {
  const reg = state.activeRegion || { country_code: "IN", country_name: "India", symbol: "₹", currency_code: "INR", minor_units: 2 };
  const codeEl = document.getElementById("activeCountryCode");
  const labelEl = document.getElementById("activeRegionLabel");
  if (codeEl) codeEl.textContent = reg.country_code || "IN";
  if (labelEl) labelEl.textContent = `${reg.country_name} · ${reg.symbol} ${reg.currency_code}`;

  const depInput = document.getElementById("depositAmount");
  if (depInput) {
    const isZeroMinor = Number(reg.minor_units ?? 2) === 0;
    depInput.step = isZeroMinor ? "1" : "0.01";
    depInput.min = isZeroMinor ? "1" : "0.01";
    depInput.placeholder = `Amount in ${reg.symbol} ${reg.currency_code} (e.g. ${isZeroMinor ? "2000" : "1000.00"})`;
  }
  const cartEmpty = document.getElementById("cartTotalValue");
  if (cartEmpty && !state.cart.length) {
    cartEmpty.textContent = moneyExact(0);
  }
  renderRegionOptions(document.getElementById("regionSearchInput")?.value || "");
}

function renderRegionOptions(filterText = "") {
  const listEl = document.getElementById("regionOptionsList");
  if (!listEl) return;
  const q = filterText.trim().toLowerCase();
  const regions = (state.meta.regions || []).filter(
    (r) =>
      !q ||
      r.country_name.toLowerCase().includes(q) ||
      r.currency_code.toLowerCase().includes(q) ||
      (r.currency_name || "").toLowerCase().includes(q)
  );
  if (!regions.length) {
    listEl.innerHTML = `<div class="muted small" style="padding:8px;">No matching country or currency.</div>`;
    return;
  }
  const activeId = Number(state.activeRegion?.region_id || 0);
  listEl.innerHTML = regions
    .map(
      (r) => `
      <button type="button" class="region-opt ${Number(r.region_id) === activeId ? "active" : ""}" onclick="selectRegion(${r.region_id})">
        <span>
          <strong>${esc(r.country_name)}</strong>
          <span class="muted small">(${esc(r.country_code)})</span>
        </span>
        <span class="region-currency-badge">${esc(r.symbol)} ${esc(r.currency_code)}</span>
      </button>
    `
    )
    .join("");
}

function toggleRegionDialog(forceOpen = null) {
  const dlg = document.getElementById("regionDialog");
  if (!dlg) return;
  const shouldOpen = forceOpen === null ? dlg.classList.contains("hidden") : Boolean(forceOpen);
  dlg.classList.toggle("hidden", !shouldOpen);
  if (shouldOpen) {
    const search = document.getElementById("regionSearchInput");
    if (search) {
      search.value = "";
      renderRegionOptions("");
      search.focus();
    }
  }
}

async function selectRegion(regionId) {
  try {
    const res = await api("/api/auth/region", {
      method: "PUT",
      body: JSON.stringify({ region_id: Number(regionId) }),
    });
    if (res.active_region) {
      state.activeRegion = res.active_region;
    }
    toggleRegionDialog(false);
    updateRegionUI();
    renderFeaturedSpotlight();
    renderGames();
    renderCartModal();
    await Promise.all([
      loadAuthSession(),
      loadLibrary(),
      loadWishlist(),
      loadWalletAndOrders(),
      loadPublisherStudio(),
    ]);
    toast(`Region set to ${state.activeRegion.country_name} (${state.activeRegion.symbol} ${state.activeRegion.currency_code}).`);
  } catch (err) {
    toast(err.message, true);
  }
}

function syncRegisterWalletPlaceholder() {
  const sel = document.getElementById("registerRegionSelect");
  const inp = document.getElementById("registerWalletInput");
  if (!sel || !inp) return;
  const reg = (state.meta.regions || []).find((r) => Number(r.region_id) === Number(sel.value));
  if (!reg) return;
  const isZero = Number(reg.minor_units ?? 2) === 0;
  inp.step = isZero ? "1" : "0.01";
  inp.placeholder = `Initial Wallet Balance (${reg.symbol} ${reg.currency_code})`;
  const defaultDisplay = Number((5000 * Number(reg.rate_from_inr || 1)).toFixed(reg.minor_units ?? 2));
  inp.value = isZero ? String(Math.round(defaultDisplay)) : defaultDisplay.toFixed(2);
}

function fmtMinutes(mins) {
  const m = Number(mins || 0);
  if (m < 60) return `${m}m`;
  const h = (m / 60).toFixed(1);
  return `${h} hrs (${m}m)`;
}

function fmtDurationHMS(totalSeconds) {
  const s = Math.max(0, Math.floor(Number(totalSeconds || 0)));
  const hrs = Math.floor(s / 3600);
  const mins = Math.floor((s % 3600) / 60);
  const secs = s % 60;
  const pad = (n) => String(n).padStart(2, "0");
  return hrs > 0 ? `${pad(hrs)}:${pad(mins)}:${pad(secs)}` : `${pad(mins)}:${pad(secs)}`;
}

function fmtPlaytime(totalSeconds, fallbackMinutes = 0) {
  const secs = Math.max(0, Math.floor(Number(totalSeconds ?? (fallbackMinutes || 0) * 60)));
  if (secs < 60) return `${secs}s`;
  const mins = Math.floor(secs / 60);
  const rem = secs % 60;
  if (mins < 60) return rem > 0 ? `${mins}m ${rem}s` : `${mins}m`;
  const h = (secs / 3600).toFixed(1);
  return rem > 0 ? `${h} hrs (${mins}m ${rem}s)` : `${h} hrs (${mins}m)`;
}

function toast(msg, isError = false) {
  const wrap = document.getElementById("toastContainer");
  const el = document.createElement("div");
  el.className = `toast ${isError ? "error" : ""}`;
  el.textContent = msg;
  wrap.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

async function api(url, options = {}) {
  const opts = {
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    cache: "no-store",
    ...options,
  };
  const res = await fetch(url, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  return data;
}

function openModal(id) {
  document.getElementById(id).classList.remove("hidden");
}

function closeModal(id) {
  document.getElementById(id).classList.add("hidden");
}

function switchTab(tabName) {
  document.querySelectorAll(".nav-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === tabName);
  });
  document.querySelectorAll(".tab-panel").forEach((p) => {
    p.classList.toggle("active", p.id === `tab-${tabName}`);
  });
  if (tabName === "db") loadDbTables();
}

function updateCartBadge() {
  document.getElementById("cartCount").textContent = state.cart.length;
}

function loginGuardHtml(sectionName) {
  return `
    <div class="card">
      <h3>Login Required</h3>
      <p class="muted">Please log in as a User to access ${esc(sectionName)}.</p>
      <div class="card-actions mt-md">
        <button class="btn btn-primary" onclick="openModal('loginModal')">Login</button>
        <button class="btn btn-secondary" onclick="openModal('registerModal')">Register</button>
      </div>
    </div>
  `;
}

function applyRoleVisibility() {
  const isPub = state.role === "publisher";
  const isAdmin = state.role === "admin";
  document.querySelectorAll(".user-only-nav").forEach((el) => {
    el.classList.toggle("hidden", isPub || isAdmin);
  });
  document.querySelectorAll(".publisher-only-nav").forEach((el) => {
    el.classList.toggle("hidden", !isPub);
  });
  document.querySelectorAll(".admin-only-nav").forEach((el) => {
    el.classList.toggle("hidden", !isAdmin);
  });

  const activeBtn = document.querySelector(".nav-btn.active");
  if (activeBtn && activeBtn.classList.contains("hidden")) {
    switchTab("store");
  }
}

async function loadAuthSession() {
  const data = await api("/api/auth/me");
  const loggedOutEl = document.getElementById("loggedOutControls");
  const loggedInEl = document.getElementById("loggedInControls");

  if (data.active_region) {
    state.activeRegion = data.active_region;
  }
  updateRegionUI();

  if (!data.authenticated || !data.user) {
    state.activeUserId = null;
    state.username = null;
    state.role = null;
    state.publisherId = null;
    state.publisherName = null;
    state.walletBalance = 0;

    loggedOutEl.classList.remove("hidden");
    loggedInEl.classList.add("hidden");
    document.getElementById("badgeLibrary").textContent = "0";
    document.getElementById("badgeWishlist").textContent = "0";
    document.getElementById("badgeFriends").textContent = "0";
    const heroLine = document.getElementById("heroLoginIdLine");
    if (heroLine) heroLine.textContent = "Not logged in — sign in as a User, Publisher, or Platform Admin.";
    document.getElementById("userQuickStats").innerHTML = `
      <div class="stat-pill"><span class="val">Guest</span><span class="lbl">Sign in to play</span></div>
    `;
    applyRoleVisibility();
    return;
  }

  state.activeUserId = data.user.user_id;
  state.username = data.user.username;
  state.role = data.user.role || "user";
  state.publisherId = data.user.publisher_id;
  state.publisherName = data.user.publisher_name;
  state.walletBalance = Number(data.user.wallet_balance || 0);

  loggedOutEl.classList.add("hidden");
  loggedInEl.classList.remove("hidden");

  const roleBadge = document.getElementById("roleBadgePill");
  roleBadge.classList.remove("publisher", "admin");
  if (state.role === "publisher") {
    roleBadge.textContent = "PUBLISHER";
    roleBadge.classList.add("publisher");
  } else if (state.role === "admin") {
    roleBadge.textContent = "ADMIN";
    roleBadge.classList.add("admin");
  } else {
    roleBadge.textContent = "USER";
  }

  const bal = moneyExact(data.user.wallet_balance);
  document.getElementById("walletChip").textContent = bal;
  document.getElementById("walletBig").textContent = bal;

  const heroLine = document.getElementById("heroLoginIdLine");
  if (state.role === "admin") {
    document.getElementById("memberIdPill").textContent = `Admin: ${data.user.username}`;
    if (heroLine) {
      heroLine.innerHTML = `Platform Admin Session · Signed in as <strong>${esc(data.user.username)}</strong> (Data Explorer Unlocked)`;
    }
    document.getElementById("userQuickStats").innerHTML = `
      <div class="stat-pill"><span class="val">${esc(data.user.username)}</span><span class="lbl">Platform Admin</span></div>
      <div class="stat-pill"><span class="val">${data.stats.total_tables || 17}</span><span class="lbl">Data Tables</span></div>
      <div class="stat-pill"><span class="val">${data.stats.total_users || 0}</span><span class="lbl">Accounts</span></div>
      <div class="stat-pill"><span class="val">${data.stats.total_orders || 0}</span><span class="lbl">Orders</span></div>
    `;
  } else if (state.role === "publisher") {
    document.getElementById("memberIdPill").textContent = `${data.user.publisher_name || "Publisher"} (${data.user.username})`;
    if (heroLine) {
      heroLine.innerHTML = `Publisher Session · <strong>${esc(data.user.username)}</strong> (${esc(data.user.publisher_name || "Studio")})`;
    }
    document.getElementById("userQuickStats").innerHTML = `
      <div class="stat-pill"><span class="val">${esc(data.user.username)}</span><span class="lbl">Publisher</span></div>
      <div class="stat-pill"><span class="val">${esc(data.user.publisher_name || "Studio")}</span><span class="lbl">Studio</span></div>
      <div class="stat-pill"><span class="val">${data.stats.published_games || 0}</span><span class="lbl">Published Titles</span></div>
    `;
  } else {
    document.getElementById("memberIdPill").textContent = `User: ${data.user.username}`;
    document.getElementById("badgeLibrary").textContent = data.stats.owned_games;
    document.getElementById("badgeWishlist").textContent = data.stats.wishlist_count;
    document.getElementById("badgeFriends").textContent = data.stats.friend_count;
    if (heroLine) {
      heroLine.innerHTML = `Player Session · Signed in as <strong>${esc(data.user.username)}</strong>`;
    }
    document.getElementById("userQuickStats").innerHTML = `
      <div class="stat-pill"><span class="val">${esc(data.user.username)}</span><span class="lbl">Username</span></div>
      <div class="stat-pill"><span class="val">${data.stats.owned_games}</span><span class="lbl">Games Owned</span></div>
      <div class="stat-pill"><span class="val">${Math.round(data.stats.total_playtime_minutes / 60)}h</span><span class="lbl">Playtime</span></div>
      <div class="stat-pill"><span class="val">${data.stats.unlocked_achievements}</span><span class="lbl">Achievements</span></div>
    `;
  }

  applyRoleVisibility();
}

async function loadMeta() {
  state.meta = await api("/api/meta");

  const tagSelect = document.getElementById("filterTag");
  const prevTag = tagSelect.value;
  tagSelect.innerHTML = `<option value="">All Tags</option>` + state.meta.tags.map((t) => `<option value="${t.tag_id}">${esc(t.name)}</option>`).join("");
  tagSelect.value = prevTag;

  const pubSelect = document.getElementById("filterPublisher");
  const prevPub = pubSelect.value;
  pubSelect.innerHTML = `<option value="">All Publishers</option>` + state.meta.publishers.map((p) => `<option value="${p.publisher_id}">${esc(p.name)}</option>`).join("");
  pubSelect.value = prevPub;

  const devSelect = document.getElementById("filterDeveloper");
  const prevDev = devSelect.value;
  devSelect.innerHTML = `<option value="">All Developers</option>` + state.meta.developers.map((d) => `<option value="${d.developer_id}">${esc(d.name)}</option>`).join("");
  devSelect.value = prevDev;

  document.getElementById("manageDevSelect").innerHTML = state.meta.developers.map((d) => `<option value="${d.developer_id}">${esc(d.name)}</option>`).join("");
  document.getElementById("manageTagCheckboxes").innerHTML = state.meta.tags
    .map((t) => `<label class="checkbox-pill"><input type="checkbox" name="tag_ids" value="${t.tag_id}" /><span>${esc(t.name)}</span></label>`)
    .join("");
  document.getElementById("manageSaleSelect").innerHTML = state.meta.sales
    .map((s) => `<option value="${s.sale_id}">${esc(s.title)} ${s.is_active ? "(ACTIVE)" : ""}</option>`)
    .join("");

  const regSel = document.getElementById("registerRegionSelect");
  if (regSel && state.meta.regions) {
    const prevReg = regSel.value;
    regSel.innerHTML = state.meta.regions
      .map((r) => `<option value="${r.region_id}">${esc(r.country_name)} (${esc(r.symbol)} ${esc(r.currency_code)})</option>`)
      .join("");
    if (prevReg) regSel.value = prevReg;
    else if (state.activeRegion?.region_id) regSel.value = String(state.activeRegion.region_id);
    syncRegisterWalletPlaceholder();
  }
  renderRegionOptions(document.getElementById("regionSearchInput")?.value || "");

  const activeSales = state.meta.sales.filter((s) => s.is_active);
  document.getElementById("activeSaleBanner").textContent = activeSales.length
    ? `Active Event: ${activeSales.map((s) => s.title).join(", ")} — Seasonal discounts live now!`
    : "Browse the SAUNA catalog, build your library, or sign in as a Publisher to release titles.";
  applyChristmasTheme(activeSales);
}

// ---------------------------------------------------------------------------
// Christmas theme: on only while a sale with "Christmas" in its title is active
// ---------------------------------------------------------------------------
let xmasTimer = null;

function applyChristmasTheme(activeSales) {
  const sale = activeSales.find((s) => /christmas/i.test(s.title));
  const banner = document.getElementById("xmasBanner");
  document.body.classList.toggle("xmas", Boolean(sale));
  banner.classList.toggle("hidden", !sale);
  clearInterval(xmasTimer);
  if (!sale) return;

  const pcts = state.meta.sale_items.filter((i) => i.sale_id === sale.sale_id).map((i) => i.discount_pct);
  document.getElementById("xmasTitle").textContent = sale.title;
  document.getElementById("xmasSubtitle").textContent = pcts.length
    ? `Christmas came early: up to ${Math.max(...pcts)}% off.`
    : "Christmas came early.";

  // The database stores sale times in UTC without a zone marker.
  const end = new Date(`${sale.end_date.replace(" ", "T")}Z`).getTime();
  const tick = () => {
    const left = Math.max(0, Math.floor((end - Date.now()) / 1000));
    const parts = [Math.floor(left / 86400), Math.floor(left / 3600) % 24, Math.floor(left / 60) % 60, left % 60];
    ["xmasDays", "xmasHours", "xmasMins", "xmasSecs"].forEach((id, i) => {
      document.getElementById(id).textContent = String(parts[i]).padStart(2, "0");
    });
    if (left === 0) {
      clearInterval(xmasTimer);
      document.body.classList.remove("xmas");
      banner.classList.add("hidden");
    }
  };
  tick();
  xmasTimer = setInterval(tick, 1000);
}

function showChristmasDeals() {
  document.getElementById("filterOnSale").checked = true;
  state.spotlightIdx = 0;
  loadGames().then(() => document.getElementById("gamesGrid").scrollIntoView({ behavior: "smooth" }));
}

async function loadGames() {
  const params = new URLSearchParams();
  const q = document.getElementById("searchInput").value.trim();
  const tag = document.getElementById("filterTag").value;
  const pub = document.getElementById("filterPublisher").value;
  const dev = document.getElementById("filterDeveloper").value;
  const onSale = document.getElementById("filterOnSale").checked;
  if (q) params.set("q", q);
  if (tag) params.set("tag_id", tag);
  if (pub) params.set("publisher_id", pub);
  if (dev) params.set("developer_id", dev);
  if (onSale) params.set("on_sale", "1");

  state.games = await api(`/api/games?${params.toString()}`);
  renderFeaturedSpotlight();
  renderGames();
}

function cycleSpotlight(delta) {
  const pool = state.games.filter((g) => g.discount_pct > 0);
  const list = pool.length ? pool : state.games;
  if (!list.length) return;
  state.spotlightIdx = (state.spotlightIdx + delta + list.length) % list.length;
  renderFeaturedSpotlight();
}

function renderFeaturedSpotlight() {
  const box = document.getElementById("featuredSpotlight");
  if (!box) return;
  const pool = state.games.filter((g) => g.discount_pct > 0);
  const list = pool.length ? pool : state.games;
  if (!list.length) {
    box.classList.add("hidden");
    return;
  }
  if (state.spotlightIdx >= list.length) state.spotlightIdx = 0;
  const g = list[state.spotlightIdx];
  const bannerUrl = gameBannerUrl(g.game_id, g.title);
  const inCart = state.cart.some((c) => c.game_id === g.game_id);
  const isNonPlayer = state.role === "publisher" || state.role === "admin";

  let actionBtn = "";
  if (isNonPlayer) {
    actionBtn = "";
  } else if (g.owned) {
    actionBtn = `<span class="tag-chip">In Library</span>`;
  } else if (inCart) {
    actionBtn = `<button class="btn-sm btn-secondary" onclick="removeFromCart(${g.game_id})">In Cart</button>`;
  } else {
    actionBtn = `<button class="btn-sm btn-sale" onclick="addToCart(${g.game_id})">Add to Cart · ${money(g.effective_price)}</button>`;
  }

  box.classList.remove("hidden");
  box.innerHTML = `
    <div class="spotlight-art" style="background-image:url('${bannerUrl}')" onclick="openGameDetail(${g.game_id})">
      <div class="spotlight-art-inner">
        <span class="spotlight-tag">${g.discount_pct > 0 ? `-${g.discount_pct}% ${esc(g.sale_title || "FEATURED SALE")}` : "FEATURED GAME"}</span>
        <h2>${esc(g.title)}</h2>
      </div>
    </div>
    <div class="spotlight-body">
      <div>
        <div class="game-meta">${esc(g.developer_name)} · ${esc(g.publisher_name)} · ${esc(g.age_rating || "N/A")}</div>
        <p class="mt-sm" style="margin-bottom:8px;">${esc(g.description)}</p>
        <div class="tag-row">${g.tags.map((t) => `<span class="tag-chip">${esc(t.name)}</span>`).join("")}</div>
      </div>
      <div class="game-footer">
        <div class="price-box">
          ${g.discount_pct > 0 ? `<span class="price-strike">${moneyExact(g.base_price)}</span> <span class="price-final on-sale">${money(g.effective_price)}</span>` : `<span class="price-final">${money(g.effective_price)}</span>`}
        </div>
        <div class="spotlight-nav">
          <button class="btn-sm btn-ghost" onclick="cycleSpotlight(-1)" title="Previous">◀</button>
          <button class="btn-sm btn-ghost" onclick="cycleSpotlight(1)" title="Next">▶</button>
          <button class="btn-sm btn-secondary" onclick="openGameDetail(${g.game_id})">Details</button>
          ${actionBtn}
        </div>
      </div>
    </div>
  `;
}

function renderGames() {
  const grid = document.getElementById("gamesGrid");
  if (!state.games.length) {
    grid.innerHTML = `<div class="card">No games match your current filters.</div>`;
    return;
  }
  const isNonPlayer = state.role === "publisher" || state.role === "admin";

  grid.innerHTML = state.games
    .map((g) => {
      const inCart = state.cart.some((c) => c.game_id === g.game_id);
      const bannerUrl = gameBannerUrl(g.game_id, g.title);
      const reviewBadge =
        g.positive_pct !== null
          ? `<span class="muted small">${g.positive_pct}% positive (${g.review_count})</span>`
          : `<span class="muted small">No reviews yet</span>`;
      const priceHtml =
        g.discount_pct > 0
          ? `<span class="price-strike">${moneyExact(g.base_price)}</span> <span class="price-final on-sale">${money(g.effective_price)}</span>`
          : `<span class="price-final">${money(g.effective_price)}</span>`;

      let actionBtn = "";
      let wishBtn = "";
      if (isNonPlayer) {
        actionBtn = `<button class="btn-sm btn-secondary" onclick="openGameDetail(${g.game_id})">View</button>`;
      } else {
        if (g.owned) {
          actionBtn = `<span class="tag-chip">In Library</span>`;
        } else if (inCart) {
          actionBtn = `<button class="btn-sm btn-secondary" onclick="removeFromCart(${g.game_id})">In Cart</button>`;
        } else {
          actionBtn = `<button class="btn-sm btn-sale" onclick="addToCart(${g.game_id})">Add to Cart</button>`;
        }
        wishBtn = g.owned
          ? ""
          : `<button class="btn-sm btn-ghost" onclick="toggleWishlist(${g.game_id}, ${g.wishlisted ? "true" : "false"})">${
              g.wishlisted ? "★ Wishlisted" : "☆ Wishlist"
            }</button>`;
      }

      return `
        <article class="game-card">
          <div class="game-banner" style="background-image:url('${bannerUrl}')" onclick="openGameDetail(${g.game_id})">
            <div class="game-banner-top">
              <span class="age-pill">${esc(g.age_rating || "N/A")}</span>
              ${g.discount_pct > 0 ? `<span class="discount-badge">-${g.discount_pct}%</span>` : ""}
            </div>
            <h3 class="game-title">${esc(g.title)}</h3>
          </div>
          <div class="game-body">
            <div class="game-meta">${esc(g.developer_name)} · ${esc(g.publisher_name)}</div>
            <div class="game-desc">${esc(g.description)}</div>
            <div class="tag-row">
              ${g.tags.map((t) => `<span class="tag-chip">${esc(t.name)}</span>`).join("")}
            </div>
            <div>${reviewBadge} · <span class="muted small">${g.achievement_count} achievements</span></div>
            <div class="game-footer">
              <div class="price-box">${priceHtml}</div>
              <div class="card-actions">
                ${wishBtn}
                ${actionBtn}
              </div>
            </div>
          </div>
        </article>
      `;
    })
    .join("");
}

async function openGameDetail(gameId) {
  const g = await api(`/api/games/${gameId}`);
  const wrap = document.getElementById("gameModalContent");
  const inCart = state.cart.some((c) => c.game_id === g.game_id);
  const isNonPlayer = state.role === "publisher" || state.role === "admin";

  const refundBtn =
    !isNonPlayer && g.owned && g.refund_info && g.refund_info.refund_eligible
      ? `<button class="btn btn-danger" onclick="openRefundModal(${g.game_id})">Refund (${moneyExact(g.refund_info.refundable_amount)})</button>`
      : "";

  const buyBtn = isNonPlayer
    ? `<span class="tag-chip">${state.role === "admin" ? "Admin Preview" : "Publisher View"}</span>`
    : g.owned
    ? `<div class="card-actions"><span class="tag-chip">Owned in Library</span>${refundBtn}</div>`
    : inCart
    ? `<button class="btn btn-secondary" onclick="removeFromCart(${g.game_id}); openGameDetail(${g.game_id})">Remove from Cart</button>`
    : `<button class="btn btn-sale" onclick="addToCart(${g.game_id}); openGameDetail(${g.game_id})">Add to Cart · ${money(g.effective_price)}</button>`;

  const reviewFormHtml = isNonPlayer
    ? `<p class="muted small mt-sm">Switch to a User account to write player reviews.</p>`
    : !state.activeUserId
    ? `<p class="muted small mt-sm">Log in as a User to post a review.</p>`
    : g.owned
    ? `
      <form id="submitReviewForm" class="form-stack mt-md" onsubmit="submitReview(event, ${g.game_id})">
        <div class="form-row">
          <select name="is_recommended" class="input">
            <option value="1">Recommended 👍 (Positive)</option>
            <option value="0">Not Recommended 👎 (Negative)</option>
          </select>
          <button type="submit" class="btn btn-primary">Post / Update Review</button>
        </div>
        <textarea name="review_text" class="input" rows="2" placeholder="Share your review with the community..." required></textarea>
      </form>
    `
    : `<p class="muted small mt-sm">Purchase this game to write a review.</p>`;

  const bannerUrl = gameBannerUrl(g.game_id, g.title);
  wrap.innerHTML = `
    <div class="modal-banner" style="background-image:url('${bannerUrl}')">
      <div class="modal-banner-title">
        <h2>${esc(g.title)}</h2>
      </div>
    </div>
    <div class="section-header">
      <div>
        <div class="muted small">Developer: ${esc(g.developer_name)} · Publisher: ${esc(g.publisher_name)} · Released: ${esc(g.release_date || "TBA")} · ${esc(g.age_rating)}</div>
      </div>
      <div>${buyBtn}</div>
    </div>
    <p>${esc(g.description)}</p>
    <div class="tag-row">${g.tags.map((t) => `<span class="tag-chip">${esc(t.name)}</span>`).join("")}</div>
    ${g.discount_pct > 0 ? `<p class="mt-sm" style="color:var(--sale)">Active Sale (${esc(g.sale_title)}): -${g.discount_pct}% off (${moneyExact(g.base_price)} → ${money(g.effective_price)})</p>` : ""}
    ${
      !isNonPlayer && g.owned && g.refund_info
        ? `<div class="mt-sm"><span class="refund-pill ${g.refund_info.refund_eligible ? "eligible" : "expired"}">Steam Refund Policy: ${esc(g.refund_info.refund_status_text)}</span></div>`
        : ""
    }

    <hr class="divider" />
    <h3>Achievements (${g.achievements.length})</h3>
    <div class="stack-list mt-sm">
      ${
        g.achievements.length
          ? g.achievements
              .map(
                (a) => `
              <div class="ach-row ${a.unlocked ? "ach-unlocked" : ""}">
                <div>
                  <strong>${esc(a.name)}</strong> ${a.is_hidden ? `<span class="age-pill">Hidden</span>` : ""}
                  <div class="muted small">${esc(a.description)}</div>
                </div>
                <div>
                  ${
                    a.unlocked
                      ? `<span class="tag-chip" style="color:var(--sale)">Unlocked</span>`
                      : g.owned && !isNonPlayer
                      ? `<button class="btn-sm btn-primary" onclick="unlockAchievement(${a.achievement_id}, ${g.game_id})">Unlock</button>`
                      : `<span class="muted small">Locked</span>`
                  }
                </div>
              </div>
            `
              )
              .join("")
          : `<div class="muted small">No achievements configured for this game.</div>`
      }
    </div>

    <hr class="divider" />
    <h3>Community Reviews (${g.reviews.length})</h3>
    ${reviewFormHtml}
    <div class="stack-list mt-md">
      ${
        g.reviews.length
          ? g.reviews
              .map(
                (r) => `
              <div class="review-card">
                <div class="review-head">
                  <span><strong>Member #${r.user_id}</strong> (${esc(r.country)}) · ${fmtMinutes(r.playtime_at_review)} at review</span>
                  <span class="${r.is_recommended ? "rec-yes" : "rec-no"}">${r.is_recommended ? "Recommended" : "Not Recommended"}</span>
                </div>
                <div>${esc(r.review_text)}</div>
                <div class="mt-sm">
                  <button class="btn-sm btn-ghost" onclick="voteHelpful(${r.review_id}, ${g.game_id})">Helpful (${r.helpful_votes})</button>
                </div>
              </div>
            `
              )
              .join("")
          : `<div class="muted small">No reviews yet.</div>`
      }
    </div>
  `;
  openModal("gameModal");
}

function addToCart(gameId) {
  if (state.role === "publisher" || state.role === "admin") {
    return toast("Only User accounts can purchase games. Log in as a User.", true);
  }
  const game = state.games.find((g) => g.game_id === gameId);
  if (!game) return;
  if (game.owned) return toast("You already own this game.", true);
  if (!state.cart.some((c) => c.game_id === gameId)) {
    state.cart.push(game);
    updateCartBadge();
    renderFeaturedSpotlight();
    renderGames();
    toast(`Added "${game.title}" to cart.`);
  }
}

function removeFromCart(gameId) {
  state.cart = state.cart.filter((c) => c.game_id !== gameId);
  updateCartBadge();
  renderFeaturedSpotlight();
  renderGames();
  renderCartModal();
}

function renderCartModal() {
  const wrap = document.getElementById("cartItemsWrap");
  const balEl = document.getElementById("cartWalletBalance");
  const warnEl = document.getElementById("cartBalanceWarning");

  if (balEl) balEl.textContent = state.activeUserId ? moneyExact(state.walletBalance) : "Login required";
  if (warnEl) warnEl.textContent = "";

  renderPaymentMethod();

  if (!state.cart.length) {
    wrap.innerHTML = `<div class="muted">Your cart is empty.</div>`;
    document.getElementById("cartTotalValue").textContent = moneyExact(0);
    return;
  }
  let total = 0;
  wrap.innerHTML = state.cart
    .map((g) => {
      total += Number(g.effective_price || 0);
      return `
        <div class="list-row">
          <div>
            <strong>${esc(g.title)}</strong>
            <div class="muted small">${g.discount_pct > 0 ? `-${g.discount_pct}% sale applied` : "Standard price"}</div>
          </div>
          <div class="card-actions">
            <strong>${money(g.effective_price)}</strong>
            <button class="btn-sm btn-danger" onclick="removeFromCart(${g.game_id})">Remove</button>
          </div>
        </div>
      `;
    })
    .join("");
  document.getElementById("cartTotalValue").textContent = moneyExact(total);

  if (state.activeUserId && total > state.walletBalance + 1e-9 && warnEl) {
    warnEl.textContent = `Insufficient wallet balance (${moneyExact(state.walletBalance)} < ${moneyExact(total)}).`;
  }
}

// Payment link read from static/images/upi_qr.png. Change both together.
const UPI_LINK = "upi://pay?pa=senzarublackrose-1@oksbi&pn=Hariharan%20Sankar&aid=uGICAgKCMl8DEVA";

function renderPaymentMethod() {
  const isUpi = document.querySelector('input[name="payMethod"]:checked').value === "upi";
  const panel = document.getElementById("upiPanel");
  document.getElementById("cartWalletInfo").classList.toggle("hidden", isUpi);
  document.getElementById("checkoutBtn").classList.toggle("hidden", isUpi);
  panel.classList.toggle("hidden", !isUpi || !state.cart.length);

  if (!isUpi || !state.cart.length) {
    panel.innerHTML = "";
    return;
  }
  if (!state.activeUserId || state.role !== "user") {
    panel.innerHTML = `<div class="muted">Log in as a User to see the UPI QR code.</div>`;
    return;
  }
  const total = state.cart.reduce((sum, g) => sum + Number(g.effective_price || 0), 0);
  if (total <= 0) {
    panel.innerHTML = `<div class="muted">Nothing to pay: these games are free.</div>`;
    return;
  }
  panel.innerHTML = `
    <strong>Scan and enter ${formatCurrencyNumber(total, "₹", 2)}</strong>
    <div class="small muted">UPI pays in Indian rupees (INR), whatever store currency is selected.</div>
    <img src="/static/images/upi_qr.png" alt="UPI QR code for senzarublackrose-1@oksbi" />
    <div class="small">Paying <strong>Hariharan Sankar</strong></div>
    <div class="small mt-xs"><a href="${esc(UPI_LINK)}">Open in a UPI app</a> (on your phone)</div>
    <div class="small muted mt-sm">UPI payments are not confirmed automatically, so games are not added to your library on payment.</div>
  `;
}

async function toggleWishlist(gameId, isWishlisted) {
  if (!state.activeUserId || state.role !== "user") {
    openModal("loginModal");
    return toast("Please log in as a User to manage your wishlist.", true);
  }
  try {
    if (isWishlisted) {
      await api(`/api/users/${state.activeUserId}/wishlist/${gameId}`, { method: "DELETE" });
      toast("Removed from wishlist.");
    } else {
      await api(`/api/users/${state.activeUserId}/wishlist`, {
        method: "POST",
        body: JSON.stringify({ game_id: gameId }),
      });
      toast("Added to wishlist!");
    }
    await Promise.all([loadGames(), loadAuthSession(), loadWishlist()]);
  } catch (err) {
    toast(err.message, true);
  }
}

async function submitReview(e, gameId) {
  e.preventDefault();
  if (!state.activeUserId) return openModal("loginModal");
  const fd = new FormData(e.target);
  try {
    await api(`/api/games/${gameId}/reviews`, {
      method: "POST",
      body: JSON.stringify({
        is_recommended: fd.get("is_recommended") === "1",
        review_text: fd.get("review_text"),
      }),
    });
    toast("Review published!");
    await Promise.all([loadGames(), openGameDetail(gameId)]);
  } catch (err) {
    toast(err.message, true);
  }
}

async function voteHelpful(reviewId, gameId) {
  if (!state.activeUserId) {
    openModal("loginModal");
    return toast("Please log in to vote on reviews.", true);
  }
  try {
    await api(`/api/reviews/${reviewId}/helpful`, { method: "POST" });
    await openGameDetail(gameId);
  } catch (err) {
    toast(err.message, true);
  }
}

async function unlockAchievement(achievementId, gameId) {
  if (!state.activeUserId) return openModal("loginModal");
  try {
    await api(`/api/users/${state.activeUserId}/achievements/${achievementId}/unlock`, { method: "POST" });
    toast("Achievement unlocked!");
    await Promise.all([loadAuthSession(), loadLibrary(), openGameDetail(gameId)]);
  } catch (err) {
    toast(err.message, true);
  }
}

async function loadLibrary() {
  if (state.playTimerInterval) {
    clearInterval(state.playTimerInterval);
    state.playTimerInterval = null;
  }
  const wrap = document.getElementById("libraryList");
  if (!state.activeUserId || state.role !== "user") {
    state.library = [];
    wrap.innerHTML = loginGuardHtml("your Game Library");
    return;
  }
  const rows = await api(`/api/users/${state.activeUserId}/library`);
  state.library = rows;
  if (!rows.length) {
    wrap.innerHTML = `<div class="card muted">No games in library yet. Purchase one from the Store!</div>`;
    return;
  }
  wrap.innerHTML = rows
    .map((g) => {
      const isRunning = Boolean(g.active_session_started_at);
      const refundBadge = g.refund_eligible
        ? `<span class="refund-pill eligible">${esc(g.refund_status_text)}</span>`
        : `<span class="refund-pill expired">${esc(g.refund_status_text || "Not refundable")}</span>`;
      const refundAction = g.refund_eligible
        ? `<button class="btn-sm btn-danger" onclick="openRefundModal(${g.game_id})">Refund (${moneyExact(g.refundable_amount)})</button>`
        : "";
      const playExitBtn = isRunning
        ? `<button class="btn-sm btn-exit" onclick="exitPlaySession(${g.game_id})">■ Exit</button>`
        : `<button class="btn-sm btn-primary" onclick="startPlaySession(${g.game_id})">▶ Play</button>
           <button class="btn-sm btn-ghost" onclick="playGame(${g.game_id}, 30)" title="Quick-simulate +30m playtime">+30m</button>`;
      const sessionInfoHtml = isRunning
        ? `<div class="mt-xs"><span class="session-live-pill">● Active Session · Start: <code>${esc(g.active_session_started_at)}</code> · Timer: <span class="live-timer" data-elapsed="${Number(g.active_session_elapsed_seconds || 0)}">${fmtDurationHMS(g.active_session_elapsed_seconds || 0)}</span></span></div>`
        : g.last_session_started_at && g.last_session_ended_at
        ? `<div class="muted small mt-xs">Last Session: <code>${esc(g.last_session_started_at)}</code> → <code>${esc(g.last_session_ended_at)}</code> (<strong>${fmtDurationHMS(g.last_session_seconds || 0)}</strong>)</div>`
        : "";
      return `
      <div class="list-row">
        <div class="lib-item-left">
          <div class="lib-thumb" style="background-image:url('${gameBannerUrl(g.game_id, g.title)}')"></div>
          <div>
            <strong>${esc(g.title)}</strong> <span class="muted small">by ${esc(g.developer_name)}</span>
            <div class="muted small mt-xs">
              Playtime: <strong>${fmtPlaytime(g.playtime_seconds, g.playtime_minutes)}</strong> ·
              Last Played: ${esc(g.last_played_at || "Never")} ·
              Achievements: ${g.unlocked_achievements}/${g.total_achievements}
            </div>
            ${sessionInfoHtml}
            <div class="mt-xs">${refundBadge}</div>
          </div>
        </div>
        <div class="card-actions">
          ${playExitBtn}
          <button class="btn-sm btn-secondary" onclick="openGameDetail(${g.game_id})">Details &amp; Achievements</button>
          ${refundAction}
        </div>
      </div>
    `;
    })
    .join("");

  if (rows.some((r) => Boolean(r.active_session_started_at))) {
    state.playTimerInterval = setInterval(() => {
      document.querySelectorAll(".live-timer").forEach((el) => {
        const next = Number(el.dataset.elapsed || 0) + 1;
        el.dataset.elapsed = String(next);
        el.textContent = fmtDurationHMS(next);
      });
    }, 1000);
  }
}

function findRefundCandidate(gameId) {
  const libItem = state.library.find((g) => Number(g.game_id) === Number(gameId));
  if (libItem) {
    return {
      game_id: libItem.game_id,
      title: libItem.title,
      order_id: libItem.order_id,
      purchased_at: libItem.purchased_at || libItem.acquired_at,
      playtime_minutes: libItem.playtime_minutes,
      playtime_seconds: libItem.playtime_seconds,
      refundable_amount: libItem.refundable_amount,
      refund_eligible: libItem.refund_eligible,
      refund_status_text: libItem.refund_status_text,
    };
  }
  for (const o of state.orders) {
    for (const it of o.items || []) {
      if (Number(it.game_id) === Number(gameId) && it.status === "purchased") {
        return {
          game_id: it.game_id,
          title: it.title,
          order_id: o.order_id,
          purchased_at: o.created_at,
          playtime_minutes: it.playtime_minutes || 0,
          refundable_amount: it.refundable_amount ?? it.price_at_purchase,
          refund_eligible: it.refund_eligible,
          refund_status_text: it.refund_status_text,
        };
      }
    }
  }
  return null;
}

async function openRefundModal(gameId) {
  if (!state.activeUserId || state.role !== "user") return openModal("loginModal");
  let item = findRefundCandidate(gameId);
  if (!item) {
    await loadLibrary();
    item = findRefundCandidate(gameId);
  }
  if (!item) return toast("Refund details unavailable for this game.", true);
  if (!item.refund_eligible) return toast(item.refund_status_text || "Game is not eligible for refund.", true);

  state.pendingRefundGameId = Number(gameId);
  document.getElementById("refundSummaryBox").innerHTML = `
    <div><span class="lbl">Game</span><strong>${esc(item.title)}</strong></div>
    <div><span class="lbl">Order Reference</span><strong>#${esc(item.order_id || "—")}</strong></div>
    <div><span class="lbl">Playtime Recorded</span><strong>${fmtPlaytime(item.playtime_seconds, item.playtime_minutes)}</strong> <span class="muted small">(limit &lt; 2h)</span></div>
    <div><span class="lbl">Purchased At</span><strong>${esc(item.purchased_at || "—")}</strong></div>
    <div style="grid-column: 1 / -1; border-top: 1px solid var(--border); padding-top: 8px; display:flex; justify-content:space-between; align-items:center;">
      <span class="muted">Refund credited to SAUNA Wallet</span>
      <strong style="color:var(--sale); font-size:16px;">+${moneyExact(item.refundable_amount)}</strong>
    </div>
  `;
  openModal("refundModal");
}

async function startPlaySession(gameId) {
  try {
    const res = await api(`/api/users/${state.activeUserId}/library/${gameId}/play/start`, {
      method: "POST",
    });
    toast(`Session started at ${res.active_session_started_at} — click Exit when done.`);
    await Promise.all([loadLibrary(), loadAuthSession()]);
  } catch (err) {
    toast(err.message, true);
  }
}

async function exitPlaySession(gameId) {
  try {
    const res = await api(`/api/users/${state.activeUserId}/library/${gameId}/play/exit`, {
      method: "POST",
    });
    toast(
      `Exited session (${fmtDurationHMS(res.last_session_seconds)} noted: ${res.last_session_started_at} → ${res.last_session_ended_at}).`
    );
    await Promise.all([loadLibrary(), loadAuthSession()]);
  } catch (err) {
    toast(err.message, true);
  }
}

async function playGame(gameId, minutes) {
  try {
    await api(`/api/users/${state.activeUserId}/library/${gameId}/play`, {
      method: "POST",
      body: JSON.stringify({ minutes }),
    });
    toast(`Logged +${minutes}m playtime!`);
    await Promise.all([loadLibrary(), loadAuthSession()]);
  } catch (err) {
    toast(err.message, true);
  }
}

async function loadWishlist() {
  const wrap = document.getElementById("wishlistList");
  if (!state.activeUserId || state.role !== "user") {
    wrap.innerHTML = loginGuardHtml("your Wishlist");
    return;
  }
  const rows = await api(`/api/users/${state.activeUserId}/wishlist`);
  if (!rows.length) {
    wrap.innerHTML = `<div class="card muted">Your wishlist is empty.</div>`;
    return;
  }
  wrap.innerHTML = rows
    .map(
      (w) => `
      <div class="list-row">
        <div class="lib-item-left">
          <div class="lib-thumb" style="background-image:url('${gameBannerUrl(w.game_id, w.title)}')"></div>
          <div>
            <strong>${esc(w.title)}</strong> <span class="muted small">(${esc(w.publisher_name)})</span>
            <div class="muted small">Added: ${esc(w.added_at)} ${w.discount_pct > 0 ? `· <span style="color:var(--sale)">-${w.discount_pct}% (${esc(w.sale_title)})</span>` : ""}</div>
          </div>
        </div>
        <div class="card-actions">
          <strong>${money(w.effective_price)}</strong>
          <button class="btn-sm btn-sale" onclick="buySingleGame(${w.game_id})">Buy Now (Wallet)</button>
          <button class="btn-sm btn-danger" onclick="toggleWishlist(${w.game_id}, true)">Remove</button>
        </div>
      </div>
    `
    )
    .join("");
}

async function buySingleGame(gameId) {
  if (!state.activeUserId || state.role !== "user") return openModal("loginModal");
  try {
    const res = await api(`/api/users/${state.activeUserId}/checkout`, {
      method: "POST",
      body: JSON.stringify({ game_ids: [gameId], payment_method: "SAUNA Wallet" }),
    });
    state.walletBalance = Number(res.wallet_balance);
    document.getElementById("walletChip").textContent = moneyExact(state.walletBalance);
    document.getElementById("walletBig").textContent = moneyExact(state.walletBalance);
    toast(`Order #${res.order_id} completed (${moneyExact(res.total_amount)})!`);
    await refreshUserData();
  } catch (err) {
    toast(err.message, true);
  }
}

async function loadWalletAndOrders() {
  const guard = document.getElementById("walletAuthGuard");
  const content = document.getElementById("walletContent");
  if (!state.activeUserId || state.role !== "user") {
    state.orders = [];
    guard.innerHTML = loginGuardHtml("Wallet & Orders");
    guard.classList.remove("hidden");
    content.classList.add("hidden");
    return;
  }
  guard.classList.add("hidden");
  content.classList.remove("hidden");

  const [txns, orders] = await Promise.all([
    api(`/api/users/${state.activeUserId}/wallet-transactions`),
    api(`/api/users/${state.activeUserId}/orders`),
  ]);
  state.orders = orders;

  const txnWrap = document.getElementById("walletTxnTable");
  txnWrap.innerHTML = txns.length
    ? `<table>
        <thead><tr><th>ID</th><th>Type</th><th>Amount</th><th>Order</th><th>Date</th></tr></thead>
        <tbody>
          ${txns
            .map(
              (t) => `
              <tr>
                <td>#${t.txn_id}</td>
                <td><span class="tag-chip">${esc(t.txn_type)}</span></td>
                <td style="color:${t.amount >= 0 ? "var(--sale)" : "var(--danger)"}">${t.amount >= 0 ? "+" : ""}${moneyRecorded(t.display_amount, t.amount, t.currency_symbol, t.minor_units)} <span class="muted small">(${esc(t.currency_code || "INR")})</span></td>
                <td>${t.reference_order_id ? `#${t.reference_order_id}` : "—"}</td>
                <td class="muted">${esc(t.created_at)}</td>
              </tr>`
            )
            .join("")}
        </tbody>
      </table>`
    : `<div class="muted small" style="padding:12px;">No wallet transactions yet.</div>`;

  const ordersWrap = document.getElementById("ordersList");
  ordersWrap.innerHTML = orders.length
    ? orders
        .map(
          (o) => `
          <div class="review-card">
            <div class="review-head">
              <strong>Order #${o.order_id} · ${esc(o.payment_method)}</strong>
              <span style="display:inline-flex;align-items:center;gap:6px;">
                <strong style="color:var(--sale)">${moneyRecorded(o.display_total_amount, o.total_amount, o.currency_symbol, o.minor_units)}</strong>
                <span class="muted small">(${esc(o.currency_code || "INR")})</span>
                <span class="order-status-pill ${esc(o.status)}">${esc(o.status.replace("_", " "))}</span>
              </span>
            </div>
            <div class="muted small">${esc(o.created_at)}</div>
            <ul class="mt-sm" style="margin:8px 0 0 18px; padding:0;">
              ${o.items
                .map((it) => {
                  let badge = "";
                  if (it.status === "refunded") {
                    badge = `<span class="refund-pill refunded">Refunded${it.refunded_at ? ` · ${esc(it.refunded_at)}` : ""}${it.refund_reason ? ` (${esc(it.refund_reason)})` : ""}</span>`;
                  } else if (it.refund_eligible) {
                    badge = `<button class="btn-sm btn-danger" onclick="openRefundModal(${it.game_id})">Refund</button>`;
                  } else if (it.refund_status_text) {
                    badge = `<span class="refund-pill expired">${esc(it.refund_status_text)}</span>`;
                  }
                  return `<li><div class="order-item-row"><span>${esc(it.title)} — ${moneyRecorded(it.display_price_at_purchase, it.price_at_purchase, it.currency_symbol, it.minor_units)}</span><span>${badge}</span></div></li>`;
                })
                .join("")}
            </ul>
          </div>`
        )
        .join("")
    : `<div class="muted small">No orders placed yet.</div>`;
}

async function loadFriends() {
  const guard = document.getElementById("friendsAuthGuard");
  const content = document.getElementById("friendsContent");
  if (!state.activeUserId || state.role !== "user") {
    guard.innerHTML = loginGuardHtml("Friends");
    guard.classList.remove("hidden");
    content.classList.add("hidden");
    return;
  }
  guard.classList.add("hidden");
  content.classList.remove("hidden");

  const rows = await api(`/api/users/${state.activeUserId}/friends`);
  const wrap = document.getElementById("friendsList");
  if (!rows.length) {
    wrap.innerHTML = `<div class="muted small">No friends or pending requests yet.</div>`;
    return;
  }
  wrap.innerHTML = rows
    .map((f) => {
      let actions = `<button class="btn-sm btn-danger" onclick="removeFriend(${f.other_user_id})">Remove</button>`;
      if (f.status === "pending" && f.direction === "incoming") {
        actions = `
          <button class="btn-sm btn-sale" onclick="acceptFriend(${f.other_user_id})">Accept</button>
          <button class="btn-sm btn-danger" onclick="removeFriend(${f.other_user_id})">Decline</button>
        `;
      }
      return `
        <div class="list-row">
          <div>
            <strong>Member #${f.other_user_id}</strong> <span class="muted small">(${esc(f.other_country)})</span>
            <div class="muted small">Status: <span class="tag-chip">${esc(f.status)}</span> (${esc(f.direction)})</div>
          </div>
          <div class="card-actions">${actions}</div>
        </div>
      `;
    })
    .join("");
}

async function acceptFriend(otherId) {
  await api(`/api/users/${state.activeUserId}/friends/${otherId}`, {
    method: "PUT",
    body: JSON.stringify({ status: "accepted" }),
  });
  toast("Friend request accepted!");
  await Promise.all([loadFriends(), loadAuthSession()]);
}

async function removeFriend(otherId) {
  await api(`/api/users/${state.activeUserId}/friends/${otherId}`, { method: "DELETE" });
  toast("Friendship removed.");
  await Promise.all([loadFriends(), loadAuthSession()]);
}

async function loadPublisherStudio() {
  const guard = document.getElementById("publisherAuthGuard");
  const content = document.getElementById("publisherStudioContent");
  if (!state.activeUserId || state.role !== "publisher") {
    guard.innerHTML = `
      <h3>Publisher Access Required</h3>
      <p class="muted">Sign in with a Publisher account to publish titles, manage discounts, and create achievements.</p>
      <div class="card-actions mt-md">
        <button class="btn btn-primary" onclick="openModalWithRole('login', 'publisher')">Publisher Login</button>
        <button class="btn btn-secondary" onclick="openModalWithRole('register', 'publisher')">Register Studio</button>
      </div>
    `;
    guard.classList.remove("hidden");
    content.classList.add("hidden");
    return;
  }

  guard.classList.add("hidden");
  content.classList.remove("hidden");
  document.getElementById("publisherStudioTitle").textContent = `Publisher Studio — ${state.publisherName || "Studio"}`;
  document.getElementById("publishingStudioName").textContent = state.publisherName || "Studio";

  const games = await api("/api/publisher/games");
  const list = document.getElementById("publisherGamesList");
  const opts = games.map((g) => `<option value="${g.game_id}">${esc(g.title)}</option>`).join("");
  document.getElementById("manageSaleGameSelect").innerHTML = opts || `<option value="">No games published yet</option>`;
  document.getElementById("manageAchGameSelect").innerHTML = opts || `<option value="">No games published yet</option>`;

  if (!games.length) {
    list.innerHTML = `<div class="muted small">You have not published any games yet. Use the form below to publish your first title!</div>`;
    return;
  }
  list.innerHTML = games
    .map(
      (g) => `
      <div class="list-row">
        <div class="lib-item-left">
          <div class="lib-thumb" style="background-image:url('${gameBannerUrl(g.game_id, g.title)}')"></div>
          <div>
            <strong>${esc(g.title)}</strong> <span class="muted small">by ${esc(g.developer_name)}</span>
            <div class="muted small mt-xs">
              Price: <strong>${money(g.effective_price)}</strong>
              ${g.discount_pct > 0 ? `(<span style="color:var(--sale)">-${g.discount_pct}% ${esc(g.sale_title)}</span>)` : ""} ·
              Players: ${g.owners_count} · Achievements: ${g.achievement_count}
            </div>
          </div>
        </div>
        <div class="card-actions">
          <button class="btn-sm btn-secondary" onclick="openGameDetail(${g.game_id})">Preview</button>
          <button class="btn-sm btn-danger" onclick="deletePublisherGame(${g.game_id}, '${esc(g.title)}')">Delete</button>
        </div>
      </div>
    `
    )
    .join("");
}

async function deletePublisherGame(gameId, title) {
  try {
    await api(`/api/games/${gameId}`, { method: "DELETE" });
    toast(`Deleted "${title}".`);
    await Promise.all([loadGames(), loadPublisherStudio(), loadAuthSession()]);
  } catch (err) {
    toast(err.message, true);
  }
}

async function loadDbTables() {
  const guard = document.getElementById("adminAuthGuard");
  const content = document.getElementById("dbContent");
  if (!state.activeUserId || state.role !== "admin") {
    guard.innerHTML = `
      <h3>Platform Admin Access Required</h3>
      <p class="muted">Only the Platform Admin can inspect database tables and run read-only queries.</p>
      <div class="card-actions mt-md">
        <button class="btn btn-primary" onclick="openModalWithRole('login', 'admin')">Platform Admin Login</button>
      </div>
    `;
    guard.classList.remove("hidden");
    content.classList.add("hidden");
    return;
  }
  guard.classList.add("hidden");
  content.classList.remove("hidden");

  state.dbTables = await api("/api/db/tables");
  const list = document.getElementById("dbTablesList");
  list.innerHTML = state.dbTables
    .map(
      (t) => `
      <button class="db-table-btn ${t.table_name === state.selectedDbTable ? "active" : ""}" data-table="${t.table_name}" onclick="inspectTable('${t.table_name}')">
        <span>${t.table_name}</span>
        <span class="badge">${t.row_count}</span>
      </button>`
    )
    .join("");
  await inspectTable(state.selectedDbTable);
}

async function inspectTable(tableName) {
  state.selectedDbTable = tableName;
  document.querySelectorAll(".db-table-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.table === tableName);
  });
  const tblMeta = state.dbTables.find((t) => t.table_name === tableName);
  const data = await api(`/api/db/tables/${tableName}`);
  document.getElementById("selectedTableTitle").textContent = data.table_name;
  document.getElementById("selectedTableMeta").textContent = `${data.rows.length} rows shown · ${data.columns.length} columns`;
  document.getElementById("tableColumnsChips").innerHTML = tblMeta
    ? tblMeta.columns
        .map(
          (c) =>
            `<span class="col-chip">${c.column_key === "PRI" ? '<span class="pk">PK</span> ' : ""}${esc(c.column_name)} <span class="muted">${esc(c.column_type)}</span></span>`
        )
        .join("")
    : "";
  renderResultTable(document.getElementById("tableRowsWrap"), data.columns, data.rows);
}

function renderResultTable(container, columns, rows) {
  if (!rows.length) {
    container.innerHTML = `<div class="muted small" style="padding:12px;">0 rows returned.</div>`;
    return;
  }
  container.innerHTML = `
    <table>
      <thead><tr>${columns.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead>
      <tbody>
        ${rows
          .map(
            (r) =>
              `<tr>${columns
                .map((c) => `<td>${r[c] === null ? '<span class="muted">NULL</span>' : esc(r[c])}</td>`)
                .join("")}</tr>`
          )
          .join("")}
      </tbody>
    </table>
  `;
}

function setLoginRole(role) {
  document.getElementById("loginAccountType").value = role;
  document.querySelectorAll("#loginRoleToggle .role-opt").forEach((b) => {
    b.classList.toggle("active", b.dataset.role === role);
  });
  const submitBtn = document.getElementById("loginSubmitBtn");
  const hintEl = document.getElementById("loginHintText");
  const idInput = document.getElementById("loginIdentifierInput");
  if (role === "publisher") {
    submitBtn.textContent = "Login as Publisher";
    idInput.placeholder = "Publisher Username (e.g. valve_pub)";
    hintEl.innerHTML = `Demo Publishers: <code>valve_pub</code>, <code>cdpr_pub</code>, <code>supergiant_pub</code> · Password: <code>password123</code>`;
  } else if (role === "admin") {
    submitBtn.textContent = "Login as Platform Admin";
    idInput.placeholder = "Admin Username (e.g. admin)";
    hintEl.innerHTML = `Demo Platform Admin: <code>admin</code> · Password: <code>password123</code>`;
  } else {
    submitBtn.textContent = "Login as User";
    idInput.placeholder = "Username or Member ID (e.g. 1)";
    hintEl.innerHTML = `Demo User IDs: <code>1</code> to <code>6</code> · Password: <code>password123</code>`;
  }
}

function setRegisterRole(role) {
  document.getElementById("registerAccountType").value = role;
  document.querySelectorAll("#registerRoleToggle .role-opt").forEach((b) => {
    b.classList.toggle("active", b.dataset.role === role);
  });
  const isPub = role === "publisher";
  document.getElementById("registerUserFields").classList.toggle("hidden", isPub);
  document.getElementById("registerPublisherFields").classList.toggle("hidden", !isPub);
  document.getElementById("regPublisherName").required = isPub;
  document.getElementById("registerSubmitBtn").textContent = isPub ? "Create Publisher Account" : "Create User Account";
}

function openModalWithRole(mode, role) {
  if (mode === "login") {
    setLoginRole(role);
    openModal("loginModal");
  } else {
    setRegisterRole(role);
    openModal("registerModal");
  }
}

async function refreshUserData() {
  await loadAuthSession();
  await Promise.all([
    loadGames(),
    loadLibrary(),
    loadWishlist(),
    loadWalletAndOrders(),
    loadFriends(),
    loadPublisherStudio(),
  ]);
}

function bindEvents() {
  document.getElementById("navTabs").addEventListener("click", (e) => {
    const btn = e.target.closest(".nav-btn");
    if (!btn) return;
    switchTab(btn.dataset.tab);
  });

  document.getElementById("loginRoleToggle").addEventListener("click", (e) => {
    const btn = e.target.closest(".role-opt");
    if (btn) setLoginRole(btn.dataset.role);
  });

  document.getElementById("registerRoleToggle").addEventListener("click", (e) => {
    const btn = e.target.closest(".role-opt");
    if (btn) setRegisterRole(btn.dataset.role);
  });

  ["searchInput", "filterTag", "filterPublisher", "filterDeveloper", "filterOnSale"].forEach((id) => {
    document.getElementById(id).addEventListener("input", loadGames);
    document.getElementById(id).addEventListener("change", loadGames);
  });

  document.getElementById("resetFiltersBtn").addEventListener("click", () => {
    document.getElementById("searchInput").value = "";
    document.getElementById("filterTag").value = "";
    document.getElementById("filterPublisher").value = "";
    document.getElementById("filterDeveloper").value = "";
    document.getElementById("filterOnSale").checked = false;
    loadGames();
  });

  document.querySelectorAll("[data-close]").forEach((el) => {
    el.addEventListener("click", () => closeModal(el.dataset.close));
  });

  document.getElementById("regionPickerBtn").addEventListener("click", (e) => {
    e.stopPropagation();
    toggleRegionDialog();
  });

  document.getElementById("closeRegionDialogBtn").addEventListener("click", () => toggleRegionDialog(false));

  document.getElementById("regionSearchInput").addEventListener("input", (e) => {
    renderRegionOptions(e.target.value);
  });

  document.getElementById("regionDialog").addEventListener("click", (e) => {
    e.stopPropagation();
  });

  document.addEventListener("click", () => {
    toggleRegionDialog(false);
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") toggleRegionDialog(false);
  });

  document.getElementById("registerRegionSelect").addEventListener("change", syncRegisterWalletPlaceholder);

  document.getElementById("openCartBtn").addEventListener("click", () => {
    renderCartModal();
    openModal("cartModal");
  });

  document.getElementById("openLoginBtn").addEventListener("click", () => openModal("loginModal"));
  document.getElementById("openRegisterBtn").addEventListener("click", () => {
    const regSel = document.getElementById("registerRegionSelect");
    if (regSel && state.activeRegion?.region_id) {
      regSel.value = String(state.activeRegion.region_id);
      syncRegisterWalletPlaceholder();
    }
    openModal("registerModal");
  });

  document.getElementById("loginForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      const res = await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify(Object.fromEntries(fd.entries())),
      });
      closeModal("loginModal");
      e.target.reset();
      setLoginRole(res.role);
      state.cart = [];
      updateCartBadge();
      await refreshUserData();
      showAccountBanner(res, "Logged in!");
      toast(`Logged in as ${res.username} (${res.role})!`);
    } catch (err) {
      toast(err.message, true);
    }
  });

  document.getElementById("registerForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = {
      ...Object.fromEntries(fd.entries()),
      input_in_active_currency: true,
    };
    try {
      const res = await api("/api/auth/register", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      closeModal("registerModal");
      e.target.reset();
      setRegisterRole("user");
      state.cart = [];
      updateCartBadge();
      await Promise.all([loadMeta(), refreshUserData()]);
      showAccountBanner(res, "Account Created!");
      toast(`Account created! Welcome, ${res.username}.`);
    } catch (err) {
      toast(err.message, true);
    }
  });

  document.getElementById("logoutBtn").addEventListener("click", async () => {
    await api("/api/auth/logout", { method: "POST" });
    state.cart = [];
    state.library = [];
    state.orders = [];
    state.pendingRefundGameId = null;
    if (state.playTimerInterval) {
      clearInterval(state.playTimerInterval);
      state.playTimerInterval = null;
    }
    state.dbTables = [];
    closeModal("refundModal");
    updateCartBadge();
    document.getElementById("loginIdNotice").classList.add("hidden");
    document.getElementById("dbTablesList").innerHTML = "";
    document.getElementById("tableColumnsChips").innerHTML = "";
    document.getElementById("tableRowsWrap").innerHTML = "";
    document.getElementById("sqlResultWrap").innerHTML = "";
    await refreshUserData();
    toast("Logged out.");
  });

  document.querySelectorAll('input[name="payMethod"]').forEach((el) => {
    el.addEventListener("change", renderPaymentMethod);
  });

  document.getElementById("refundForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!state.activeUserId || !state.pendingRefundGameId) return;
    const gameId = state.pendingRefundGameId;
    const reason = document.getElementById("refundReasonSelect").value;
    try {
      const res = await api(`/api/users/${state.activeUserId}/library/${gameId}/refund`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      });
      state.pendingRefundGameId = null;
      state.walletBalance = Number(res.wallet_balance);
      document.getElementById("walletChip").textContent = moneyExact(state.walletBalance);
      document.getElementById("walletBig").textContent = moneyExact(state.walletBalance);
      closeModal("refundModal");
      closeModal("gameModal");
      toast(`Refunded "${res.game_title}" (+${moneyExact(res.refund_amount)} credited to Wallet).`);
      await refreshUserData();
    } catch (err) {
      toast(err.message, true);
    }
  });

  document.getElementById("checkoutBtn").addEventListener("click", async () => {
    if (!state.activeUserId || state.role !== "user") {
      closeModal("cartModal");
      openModal("loginModal");
      return toast("Please log in as a User to complete your purchase.", true);
    }
    if (!state.cart.length) return toast("Cart is empty.", true);
    try {
      const res = await api(`/api/users/${state.activeUserId}/checkout`, {
        method: "POST",
        body: JSON.stringify({
          game_ids: state.cart.map((g) => g.game_id),
          payment_method: "SAUNA Wallet",
        }),
      });
      state.cart = [];
      state.walletBalance = Number(res.wallet_balance);
      document.getElementById("walletChip").textContent = moneyExact(state.walletBalance);
      document.getElementById("walletBig").textContent = moneyExact(state.walletBalance);
      updateCartBadge();
      closeModal("cartModal");
      toast(`Purchase complete! Order #${res.order_id} (${moneyExact(res.total_amount)})`);
      await refreshUserData();
    } catch (err) {
      toast(err.message, true);
    }
  });

  document.getElementById("depositForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const amount = document.getElementById("depositAmount").value;
    try {
      const res = await api(`/api/users/${state.activeUserId}/wallet/deposit`, {
        method: "POST",
        body: JSON.stringify({ amount, input_in_active_currency: true }),
      });
      document.getElementById("depositAmount").value = "";
      const reg = state.activeRegion || { symbol: "₹", minor_units: 2 };
      toast(`Deposited ${formatCurrencyNumber(res.deposited_display_amount, reg.symbol, reg.minor_units)} to Wallet!`);
      await Promise.all([loadAuthSession(), loadWalletAndOrders()]);
    } catch (err) {
      toast(err.message, true);
    }
  });

  document.getElementById("addFriendForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const friendId = document.getElementById("friendMemberIdInput").value;
    if (!friendId) return;
    try {
      await api(`/api/users/${state.activeUserId}/friends`, {
        method: "POST",
        body: JSON.stringify({ friend_id: Number(friendId) }),
      });
      document.getElementById("friendMemberIdInput").value = "";
      toast(`Friend request sent to Member #${friendId}!`);
      await loadFriends();
    } catch (err) {
      toast(err.message, true);
    }
  });

  document.getElementById("createGameForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = {
      title: fd.get("title"),
      description: fd.get("description"),
      release_date: fd.get("release_date") || null,
      base_price: fd.get("base_price"),
      developer_id: fd.get("developer_id"),
      age_rating: fd.get("age_rating"),
      tag_ids: fd.getAll("tag_ids").map(Number),
    };
    try {
      await api("/api/games", { method: "POST", body: JSON.stringify(payload) });
      e.target.reset();
      toast("New game published to catalog!");
      await Promise.all([loadGames(), loadPublisherStudio(), loadAuthSession()]);
    } catch (err) {
      toast(err.message, true);
    }
  });

  document.getElementById("createDevForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await api("/api/developers", { method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(e.target))) });
      e.target.reset();
      toast("Developer studio added!");
      await loadMeta();
    } catch (err) {
      toast(err.message, true);
    }
  });

  document.getElementById("createTagForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await api("/api/tags", { method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(e.target))) });
      e.target.reset();
      toast("Tag added!");
      await loadMeta();
    } catch (err) {
      toast(err.message, true);
    }
  });

  document.getElementById("createSaleForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = {
      title: fd.get("title"),
      start_date: fd.get("start_date").replace("T", " ") + ":00",
      end_date: fd.get("end_date").replace("T", " ") + ":00",
    };
    try {
      await api("/api/sales", { method: "POST", body: JSON.stringify(payload) });
      e.target.reset();
      toast("Sale event created!");
      await loadMeta();
    } catch (err) {
      toast(err.message, true);
    }
  });

  document.getElementById("addSaleItemForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      await api(`/api/sales/${fd.get("sale_id")}/items`, {
        method: "POST",
        body: JSON.stringify({ game_id: fd.get("game_id"), discount_pct: fd.get("discount_pct") }),
      });
      toast("Discount applied to game!");
      await Promise.all([loadMeta(), loadGames(), loadWishlist(), loadPublisherStudio()]);
    } catch (err) {
      toast(err.message, true);
    }
  });

  document.getElementById("createAchForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      await api("/api/achievements", {
        method: "POST",
        body: JSON.stringify({
          game_id: fd.get("game_id"),
          name: fd.get("name"),
          description: fd.get("description"),
          is_hidden: fd.get("is_hidden") === "on",
        }),
      });
      e.target.reset();
      toast("Achievement added!");
      await Promise.all([loadGames(), loadPublisherStudio()]);
    } catch (err) {
      toast(err.message, true);
    }
  });

  document.getElementById("runSqlBtn").addEventListener("click", async () => {
    const sql = document.getElementById("sqlInput").value;
    try {
      const res = await api("/api/db/query", { method: "POST", body: JSON.stringify({ sql }) });
      renderResultTable(document.getElementById("sqlResultWrap"), res.columns, res.rows);
    } catch (err) {
      document.getElementById("sqlResultWrap").innerHTML = `<div style="padding:12px;color:var(--danger);">${esc(err.message)}</div>`;
    }
  });

  document.querySelectorAll(".sql-preset").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.getElementById("sqlInput").value = btn.dataset.sql;
      document.getElementById("runSqlBtn").click();
    });
  });
}

async function init() {
  bindEvents();
  await loadMeta();
  await refreshUserData();
}

init().catch((err) => toast(err.message, true));

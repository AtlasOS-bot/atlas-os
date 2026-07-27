/*
 * Atlas v21 - Module 8: dashboard interactivity.
 *
 * DELIBERATELY THIN. This file never classifies a market, never
 * derives a demand tag, never resolves an image priority, and never
 * formats a relative timestamp - all of that already happened in
 * Python (collector_intelligence/dashboard_view.py) when this page
 * was generated. This file only:
 *   - fetches/writes personal data (hearts, notes, overrides, manual
 *     items) via Supabase's REST API
 *   - toggles DOM state (heart icon, drawer open/close)
 *   - handles form submission
 *   - does client-side search/filter/sort over already-rendered rows
 *
 * =====================================================================
 * SECURITY NOTE - READ BEFORE ENABLING WRITES IN PRODUCTION
 * =====================================================================
 * This uses Supabase's ANON key only - never a service-role key or
 * any credential capable of bypassing Row Level Security. That is
 * correct and required, but it is NOT sufficient on its own: whether
 * these writes are actually safe depends entirely on the RLS policies
 * attached to the tables below in your live Supabase project, which
 * this codebase cannot see or verify (see the commented-out policy
 * recommendations in db/migrations/0002_create_dashboard_user_data.sql).
 * Until you have confirmed appropriate policies are in place, treat
 * every write in this file as NOT VERIFIED SECURE beyond personal,
 * local use - do not deploy this publicly without reviewing that.
 * =====================================================================
 */

const SUPABASE_URL = "https://fdvgndlwajhjyxttfiht.supabase.co";
const SUPABASE_ANON_KEY = "sb_publishable_GTuwSWGgSpmZScE4T4Beww_DQEDZ839";

const TABLES = {
  overrides: "opportunity_user_overrides",
  overrideHistory: "opportunity_override_history",
  notes: "opportunity_notes",
  heartedItems: "hearted_items",
  heartedItemNotes: "hearted_item_notes",
};

// ---------------------------------------------------------------
// Supabase REST helpers
// ---------------------------------------------------------------

async function sb(method, table, { query = "", body = null, prefer = null } = {}) {
  const headers = {
    apikey: SUPABASE_ANON_KEY,
    Authorization: `Bearer ${SUPABASE_ANON_KEY}`,
    "Content-Type": "application/json",
  };
  if (prefer) headers["Prefer"] = prefer;

  const response = await fetch(`${SUPABASE_URL}/rest/v1/${table}${query}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`Supabase ${method} ${table} failed (${response.status}): ${text}`);
  }

  const text = await response.text();
  return text ? JSON.parse(text) : null;
}

// ---------------------------------------------------------------
// Safe URL validation (mirrors Module 5's normalize_url: http/https
// only, rejects javascript:/data:/file:/anything else)
// ---------------------------------------------------------------

const ALLOWED_URL_SCHEMES = new Set(["http:", "https:"]);

function isSafeUrl(value) {
  if (!value) return true; // empty is allowed (optional field)
  try {
    const parsed = new URL(value);
    return ALLOWED_URL_SCHEMES.has(parsed.protocol);
  } catch (err) {
    return false;
  }
}

function rejectUnsafeUrlFields(form, fieldNames) {
  for (const name of fieldNames) {
    const field = form.elements.namedItem(name);
    if (field && field.value && !isSafeUrl(field.value)) {
      return `"${field.value}" is not a safe URL (only http/https links are allowed).`;
    }
  }
  return null;
}

// ---------------------------------------------------------------
// Heart / unheart
// ---------------------------------------------------------------

async function toggleHeart(button) {
  const opportunityId = button.dataset.opportunityId;
  const currentlyHearted = button.getAttribute("aria-pressed") === "true";

  // Optimistic UI update.
  setHeartButtonState(button, !currentlyHearted);

  try {
    if (currentlyHearted) {
      await sb("DELETE", TABLES.heartedItems, {
        query: `?opportunity_id=eq.${encodeURIComponent(opportunityId)}`,
      });
    } else {
      await sb("POST", TABLES.heartedItems, {
        body: { opportunity_id: opportunityId, status: "SAVED" },
        prefer: "return=minimal",
      });
    }
  } catch (err) {
    // Roll back on failure.
    setHeartButtonState(button, currentlyHearted);
    console.error("Failed to update hearted state:", err);
    alert("Could not save - please try again.");
  }
}

function setHeartButtonState(button, hearted) {
  button.setAttribute("aria-pressed", hearted ? "true" : "false");
  button.setAttribute("aria-label", hearted ? "Remove from Hearted Items" : "Save to Hearted Items");
  button.classList.toggle("heart-btn--hearted", hearted);
  button.classList.toggle("heart-btn--not-hearted", !hearted);
  const glyph = button.querySelector("span[aria-hidden]");
  if (glyph) glyph.textContent = hearted ? "♥" : "♡";
  const card = button.closest(".card");
  if (card) card.dataset.hearted = hearted ? "true" : "false";
}

async function unheartFromHeartedItemsPage(button) {
  const heartedItemId = button.dataset.heartedItemId;
  if (!confirm("Remove this item from Hearted Items?")) return;

  try {
    await sb("DELETE", TABLES.heartedItems, {
      query: `?id=eq.${encodeURIComponent(heartedItemId)}`,
    });
    const row = button.closest(".hearted-row");
    if (row) row.remove();
  } catch (err) {
    console.error("Failed to remove hearted item:", err);
    alert("Could not remove - please try again.");
  }
}

async function toggleArchive(button) {
  const heartedItemId = button.dataset.heartedItemId;
  const row = button.closest(".hearted-row");
  const currentlyArchived = row.dataset.archived === "true";

  try {
    await sb("PATCH", TABLES.heartedItems, {
      query: `?id=eq.${encodeURIComponent(heartedItemId)}`,
      body: { archived_at: currentlyArchived ? null : new Date().toISOString() },
      prefer: "return=minimal",
    });
    row.dataset.archived = currentlyArchived ? "false" : "true";
    button.textContent = currentlyArchived ? "Archive" : "Unarchive";
  } catch (err) {
    console.error("Failed to update archive state:", err);
    alert("Could not update - please try again.");
  }
}

// ---------------------------------------------------------------
// Drawer (notes / edit / manual item) - a single shared panel
// ---------------------------------------------------------------

function openDrawer() {
  const drawer = document.getElementById("drawer");
  if (!drawer) return;
  drawer.hidden = false;
  drawer.setAttribute("aria-hidden", "false");
  const focusable = drawer.querySelector("input, textarea, select, button");
  if (focusable) focusable.focus();
  document.addEventListener("keydown", closeDrawerOnEscape);
}

function closeDrawer() {
  const drawer = document.getElementById("drawer");
  if (!drawer) return;
  drawer.hidden = true;
  drawer.setAttribute("aria-hidden", "true");
  document.removeEventListener("keydown", closeDrawerOnEscape);
}

function closeDrawerOnEscape(event) {
  if (event.key === "Escape") closeDrawer();
}

// ---------------------------------------------------------------
// Notes
// ---------------------------------------------------------------

async function openNotesDrawer(opportunityId, heartedItemId) {
  const drawerBody = document.getElementById("drawer-body");
  drawerBody.innerHTML = `
    <div class="drawer-notes" aria-label="My Notes">
      <h2>My Notes</h2>
      <ul id="notes-list" class="notes-list"><li>Loading...</li></ul>
      <form id="note-form">
        <label for="note-body" class="sr-only">Add a note</label>
        <textarea id="note-body" name="body" rows="2" placeholder="Add a note..." required></textarea>
        <button type="submit">Add note</button>
      </form>
    </div>`;
  openDrawer();

  const table = opportunityId ? TABLES.notes : TABLES.heartedItemNotes;
  const filterField = opportunityId ? "opportunity_id" : "hearted_item_id";
  const filterValue = opportunityId || heartedItemId;

  const notesList = document.getElementById("notes-list");

  async function refresh() {
    const notes = await sb("GET", table, {
      query: `?${filterField}=eq.${encodeURIComponent(filterValue)}&order=updated_at.desc`,
    });
    notesList.innerHTML = notes.length
      ? notes.map(renderNoteItem).join("")
      : "<li>No notes yet.</li>";
    wireNoteButtons(table, filterField, filterValue, refresh);
  }

  document.getElementById("note-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const body = event.target.elements.body.value.trim();
    if (!body) return;
    await sb("POST", table, {
      body: { [filterField]: filterValue, body },
      prefer: "return=minimal",
    });
    event.target.reset();
    await refresh();
  });

  await refresh();
}

function renderNoteItem(note) {
  const span = document.createElement("span");
  span.textContent = note.body; // textContent, never innerHTML - safe from injection
  const edited = note.updated_at !== note.created_at;
  return `<li data-note-id="${note.id}">
    <p class="note-body">${span.innerHTML}</p>
    <span class="note-meta">${edited ? "Edited" : "Added"} ${new Date(note.updated_at).toLocaleString()}</span>
    <button type="button" class="note-delete" data-note-id="${note.id}">Delete</button>
  </li>`;
}

function wireNoteButtons(table, filterField, filterValue, refresh) {
  document.querySelectorAll(".note-delete").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!confirm("Delete this note?")) return;
      await sb("DELETE", table, { query: `?id=eq.${encodeURIComponent(button.dataset.noteId)}` });
      await refresh();
    });
  });
}

// ---------------------------------------------------------------
// Overrides
// ---------------------------------------------------------------

// No server regenerates these static pages on demand, so a write must
// patch the DOM directly rather than reload (a reload would just
// re-fetch the same pre-rendered file from disk, unchanged). These
// two lookup tables mirror dashboard_render.py's own CSS class maps -
// they select between Atlas's already-computed values, never derive
// new ones.
const STRENGTH_BADGE_CLASS = { STRONG: "strong", MEDIUM: "medium", WEAK: "weak", UNKNOWN: "unknown" };
const TREND_SYMBOL = { RISING: "↑", STABLE: "→", FALLING: "↓", UNKNOWN: "?" };

function titleCase(word) {
  return word ? word.charAt(0) + word.slice(1).toLowerCase() : word;
}

function applyOverrideToCard(opportunityId, payload, atlasValues) {
  const card = document.querySelector(`.card[data-opportunity-id="${CSS.escape(opportunityId)}"]`);
  if (!card) return;

  const strength = payload.market_strength_override || atlasValues.market_strength || "UNKNOWN";
  const trend = payload.market_trend_override || atlasValues.market_trend || "UNKNOWN";

  const strengthBadge = card.querySelector('[data-role="strength-badge"]');
  if (strengthBadge) {
    strengthBadge.textContent = strength;
    strengthBadge.className = `badge badge--${STRENGTH_BADGE_CLASS[strength] || "unknown"}`;
    strengthBadge.setAttribute("aria-label", `Market strength: ${titleCase(strength)}`);
  }

  const trendValue = card.querySelector('[data-role="trend-value"]');
  if (trendValue && trendValue.firstChild) {
    trendValue.firstChild.nodeValue = `${trend} `;
    const symbolEl = trendValue.querySelector('[data-role="trend-symbol"]');
    if (symbolEl) symbolEl.textContent = TREND_SYMBOL[trend] || "?";
  }

  const badgesContainer = card.querySelector('[data-role="strength-badges"]');
  const hasOverride = Boolean(payload.market_strength_override || payload.market_trend_override);
  if (badgesContainer) {
    let overrideBadge = badgesContainer.querySelector(".badge--override");
    if (hasOverride && !overrideBadge) {
      overrideBadge = document.createElement("span");
      overrideBadge.className = "badge badge--override";
      overrideBadge.setAttribute("role", "status");
      overrideBadge.textContent = "Manual override";
      badgesContainer.appendChild(overrideBadge);
    } else if (!hasOverride && overrideBadge) {
      overrideBadge.remove();
    }
  }
}

async function openOverrideDrawer(card) {
  const opportunityId = card.dataset.opportunityId;
  const atlasValues = JSON.parse(card.dataset.atlasValues || "{}");

  const drawerBody = document.getElementById("drawer-body");
  drawerBody.innerHTML = `
    <form id="override-form" class="drawer-form" aria-label="Manual market override">
      <h2>Manual override</h2>
      <p class="atlas-value-note">Atlas assessment: <span id="ov-atlas-strength">${atlasValues.market_strength || "Unknown"}</span></p>

      <label for="ov-market-strength">Market strength</label>
      <select id="ov-market-strength" name="market_strength_override">
        <option value="">Use Atlas assessment</option>
        <option value="STRONG">Strong</option>
        <option value="MEDIUM">Medium</option>
        <option value="WEAK">Weak</option>
        <option value="UNKNOWN">Unknown</option>
      </select>

      <label for="ov-market-trend">Market trend</label>
      <select id="ov-market-trend" name="market_trend_override">
        <option value="">Use Atlas assessment</option>
        <option value="RISING">Rising</option>
        <option value="STABLE">Stable</option>
        <option value="FALLING">Falling</option>
        <option value="UNKNOWN">Unknown</option>
      </select>

      <label for="ov-reason">Reason (optional)</label>
      <textarea id="ov-reason" name="reason" rows="2"></textarea>

      <div class="form-actions">
        <button type="submit">Save override</button>
        <button type="button" id="ov-reset">Reset to Atlas</button>
        <button type="button" data-action="cancel-drawer">Cancel</button>
      </div>
    </form>`;
  openDrawer();

  const existing = await sb("GET", TABLES.overrides, {
    query: `?opportunity_id=eq.${encodeURIComponent(opportunityId)}&limit=1`,
  });
  const current = existing && existing[0];

  const form = document.getElementById("override-form");
  if (current) {
    form.elements.market_strength_override.value = current.market_strength_override || "";
    form.elements.market_trend_override.value = current.market_trend_override || "";
    form.elements.reason.value = current.reason || "";
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    await saveOverride(opportunityId, form, atlasValues, current);
    closeDrawer();
  });

  document.getElementById("ov-reset").addEventListener("click", async () => {
    try {
      if (current) {
        await sb("DELETE", TABLES.overrides, { query: `?opportunity_id=eq.${encodeURIComponent(opportunityId)}` });
        if (current.market_strength_override) {
          await recordOverrideHistory(opportunityId, "market_strength", atlasValues.market_strength, current.market_strength_override, null, "Reset to Atlas assessment");
        }
        if (current.market_trend_override) {
          await recordOverrideHistory(opportunityId, "market_trend", atlasValues.market_trend, current.market_trend_override, null, "Reset to Atlas assessment");
        }
      }
      applyOverrideToCard(opportunityId, {}, atlasValues);
      closeDrawer();
    } catch (err) {
      console.error("Failed to reset override:", err);
      alert("Could not reset - please try again.");
    }
  });
}

async function saveOverride(opportunityId, form, atlasValues, previous) {
  const payload = {
    opportunity_id: opportunityId,
    market_strength_override: form.elements.market_strength_override.value || null,
    market_trend_override: form.elements.market_trend_override.value || null,
    reason: form.elements.reason.value || null,
    updated_at: new Date().toISOString(),
  };

  if (previous) {
    await sb("PATCH", TABLES.overrides, {
      query: `?opportunity_id=eq.${encodeURIComponent(opportunityId)}`,
      body: payload,
      prefer: "return=minimal",
    });
  } else {
    await sb("POST", TABLES.overrides, { body: payload, prefer: "return=minimal" });
  }

  if (payload.market_strength_override !== (previous && previous.market_strength_override)) {
    await recordOverrideHistory(
      opportunityId, "market_strength", atlasValues.market_strength,
      previous && previous.market_strength_override, payload.market_strength_override, payload.reason,
    );
  }
  if (payload.market_trend_override !== (previous && previous.market_trend_override)) {
    await recordOverrideHistory(
      opportunityId, "market_trend", atlasValues.market_trend,
      previous && previous.market_trend_override, payload.market_trend_override, payload.reason,
    );
  }

  applyOverrideToCard(opportunityId, payload, atlasValues);
}

async function recordOverrideHistory(opportunityId, fieldName, atlasValue, previousValue, newValue, reason) {
  await sb("POST", TABLES.overrideHistory, {
    body: {
      opportunity_id: opportunityId,
      field_name: fieldName,
      atlas_value_snapshot: atlasValue,
      previous_override_value: previousValue,
      new_override_value: newValue,
      reason,
    },
    prefer: "return=minimal",
  });
}

// ---------------------------------------------------------------
// Hearted Items page: DOM patching after a write, so a manual item
// add/edit shows up immediately without needing to re-run the Python
// generator. Only formats already-known values (product name, price,
// tags the user themselves typed) - never derives a classification.
// ---------------------------------------------------------------

const STATUS_LABELS = {
  SAVED: "Saved", APPROVED: "Approved", DENIED: "Denied",
  PURCHASED: "Purchased", SOLD: "Sold", ARCHIVED: "Archived",
};

function formatMoney(value) {
  if (value === null || value === undefined || value === "") return "Unknown";
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return "Unknown";
  return Number.isInteger(numeric)
    ? `$${numeric.toLocaleString()}`
    : `$${numeric.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value == null ? "" : String(value);
  return div.innerHTML;
}

function findHeartedRow(id) {
  return document.querySelector(`.hearted-row[data-hearted-item-id="${CSS.escape(id)}"]`);
}

function buildHeartedRowHtml(item) {
  const marketStrength = item.market_strength || "UNKNOWN";
  const strengthClass = STRENGTH_BADGE_CLASS[marketStrength] || "unknown";
  const hasImage = Boolean(item.image_url);
  const tags = item.tags || [];
  const tagsHtml = tags.length
    ? `<ul class="demand-tags" aria-label="Tags">${tags.map((t) => `<li class="tag">${escapeHtml(t)}</li>`).join("")}</ul>`
    : "";
  const links = [];
  if (item.product_link) links.push(`<a class="action-link" href="${escapeHtml(item.product_link)}" target="_blank" rel="noopener noreferrer">View Product</a>`);
  if (item.ebay_sold_link) links.push(`<a class="action-link" href="${escapeHtml(item.ebay_sold_link)}" target="_blank" rel="noopener noreferrer">eBay Sold</a>`);

  return `<article class="hearted-row" data-hearted-item-id="${escapeHtml(item.id)}"
      data-status="${escapeHtml(item.status || "SAVED")}" data-priority="${escapeHtml(item.priority || "")}"
      data-category="${escapeHtml(item.category || "")}" data-archived="false" data-is-manual="true"
      data-product-name="${escapeHtml((item.product_name || "").toLowerCase())}" data-hearted-at="${escapeHtml(item.hearted_at || new Date().toISOString())}">
    <div class="hearted-row-image">
      <img src="${escapeHtml(item.image_url || "assets/placeholder.svg")}" alt="${escapeHtml(item.product_name || "Product image")}" loading="lazy" class="${hasImage ? "" : "placeholder"}">
    </div>
    <div class="hearted-row-body">
      <div class="hearted-row-header">
        <h3>${escapeHtml(item.product_name || "Untitled item")}</h3>
        <div class="card-badges">
          <span data-role="strength-badge" class="badge badge--${strengthClass}" role="status" aria-label="Market strength: ${escapeHtml(titleCase(marketStrength))}">${escapeHtml(marketStrength)}</span>
          <span class="badge badge--manual" role="status">Manual</span>
        </div>
      </div>
      <div class="hearted-row-stats">
        <span class="stat"><span class="stat-label">Status</span><span class="stat-value" data-role="status-value">${escapeHtml(STATUS_LABELS[item.status] || item.status || "Saved")}</span></span>
        <span class="stat"><span class="stat-label">Target</span><span class="stat-value" data-role="target-price-value">${escapeHtml(formatMoney(item.target_price))}</span></span>
        <span class="stat"><span class="stat-label">Qty</span><span class="stat-value" data-role="quantity-value">${item.quantity !== null && item.quantity !== undefined ? escapeHtml(String(item.quantity)) : "—"}</span></span>
        <span class="stat"><span class="stat-label">Priority</span><span class="stat-value" data-role="priority-value">${escapeHtml(item.priority || "—")}</span></span>
      </div>
      ${tagsHtml}
      <div class="card-actions">
        ${links.join("")}
        <button type="button" class="action-btn" data-action="notes" data-hearted-item-id="${escapeHtml(item.id)}">Notes</button>
        <button type="button" class="action-btn" data-action="edit-hearted" data-hearted-item-id="${escapeHtml(item.id)}">Edit</button>
        <button type="button" class="action-btn" data-action="archive-hearted" data-hearted-item-id="${escapeHtml(item.id)}">Archive</button>
        <button type="button" class="heart-btn heart-btn--hearted" data-action="unheart" data-hearted-item-id="${escapeHtml(item.id)}" aria-pressed="true" aria-label="Remove from Hearted Items"><span aria-hidden="true">&#9829;</span></button>
      </div>
    </div>
  </article>`;
}

function ensureHeartedListSection() {
  let list = document.querySelector(".hearted-list");
  if (list) return list;
  list = document.createElement("section");
  list.className = "hearted-list";
  list.setAttribute("aria-label", "Hearted items");
  const empty = document.querySelector(".shell .empty-state");
  if (empty) empty.replaceWith(list);
  else document.querySelector(".shell").appendChild(list);
  return list;
}

function insertNewHeartedRow(item) {
  const list = ensureHeartedListSection();
  const wrapper = document.createElement("div");
  wrapper.innerHTML = buildHeartedRowHtml(item).trim();
  list.prepend(wrapper.firstElementChild);
}

function applyHeartedItemFieldsToRow(row, item, { isManual }) {
  row.dataset.status = item.status || "SAVED";
  row.dataset.priority = item.priority || "";
  row.dataset.category = item.category || "";

  const statusValue = row.querySelector('[data-role="status-value"]');
  if (statusValue) statusValue.textContent = STATUS_LABELS[item.status] || item.status || "Saved";

  const targetValue = row.querySelector('[data-role="target-price-value"]');
  if (targetValue) targetValue.textContent = formatMoney(item.target_price);

  const quantityValue = row.querySelector('[data-role="quantity-value"]');
  if (quantityValue) {
    quantityValue.textContent = item.quantity !== null && item.quantity !== undefined ? String(item.quantity) : "—";
  }

  const priorityValue = row.querySelector('[data-role="priority-value"]');
  if (priorityValue) priorityValue.textContent = item.priority || "—";

  const tags = item.tags || [];
  let tagsList = row.querySelector(".demand-tags");
  if (!tagsList && tags.length) {
    tagsList = document.createElement("ul");
    tagsList.className = "demand-tags";
    tagsList.setAttribute("aria-label", "Tags");
    row.querySelector(".hearted-row-stats").insertAdjacentElement("afterend", tagsList);
  }
  if (tagsList) {
    tagsList.innerHTML = "";
    tags.forEach((tag) => {
      const li = document.createElement("li");
      li.className = "tag";
      li.textContent = tag;
      tagsList.appendChild(li);
    });
    if (!tags.length) tagsList.remove();
  }

  if (!isManual) return;

  const heading = row.querySelector(".hearted-row-header h3");
  if (heading && heading.firstChild) heading.firstChild.nodeValue = item.product_name || "Untitled item";

  const img = row.querySelector(".hearted-row-image img");
  if (img) {
    const hasImage = Boolean(item.image_url);
    img.src = item.image_url || "assets/placeholder.svg";
    img.alt = item.product_name || "Product image";
    img.classList.toggle("placeholder", !hasImage);
  }

  const strengthBadge = row.querySelector('[data-role="strength-badge"]');
  if (strengthBadge) {
    const strength = item.market_strength || "UNKNOWN";
    strengthBadge.textContent = strength;
    strengthBadge.className = `badge badge--${STRENGTH_BADGE_CLASS[strength] || "unknown"}`;
    strengthBadge.setAttribute("aria-label", `Market strength: ${titleCase(strength)}`);
  }

  const actions = row.querySelector(".card-actions");
  actions.querySelectorAll(".action-link").forEach((a) => a.remove());
  const linkDefs = [];
  if (item.product_link) linkDefs.push(["View Product", item.product_link]);
  if (item.ebay_sold_link) linkDefs.push(["eBay Sold", item.ebay_sold_link]);
  linkDefs.reverse().forEach(([label, url]) => {
    const a = document.createElement("a");
    a.className = "action-link";
    a.href = url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = label;
    actions.insertBefore(a, actions.firstChild);
  });
}

function showToast(message) {
  let toast = document.getElementById("atlas-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "atlas-toast";
    toast.setAttribute("role", "status");
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.classList.add("visible");
  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(() => toast.classList.remove("visible"), 4000);
}

// ---------------------------------------------------------------
// Manual item form
// ---------------------------------------------------------------

// Fields that describe the *product itself*. For a manual item these are
// user-owned and editable. For an Atlas-linked hearted item these are
// derived from the opportunity and must not be edited here - only the
// collector's own fields (target price, quantity, priority, category,
// tags) are.
const MANUAL_ITEM_IDENTITY_FIELDS = [
  "product_name", "image_url", "product_link", "ebay_sold_link",
  "msrp", "last_sold_price", "market_strength",
];

function fillManualItemForm(form, item) {
  form.elements.product_name.value = item.product_name || "";
  form.elements.image_url.value = item.image_url || "";
  form.elements.product_link.value = item.product_link || "";
  form.elements.ebay_sold_link.value = item.ebay_sold_link || "";
  form.elements.msrp.value = item.msrp ?? "";
  form.elements.last_sold_price.value = item.last_sold_price ?? "";
  form.elements.market_strength.value = item.market_strength || "UNKNOWN";
  form.elements.category.value = item.category || "";
  form.elements.priority.value = item.priority || "";
  form.elements.target_price.value = item.target_price ?? "";
  form.elements.quantity.value = item.quantity ?? "";
  form.elements.tags.value = (item.tags || []).join(", ");
  const notesField = form.elements.namedItem("notes");
  if (notesField) notesField.value = "";
}

function setIdentityFieldsDisabled(form, disabled) {
  MANUAL_ITEM_IDENTITY_FIELDS.forEach((name) => {
    const field = form.elements.namedItem(name);
    if (field) field.disabled = disabled;
  });
}

function readManualItemPayload(form, { includeIdentity }) {
  const tags = form.elements.tags.value
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);

  const payload = {
    category: form.elements.category.value || null,
    priority: form.elements.priority.value || null,
    target_price: form.elements.target_price.value ? Number(form.elements.target_price.value) : null,
    quantity: form.elements.quantity.value ? Number(form.elements.quantity.value) : null,
    tags,
  };

  if (includeIdentity) {
    payload.product_name = form.elements.product_name.value.trim();
    payload.image_url = form.elements.image_url.value || null;
    payload.product_link = form.elements.product_link.value || null;
    payload.ebay_sold_link = form.elements.ebay_sold_link.value || null;
    payload.msrp = form.elements.msrp.value ? Number(form.elements.msrp.value) : null;
    payload.last_sold_price = form.elements.last_sold_price.value ? Number(form.elements.last_sold_price.value) : null;
    payload.market_strength = form.elements.market_strength.value || "UNKNOWN";
  }

  return payload;
}

function openManualItemDrawer() {
  const drawerBody = document.getElementById("drawer-body");
  drawerBody.innerHTML = document.getElementById("manual-item-form-template").innerHTML;
  openDrawer();

  const form = document.getElementById("manual-item-form");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const urlError = rejectUnsafeUrlFields(form, ["image_url", "product_link", "ebay_sold_link"]);
    if (urlError) {
      alert(urlError);
      return;
    }

    const payload = readManualItemPayload(form, { includeIdentity: true });
    payload.status = "SAVED";

    if (!payload.product_name) {
      alert("Product name is required.");
      return;
    }

    try {
      const created = await sb("POST", TABLES.heartedItems, { body: payload, prefer: "return=representation" });
      closeDrawer();
      const item = created && created[0];
      if (item) {
        if (document.getElementById("hi-search")) {
          insertNewHeartedRow(item);
          applyHeartedItemsControls();
        } else {
          showToast(`Added "${item.product_name}" to Hearted Items.`);
        }
      }
    } catch (err) {
      console.error("Failed to save manual item:", err);
      alert("Could not save - please try again.");
    }
  });
}

async function openEditHeartedItemDrawer(heartedItemId, isManual) {
  const drawerBody = document.getElementById("drawer-body");
  drawerBody.innerHTML = document.getElementById("manual-item-form-template").innerHTML;
  openDrawer();

  const form = document.getElementById("manual-item-form");
  form.querySelector("h2").textContent = "Edit item";
  form.querySelector('button[type="submit"]').textContent = "Save changes";

  if (!isManual) {
    setIdentityFieldsDisabled(form, true);
    const note = document.createElement("p");
    note.className = "field-note";
    note.textContent = "Product details for this item come from Atlas and can't be edited here.";
    form.insertBefore(note, form.querySelector("label"));
  }

  const existing = await sb("GET", TABLES.heartedItems, {
    query: `?id=eq.${encodeURIComponent(heartedItemId)}&limit=1`,
  });
  const item = existing && existing[0];
  if (!item) {
    alert("Could not load this item.");
    closeDrawer();
    return;
  }
  fillManualItemForm(form, item);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (isManual) {
      const urlError = rejectUnsafeUrlFields(form, ["image_url", "product_link", "ebay_sold_link"]);
      if (urlError) {
        alert(urlError);
        return;
      }
    }

    const payload = readManualItemPayload(form, { includeIdentity: isManual });
    if (isManual && !payload.product_name) {
      alert("Product name is required.");
      return;
    }

    try {
      const updated = await sb("PATCH", TABLES.heartedItems, {
        query: `?id=eq.${encodeURIComponent(heartedItemId)}`,
        body: payload,
        prefer: "return=representation",
      });
      closeDrawer();
      const updatedItem = updated && updated[0];
      const row = findHeartedRow(heartedItemId);
      if (updatedItem && row) applyHeartedItemFieldsToRow(row, updatedItem, { isManual });
    } catch (err) {
      console.error("Failed to update item:", err);
      alert("Could not save - please try again.");
    }
  });
}

// ---------------------------------------------------------------
// Hearted Items page: search / filter / sort (pure DOM operations,
// no classification)
// ---------------------------------------------------------------

// Wired once; a freshly-inserted row (manual item add) or a
// previously-empty page transitioning to non-empty both need
// filters re-applied without re-registering listeners each time.
let _heartedControlsWired = false;
let _reapplyHeartedFilters = null;

function applyHeartedItemsControls() {
  const list = document.querySelector(".hearted-list");
  if (!list) return;

  if (!_heartedControlsWired) {
    _heartedControlsWired = true;
    const search = document.getElementById("hi-search");
    const filterStatus = document.getElementById("hi-filter-status");
    const sortSelect = document.getElementById("hi-sort");

    function apply() {
      const currentList = document.querySelector(".hearted-list");
      if (!currentList) return;

      const query = (search.value || "").toLowerCase();
      const status = filterStatus.value;

      currentList.querySelectorAll(".hearted-row").forEach((row) => {
        const matchesSearch = !query || row.dataset.productName.includes(query);
        const matchesStatus = !status || row.dataset.status === status;
        row.style.display = matchesSearch && matchesStatus ? "" : "none";
      });

      const rows = Array.from(currentList.querySelectorAll(".hearted-row"));
      const sortKey = sortSelect.value;
      rows.sort((a, b) => {
        if (sortKey === "hearted_at_asc") return a.dataset.heartedAt.localeCompare(b.dataset.heartedAt);
        if (sortKey === "hearted_at_desc") return b.dataset.heartedAt.localeCompare(a.dataset.heartedAt);
        if (sortKey === "priority") return (a.dataset.priority || "").localeCompare(b.dataset.priority || "");
        if (sortKey === "name") return a.dataset.productName.localeCompare(b.dataset.productName);
        return 0;
      });
      rows.forEach((row) => currentList.appendChild(row));
    }

    _reapplyHeartedFilters = apply;
    search.addEventListener("input", apply);
    filterStatus.addEventListener("change", apply);
    sortSelect.addEventListener("change", apply);
  }

  _reapplyHeartedFilters();
}

// ---------------------------------------------------------------
// Event delegation
// ---------------------------------------------------------------

document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-action]");
  if (!target) return;

  const action = target.dataset.action;

  if (action === "toggle-heart") toggleHeart(target);
  else if (action === "unheart") unheartFromHeartedItemsPage(target);
  else if (action === "archive-hearted") toggleArchive(target);
  else if (action === "notes") openNotesDrawer(target.dataset.opportunityId, target.dataset.heartedItemId);
  else if (action === "edit") openOverrideDrawer(target.closest(".card"));
  else if (action === "edit-hearted") {
    const row = target.closest(".hearted-row");
    const isManual = row ? row.dataset.isManual === "true" : true;
    openEditHeartedItemDrawer(target.dataset.heartedItemId, isManual);
  }
  else if (action === "cancel-drawer") closeDrawer();
  else if (action === "add-item") openManualItemDrawer();
});

document.addEventListener("DOMContentLoaded", () => {
  const addManualButton = document.getElementById("hi-add-manual");
  if (addManualButton) addManualButton.addEventListener("click", openManualItemDrawer);

  if (document.querySelector(".hearted-list")) applyHeartedItemsControls();
});

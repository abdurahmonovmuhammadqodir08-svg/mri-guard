const $ = s => document.querySelector(s);
const LABEL = {glioma: "Glioma", meningioma: "Meningioma", pituitary: "Gipofiz o'smasi", notumor: "O'sma aniqlanmadi"};
const STATUS = {processed: "Tasdiq kutilmoqda", needs_review: "Qo'lda tekshirish kerak", confirmed: "Tasdiqlangan"};

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}
function logout() { sessionStorage.clear(); location.href = "/"; }
function show(msg, ok) {
  const m = $("#msg"); m.textContent = msg; m.className = "msg" + (ok ? " ok" : "");
}
function hideMsg() { const m = $("#msg"); if (m) m.className = "msg hidden"; }
function fmtDate(iso) { return new Date(iso).toLocaleString("uz-UZ", {dateStyle: "short", timeStyle: "short"}); }

async function api(path, opts = {}) {
  const headers = {};
  const t = sessionStorage.getItem("token");
  if (t) headers.Authorization = "Bearer " + t;
  let body = opts.body;
  if (opts.json) { headers["Content-Type"] = "application/json"; body = JSON.stringify(opts.json); }
  const r = await fetch(path, {method: opts.method || "GET", headers, body});
  let data = null;
  try { data = await r.json(); } catch (e) {}
  if (r.status === 401 && t) logout();
  if (!r.ok) throw new Error(typeof (data && data.detail) === "string" ? data.detail : "Kiritilgan ma'lumotlar noto'g'ri");
  return data;
}

function requireRole(role) {
  if (sessionStorage.getItem("role") !== role) { logout(); return false; }
  $("#logout").addEventListener("click", logout);
  return true;
}

/* ---------- Kirish sahifasi ---------- */
function initLogin() {
  $("#showReg").addEventListener("click", () => $("#regForm").classList.toggle("hidden"));
  $("#loginForm").addEventListener("submit", async e => {
    e.preventDefault(); hideMsg();
    try {
      const d = await api("/auth/login", {method: "POST", json: {
        email: $("#email").value, password: $("#password").value, totp_code: $("#totp").value || null}});
      sessionStorage.setItem("token", d.access_token);
      sessionStorage.setItem("role", d.role);
      if (d.role === "doctor") location.href = "/doctor.html";
      else if (d.role === "patient") location.href = "/patient.html";
      else show("Administrator paneli hali tayyor emas.");
    } catch (err) { show(err.message); }
  });
  $("#regForm").addEventListener("submit", async e => {
    e.preventDefault(); hideMsg();
    try {
      await api("/auth/register-patient", {method: "POST", json: {
        full_name: $("#rname").value, email: $("#remail").value, password: $("#rpass").value}});
      show("Hisob yaratildi. Endi yuqoridagi shakl orqali kiring.", true);
      $("#regForm").classList.add("hidden");
    } catch (err) { show(err.message); }
  });
}

/* ---------- Shifokor paneli ---------- */
function step(state, title, text) {
  const li = el("li", state);
  li.appendChild(el("span", "dot", state === "warn" ? "!" : state === "skip" ? "–" : "✓"));
  const d = el("div"); d.appendChild(el("div", "step-title", title)); d.appendChild(el("div", "step-text", text));
  li.appendChild(d); return li;
}

function renderResult(r) {
  $("#emptyRes").classList.add("hidden");
  const box = $("#result"); box.replaceChildren();
  const ol = el("ol", "steps");
  ol.appendChild(step("ok", "Fayl tekshiruvi", "Format va hajm to'g'ri, tasvir xavfsiz qayta kodlandi."));
  ol.appendChild(r.attack_detected
    ? step("warn", "Hujumni aniqlash", `Adversarial hujum belgisi topildi (ball: ${r.detection_score.toFixed(3)}).`)
    : step("ok", "Hujumni aniqlash", `Hujum belgisi topilmadi (ball: ${r.detection_score.toFixed(3)}).`));
  if (r.purified) {
    ol.appendChild(r.status === "needs_review"
      ? step("warn", "Tozalash", `Tasvir tozalandi, lekin shubha qoldi (qolgan ball: ${r.residual_score.toFixed(3)}).`)
      : step("ok", "Tozalash", `Tasvir tozalandi (qolgan ball: ${r.residual_score.toFixed(3)}).`));
  } else ol.appendChild(step("skip", "Tozalash", "Kerak bo'lmadi."));
  ol.appendChild(step("ok", "Tasnif", "Model xulosasi tayyor."));
  box.appendChild(ol);
  box.appendChild(el("div", "verdict", `${LABEL[r.prediction] || r.prediction} (${(r.confidence * 100).toFixed(1)}%)`));
  if (r.status === "needs_review")
    box.appendChild(el("div", "msg", "Tozalashdan keyin ham shubha qoldi. Natijaga tayanmang, tasvirni qayta oling yoki qo'lda tekshiring."));
  const note = el("div", "note", "Natija bemorga faqat siz tasdiqlaganingizdan keyin ko'rinadi.");
  box.appendChild(note);
  const b = el("button", "", "Natijani tasdiqlash va bemorga yuborish");
  b.addEventListener("click", async () => {
    b.disabled = true;
    try { await api(`/scans/${r.scan_id}/confirm`, {method: "POST"}); b.textContent = "Tasdiqlandi"; loadScans(); }
    catch (err) { show(err.message); b.disabled = false; }
  });
  box.appendChild(b);
}

async function loadScans() {
  const rows = await api("/doctor/scans");
  const tb = $("#scanRows"); tb.replaceChildren();
  $("#noScans").classList.toggle("hidden", rows.length > 0);
  rows.forEach(s => {
    const tr = el("tr");
    tr.appendChild(el("td", "", fmtDate(s.date)));
    tr.appendChild(el("td", "", s.patient_name));
    tr.appendChild(el("td", "", `${LABEL[s.prediction] || s.prediction} (${(s.confidence * 100).toFixed(0)}%)`));
    const h = el("td"); h.appendChild(el("span", "badge " + (s.attack_detected ? "warn" : "ok"),
      s.attack_detected ? (s.purified ? "Aniqlandi, tozalandi" : "Aniqlandi") : "Yo'q")); tr.appendChild(h);
    const st = el("td"); st.appendChild(el("span", "badge " + (s.status === "confirmed" ? "ok" : "warn"), STATUS[s.status] || s.status)); tr.appendChild(st);
    const act = el("td");
    if (s.status !== "confirmed") {
      const b = el("button", "small", "Tasdiqlash");
      b.addEventListener("click", async () => {
        try { await api(`/scans/${s.id}/confirm`, {method: "POST"}); loadScans(); } catch (err) { show(err.message); }
      });
      act.appendChild(b);
    }
    tr.appendChild(act); tb.appendChild(tr);
  });
}

async function initDoctor() {
  if (!requireRole("doctor")) return;
  try {
    const ps = await api("/doctor/patients");
    const sel = $("#patient");
    if (!ps.length) sel.appendChild(el("option", "", "Bemorlar yo'q"));
    ps.forEach(p => { const o = el("option", "", `${p.full_name} (${p.email})`); o.value = p.id; sel.appendChild(o); });
    await loadScans();
  } catch (err) { show(err.message); }
  $("#uploadForm").addEventListener("submit", async e => {
    e.preventDefault(); hideMsg();
    const btn = $("#upBtn"); btn.disabled = true; btn.textContent = "Tekshirilmoqda...";
    try {
      const fd = new FormData();
      fd.append("patient_id", $("#patient").value);
      fd.append("file", $("#file").files[0]);
      renderResult(await api("/scans/upload", {method: "POST", body: fd}));
      loadScans();
    } catch (err) { show(err.message); }
    btn.disabled = false; btn.textContent = "Yuklash va tekshirish";
  });
}

/* ---------- Bemor paneli ---------- */
async function initPatient() {
  if (!requireRole("patient")) return;
  try {
    const rows = await api("/patient/results");
    $("#empty").classList.toggle("hidden", rows.length > 0);
    const tb = $("#rows");
    rows.forEach(s => {
      const tr = el("tr");
      tr.appendChild(el("td", "", fmtDate(s.date)));
      tr.appendChild(el("td", "", LABEL[s.prediction] || s.prediction));
      tr.appendChild(el("td", "", (s.confidence * 100).toFixed(1) + "%"));
      tb.appendChild(tr);
    });
  } catch (err) { show(err.message); }
}

const page = document.body.dataset.page;
if (page === "login") initLogin();
else if (page === "doctor") initDoctor();
else if (page === "patient") initPatient();

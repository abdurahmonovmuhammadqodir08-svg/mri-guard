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
      else if (d.role === "admin") location.href = "/admin.html";
      else show("Noma\u2019lum rol.");
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
function adviceBox(btnText, onConfirm) {
  const wrap = el("div", "advice");
  const ta = el("textarea"); ta.rows = 4; ta.maxLength = 2000;
  ta.id = "adv" + Math.random().toString(36).slice(2);
  ta.placeholder = "Bemor uchun tavsiya: keyingi qadamlar, qabulga yozilish, ehtiyot choralari...";
  const lab = el("label", "", "Shifokor maslahati"); lab.htmlFor = ta.id;
  const hint = el("p", "hint", "Bu matn natija bilan birga bemorga ko\u2018rinadi. Ixtiyoriy.");
  const b = el("button", "", btnText);
  b.addEventListener("click", async () => {
    b.disabled = true;
    try { await onConfirm(ta.value.trim(), wrap); } catch (err) { show(err.message); b.disabled = false; }
  });
  wrap.append(lab, ta, hint, b);
  return wrap;
}
const confirmScan = (id, advice) => api(`/scans/${id}/confirm`, {method: "POST", json: {advice}});

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
  if (r.status !== "needs_review") {
    box.appendChild(adviceBox("Tasdiqlash va bemorga yuborish", async (advice, wrap) => {
      await confirmScan(r.scan_id, advice);
      wrap.replaceChildren(el("div", "msg ok", "Natija va maslahat bemorga yuborildi."));
      loadScans();
    }));
  }
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
    tr.appendChild(act); tb.appendChild(tr);
    if (s.status === "processed") {
      const b = el("button", "small", "Maslahat va tasdiq");
      const row2 = el("tr", "hidden"), c2 = el("td"); c2.colSpan = 6; row2.appendChild(c2);
      c2.appendChild(adviceBox("Tasdiqlash va bemorga yuborish", async advice => { await confirmScan(s.id, advice); loadScans(); }));
      b.addEventListener("click", () => row2.classList.toggle("hidden"));
      act.appendChild(b); tb.appendChild(row2);
    }
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
    rows.forEach(s => {
      const card = el("article", "result-card"), head = el("div", "rc-head");
      head.appendChild(el("div", "rc-title", LABEL[s.prediction] || s.prediction));
      head.appendChild(el("div", "rc-meta", `${fmtDate(s.date)} \u00b7 ishonchlilik ${(s.confidence * 100).toFixed(1)}%`));
      card.appendChild(head);
      const adv = el("div", "advice-view");
      adv.appendChild(el("div", "adv-label", s.doctor_name ? `Shifokor maslahati (${s.doctor_name})` : "Shifokor maslahati"));
      adv.appendChild(el("p", "adv-text", s.advice || "Shifokor qo\u2018shimcha maslahat qoldirmagan."));
      card.appendChild(adv);
      $("#list").appendChild(card);
    });
  } catch (err) { show(err.message); }
}

const ROLES = {doctor: "Shifokor", patient: "Bemor", admin: "Administrator"};

async function initAdmin() {
  if (!requireRole("admin")) return;
  const secret = (text, pwd) => {
    const m = $("#msg"); m.className = "msg ok";
    m.replaceChildren(document.createTextNode(text + " "), el("code", "", pwd),
      document.createTextNode(" Bu parol faqat bir marta ko\u2018rsatiladi, uni foydalanuvchiga xavfsiz yo\u2018l bilan bering."));
  };
  async function load() {
    try {
      const q = encodeURIComponent($("#fq").value.trim()), role = $("#frole").value;
      const [stats, users, log] = await Promise.all([api("/admin/stats"), api(`/admin/users?q=${q}&role=${role}`), api("/admin/audit")]);
      $("#st-doctors").textContent = stats.doctors; $("#st-patients").textContent = stats.patients;
      $("#st-scans").textContent = stats.scans; $("#st-attacks").textContent = stats.attacks;
      const tb = $("#userRows"); tb.replaceChildren();
      users.forEach(u => {
        const tr = el("tr");
        [String(u.id), u.full_name, u.email, ROLES[u.role] || u.role].forEach(t => tr.appendChild(el("td", "", t)));
        const stc = el("td"); stc.appendChild(el("span", "badge " + (u.active ? "ok" : "bad"), u.active ? "Faol" : "Bloklangan")); tr.appendChild(stc);
        const act = el("td"), box = el("div", "actions");
        if (!u.is_self) {
          const tg = el("button", "small", u.active ? "Bloklash" : "Faollashtirish");
          tg.addEventListener("click", async () => {
            if (!confirm(`${u.email}: ${u.active ? "bloklansinmi" : "faollashtirilsinmi"}?`)) return;
            try { await api(`/admin/users/${u.id}/active`, {method: "POST", json: {active: !u.active}}); hideMsg(); load(); }
            catch (err) { show(err.message); }
          });
          box.appendChild(tg);
        }
        const rs = el("button", "small", "Parolni tiklash");
        rs.addEventListener("click", async () => {
          if (!confirm(`${u.email} uchun yangi vaqtinchalik parol yaratilsinmi?`)) return;
          try { const d = await api(`/admin/users/${u.id}/reset-password`, {method: "POST"}); secret(`${u.email} uchun yangi parol:`, d.temp_password); load(); }
          catch (err) { show(err.message); }
        });
        box.appendChild(rs); act.appendChild(box); tr.appendChild(act); tb.appendChild(tr);
      });
      const ab = $("#auditRows"); ab.replaceChildren();
      log.forEach(r => {
        const tr = el("tr");
        [fmtDate(r.time), r.user || "\u2014", r.action, r.detail || "", r.ip || ""].forEach(t => tr.appendChild(el("td", "", t)));
        ab.appendChild(tr);
      });
    } catch (err) { show(err.message); }
  }
  $("#newUser").addEventListener("submit", async e => {
    e.preventDefault(); hideMsg();
    try {
      const d = await api("/admin/users", {method: "POST", json: {full_name: $("#nName").value, email: $("#nEmail").value,
        role: $("#nRole").value, password: $("#nPass").value || null}});
      if (d.temp_password) secret("Hisob yaratildi. Vaqtinchalik parol:", d.temp_password); else show("Hisob yaratildi.", true);
      e.target.reset(); load();
    } catch (err) { show(err.message); }
  });
  let timer; $("#fq").addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(load, 300); });
  $("#frole").addEventListener("change", load);
  load();
}

const page = document.body.dataset.page;
if (page === "login") initLogin();
else if (page === "doctor") initDoctor();
else if (page === "patient") initPatient();
else if (page === "admin") initAdmin();

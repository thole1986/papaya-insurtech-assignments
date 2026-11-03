"use strict";
const $ = id => document.getElementById(id);
const state = {session: null, claim: null, run: null, cases: [], selected: null, busy: false};
const money = value => value == null ? "Chưa đánh giá" : `${new Intl.NumberFormat("vi-VN").format(value)} ₫`;
function el(tag, text, cls) { const n = document.createElement(tag); if (text != null) n.textContent = text; if (cls) n.className = cls; return n; }
function notice(text, error = false) { $("notice").textContent = text; $("notice").className = error ? "error" : ""; }
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error?.message || JSON.stringify(result.detail || result));
  return result;
}
function controls() {
  $("create").disabled = state.busy || !state.selected;
  $("assess").disabled = state.busy || !state.claim;
  $("attach").disabled = state.busy || !$("documents").value;
  for (const id of ["send", "save-review"]) $(id).disabled = state.busy || state.run?.status !== "completed";
  for (const id of ["custom-create", "new-session", "history", "documents"]) $(id).disabled = state.busy;
  document.querySelectorAll(".case").forEach(n => {n.disabled = state.busy;});
}
async function action(fn) {
  if (state.busy) return;
  state.busy = true; controls(); notice("Đang xử lý…");
  try { await fn(); notice("Hoàn tất."); }
  catch (error) { notice(error.message, true); }
  finally { state.busy = false; controls(); }
}
async function session() {
  state.session = await api("/api/v1/sessions", {});
  localStorage.setItem("claim-session", state.session.id);
  state.claim = null; state.run = null;
  $("claim-summary").textContent = "Chưa có claim.";
  $("claim-json").textContent = "{}"; $("revision").textContent = "—";
  $("history").replaceChildren(new Option("Chưa có assessment", ""));
  $("documents").replaceChildren(new Option("Không có tài liệu bổ sung", ""));
  clearReport();
}
function clearReport() {
  state.run = null; $("report").replaceChildren(); $("report").hidden = true; $("empty").hidden = false;
  $("audit-panel").hidden = true; $("messages").replaceChildren(el("p", "Hoàn tất assessment để bắt đầu.", "muted"));
  $("reviews").replaceChildren(); $("outcome").textContent = "WAITING"; $("outcome").className = "pill";
  $("result-title").textContent = "Sẵn sàng thẩm định";
}
async function loadClaim(id, chosenRun) {
  const data = await api(`/api/v1/claims/${id}`); state.claim = data.claim;
  const c = data.claim;
  $("claim-summary").textContent = `${c.claim_type} · ${c.diagnosis} · ${money(c.amount)} · ${c.treatment_start} → ${c.treatment_end}`;
  $("claim-json").textContent = JSON.stringify({claim: c, documents: data.documents}, null, 2);
  $("revision").textContent = `REV ${c.revision}`;
  $("documents").replaceChildren(new Option("Chọn tài liệu để bổ sung", ""));
  for (const d of data.documents.filter(d => !c.document_ids.includes(d.id))) $("documents").append(new Option(`${d.declared_type} · registry verified`, d.id));
  $("history").replaceChildren(new Option("Chọn assessment version", ""));
  for (const r of data.assessments) $("history").append(new Option(`v${r.version} · ${r.status} · ${r.report?.recommendation.outcome || r.error || "running"}`, r.id));
  const target = chosenRun || data.assessments.at(-1)?.id;
  if (target) { $("history").value = target; await loadRun(target); } else clearReport();
}
function section(number, title) { const s = el("section", null, "panel report-section"); const h = el("h2"); h.append(el("span", number, "number"), document.createTextNode(title)); s.append(h); $("report").append(s); return s; }
function facts(container, items) { const grid = el("div", null, "facts"); for (const [label,value,highlight] of items) {const f = el("div", null, "fact" + (highlight ? " highlight" : "")); f.append(el("span", label), el("strong", String(value))); grid.append(f);} container.append(grid); }
function renderReport(r) {
  $("report").replaceChildren(); $("report").hidden = false; $("empty").hidden = true;
  $("result-title").textContent = `Assessment · revision ${r.claim_revision}`;
  $("outcome").textContent = r.recommendation.outcome; $("outcome").className = `pill ${r.recommendation.outcome}`;
  let s = section("01", "Document Review");
  for (const d of r.document_review) {const row = el("div", null, "doc-row"); const top = el("div", null, "doc-top"); top.append(el("strong", d.expected_type), el("span", d.status.toUpperCase(), "pill")); row.append(top, el("small", d.document_id || "Chưa nộp")); if(d.issues.length) row.append(el("p", d.issues.join(" "))); s.append(row);}
  s = section("02", "Policy Verification"); const p = r.policy_verification;
  facts(s, [["Policy", `${p.policy_id} ${p.policy_version}`], ["Coverage period", p.active_for_treatment ? "Pass" : "Fail"], ["Member", p.member_covered ? "Covered" : "Not covered"], ["Claim type", p.claim_type_covered ? "Covered" : "Not covered"], ["Waiting period", p.waiting_period_satisfied ? "Satisfied" : "Not satisfied"]]);
  for (const f of p.findings) s.append(el("p", `${f.code}: ${f.explanation}`));
  s = section("03", "Medical Necessity"); s.append(el("span", r.medical_necessity.status, "pill"), el("p", r.medical_necessity.explanation), el("small", r.medical_necessity.rule_ids.join(", "), "muted"));
  s = section("04", "Benefit Calculation"); const b = r.benefit_calculation;
  facts(s, [["Submitted", money(b.submitted_amount)], ["Insurer payout", money(b.covered_amount), true], ["Member copay", money(b.copay)], ["Limit excess", money(b.limit_excess)], ["Member total", money(b.member_responsibility)], ["Remaining limit", money(b.remaining_limit_after)]]); s.append(el("p", `${b.status}: ${b.explanation}`, "muted"));
  s = section("05", "Recommendation");
  for (const reason of r.recommendation.reasons) {const row = el("div", null, "reason"); row.append(el("strong", reason.code), el("p", reason.explanation)); for(const c of reason.clause_ids) row.append(el("code", c)); row.append(el("p", `Evidence: ${reason.evidence_refs.join(", ")}`, "muted")); s.append(row);}
  const summary = el("details"); summary.append(el("summary", "Model-generated summary (review alongside verified facts)"), el("p", r.narrative)); s.append(summary);
  s = section("06", "Policy Citations");
  for (const c of r.policy_citations) {const row = el("div", null, "citation"); row.append(el("code", c.id), el("strong", ` ${c.title}`), el("p", c.text)); s.append(row);}
  $("decision").value = r.recommendation.outcome;
}
async function loadRun(id) {
  state.run = await api(`/api/v1/assessments/${id}`); const run = state.run;
  if (run.report) renderReport(run.report); else {clearReport(); state.run = run; $("result-title").textContent = `Assessment ${run.status}: ${run.error || "đang chạy"}`;}
  const trace = await api(`/api/v1/assessments/${id}/tool-calls`); $("trace").replaceChildren();
  for (const t of trace) {const d = el("details"); d.append(el("summary", `${String(t.sequence).padStart(2,"0")} · ${t.tool} · ${t.status} · ${t.duration_ms} ms`), el("pre", JSON.stringify(t, null, 2))); $("trace").append(d);}
  $("audit-panel").hidden = false; $("download").href = `/api/v1/assessments/${id}/markdown`; $("download").hidden = !run.report;
  await loadReviews();
  const data = await api(`/api/v1/sessions/${state.session.id}`); $("messages").replaceChildren();
  for (const m of data.messages.filter(m => m.assessment_id === id)) addMessage(m);
}
function addMessage(m) {const item = el("div", null, `message ${m.role}`); item.append(el("small", `${m.role} · ${m.mode}`), document.createTextNode(m.content)); $("messages").append(item); $("messages").scrollTop = $("messages").scrollHeight;}
async function loadReviews() {$("reviews").replaceChildren(); if (!state.run) return; const rows = await api(`/api/v1/assessments/${state.run.id}/reviews`); for (const r of rows) {const div = el("div", null, "review-item"); div.append(el("strong", `${r.decision} · ${r.reviewer}`), el("p", r.reason), el("small", `${r.created_at} · original: ${r.original_recommendation}`, "muted")); $("reviews").append(div);}}
$("create").onclick = () => action(async () => {const c = await api("/api/v1/claims", {session_id: state.session.id, case_id: state.selected}); await loadClaim(c.id);});
$("custom-create").onclick = () => action(async () => {const c = await api("/api/v1/claims", {session_id: state.session.id, claim: JSON.parse($("custom-json").value)}); await loadClaim(c.id);});
$("new-session").onclick = () => action(session);
$("assess").onclick = () => action(async () => {const claimId = state.claim.id; try {const r = await api(`/api/v1/claims/${claimId}/assessments`, {}); await loadClaim(claimId, r.id);} catch(e) {await loadClaim(claimId); throw e;}});
$("history").onchange = () => {if ($("history").value) action(() => loadRun($("history").value));};
$("documents").onchange = controls;
$("attach").onclick = () => action(async () => {await api(`/api/v1/claims/${state.claim.id}/documents`, {document_id: $("documents").value}); await loadClaim(state.claim.id);});
$("chat-form").onsubmit = e => {e.preventDefault(); action(async () => {const text = $("chat").value; const m = await api(`/api/v1/sessions/${state.session.id}/messages`, {assessment_id: state.run.id, content: text}); addMessage({role:"user", mode:m.mode, content:text}); addMessage(m); $("chat").value = "";});};
$("review-form").onsubmit = e => {e.preventDefault(); action(async () => {await api(`/api/v1/assessments/${state.run.id}/reviews`, {decision:$("decision").value, reviewer:$("reviewer").value.trim(), reason:$("review-reason").value.trim()}); await loadReviews(); $("review-reason").value = "";});};
action(async () => {
  const health = await api("/health"); $("mode").textContent = health.mode === "offline" ? "OFFLINE · NO LLM API" : "LIVE · GEMINI API";
  state.cases = await api("/api/v1/demo-cases");
  for (const [i,c] of state.cases.entries()) {const button = el("button", c.title, "case"); button.append(el("small", c.id)); button.onclick = () => {state.selected=c.id; document.querySelectorAll(".case").forEach(b=>b.classList.remove("selected")); button.classList.add("selected"); const custom = {...c.claim, document_ids:[]}; $("custom-json").value=JSON.stringify(custom,null,2); controls();}; $("cases").append(button); if(i===0) button.click();}
  const saved = localStorage.getItem("claim-session");
  if(saved) {try {state.session = await api(`/api/v1/sessions/${saved}`); if(state.session.claims.length) await loadClaim(state.session.claims.at(-1).id);} catch {await session();}} else await session();
});

/* Storyteller frontend — vanilla JS, no build step, works on low-spec Android. */
const $ = (id) => document.getElementById(id);
const STAGES = ["research", "script", "images", "narration", "subtitles", "video", "thumbnail", "metadata"];
const STAGE_LABELS = {
  research: "🔍 Researching", script: "✍️ Writing script", images: "🖼️ Finding pictures",
  narration: "🎙️ Recording voice", subtitles: "💬 Adding subtitles", video: "🎬 Rendering video",
  thumbnail: "🖼️ Making thumbnail", metadata: "🏷️ Writing title & tags", done: "✅ Ready to review",
};
let currentId = null, pollTimer = null;

async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!r.ok) throw new Error((await r.text()).slice(0, 300));
  return r.json();
}

async function checkHealth() {
  try {
    const h = await api("/api/health");
    const b = $("healthBadge");
    b.textContent = h.youtube_configured ? "● YouTube connected" : "● Demo mode (manual upload)";
    b.className = "badge " + (h.youtube_configured ? "ok" : "warn");
  } catch { $("healthBadge").textContent = "● Offline"; }
}

function renderStages(current, doneList) {
  $("stageList").innerHTML = STAGES.map((s) => {
    const done = doneList.includes(s);
    const active = s === current && !done;
    const cls = done ? "done" : active ? "active" : "";
    const mark = done ? "✓" : active ? "…" : "";
    return `<li class="${cls}"><span>${STAGE_LABELS[s]}</span><span class="st">${mark}</span></li>`;
  }).join("");
}

function showPreview(p) {
  $("previewArea").hidden = false;
  const v = $("previewVideo");
  v.src = `/api/projects/${p.id}/file?path=FinalVideo/video.mp4`;
  $("previewThumb").src = `/api/projects/${p.id}/file?path=Thumbnail/thumbnail.jpg`;
  const meta = p.data.metadata || {};
  $("metaTitle").textContent = meta.title || p.topic;
  $("metaTags").textContent = (meta.tags || []).join(", ");
  const links = [];
  if (p.data.srt) links.push(`<a href="/api/projects/${p.id}/file?path=Subtitles/captions.srt" download>⬇ Subtitles (.srt)</a>`);
  links.push(`<a href="/api/projects/${p.id}/file?path=Script/script.txt" download>⬇ Script</a>`);
  links.push(`<a href="/api/projects/${p.id}/file?path=Metadata/description.txt" download>⬇ Description</a>`);
  if (p.drive_url) links.push(`<a href="${p.drive_url}" target="_blank">💾 Open in Drive</a>`);
  if (p.youtube_url) links.push(`<a href="${p.youtube_url}" target="_blank">▶ Watch on YouTube</a>`);
  $("assetLinks").innerHTML = links.join("");
}

function updateUI(p) {
  $("projTitle").textContent = p.topic;
  $("progressFill").style.width = p.progress + "%";
  $("pct").textContent = p.progress + "%";
  $("stageLabel").textContent = STAGE_LABELS[p.stage] || p.stage;
  renderStages(p.stage, p.stages_done || []);
  const ready = p.status === "awaiting_approval" || p.status === "done";
  if (ready) showPreview(p);
  if (p.status === "failed") {
    $("failBox").hidden = false;
    $("failBox").textContent = "⚠️ " + (p.error || "Something went wrong. Retry resumes from the failed step.");
    $("retryBtn").hidden = false;
  } else {
    $("failBox").hidden = true;
    $("retryBtn").hidden = true;
  }
  if (p.youtube_url) $("publishMsg").textContent = "✅ Published: " + p.youtube_url;
}

async function poll() {
  if (!currentId) return;
  try {
    const p = await api(`/api/projects/${currentId}`);
    updateUI(p);
    if (["awaiting_approval", "done", "failed"].includes(p.status)) {
      clearInterval(pollTimer); pollTimer = null;
      loadHistory();
    }
  } catch (e) { /* keep polling */ }
}

async function loadHistory() {
  try {
    const list = await api("/api/projects");
    const box = $("history");
    if (!list.length) { box.innerHTML = '<p class="sub">No projects yet.</p>'; return; }
    box.innerHTML = list.slice(0, 10).map((p) => `
      <div class="history-item" data-id="${p.id}">
        <span>${p.topic}</span>
        <span class="h-status">${p.status} · ${p.progress}%</span>
      </div>`).join("");
    box.querySelectorAll(".history-item").forEach((el) =>
      el.addEventListener("click", () => {
        currentId = el.dataset.id;
        $("progressCard").hidden = false;
        poll(); pollTimer = setInterval(poll, 2500);
        window.scrollTo({ top: 0, behavior: "smooth" });
      }));
  } catch { /* ignore */ }
}

$("generateBtn").addEventListener("click", async () => {
  const topic = $("topic").value.trim();
  if (!topic) { $("genError").hidden = false; $("genError").textContent = "Please enter a topic first."; return; }
  $("genError").hidden = true;
  $("generateBtn").disabled = true;
  $("generateBtn").textContent = "⏳ Working…";
  $("progressCard").hidden = false;
  $("previewArea").hidden = true;
  $("publishMsg").textContent = "";
  try {
    const p = await api("/api/projects", {
      method: "POST",
      body: JSON.stringify({
        topic, description: $("desc").value.trim(),
        duration_sec: parseInt($("duration").value, 10),
        format: $("format").value, voice: $("voice").value, language: $("language").value,
      }),
    });
    currentId = p.id;
    updateUI(p);
    pollTimer = setInterval(poll, 2500);
  } catch (e) {
    $("genError").hidden = false;
    $("genError").textContent = "Error: " + e.message;
  } finally {
    $("generateBtn").disabled = false;
    $("generateBtn").textContent = "✨ Generate Video";
  }
});

$("publishBtn").addEventListener("click", async () => {
  if (!currentId) return;
  $("publishBtn").disabled = true;
  $("publishMsg").textContent = "⏳ Publishing…";
  try {
    const res = await api(`/api/projects/${currentId}/publish`, {
      method: "POST", body: JSON.stringify({ privacy: $("privacy").value }),
    });
    $("publishMsg").textContent = res.published
      ? "✅ Published! " + res.url
      : "📦 Manual-upload package ready in Metadata/manual_upload — " + (res.message || "");
  } catch (e) {
    $("publishMsg").textContent = "❌ " + e.message;
  } finally { $("publishBtn").disabled = false; }
});

$("driveBtn").addEventListener("click", () => {
  $("publishMsg").textContent = "💾 All files are saved in the project folder (and Drive if mounted). Use the download links below.";
});

$("retryBtn").addEventListener("click", async () => {
  if (!currentId) return;
  await api(`/api/projects/${currentId}/retry`, { method: "POST" });
  pollTimer = setInterval(poll, 2500);
});

checkHealth();
loadHistory();

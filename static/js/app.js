// ==========================================================================
// VERDANT WILDNOTES — CLIENT APPLICATION ENGINE
// ==========================================================================

let activeImagePayload = null; // Can be File, base64 string, or sample ID
let activeCameraStream = null;
let sensoryXP = 82;
let completedCluesCount = 0;

// DOM Elements
const systemStatusBadge = document.getElementById("systemStatusBadge");
const modelStatusText = document.getElementById("modelStatusText");

const tabUpload = document.getElementById("tabUpload");
const tabCamera = document.getElementById("tabCamera");
const dropzoneView = document.getElementById("dropzoneView");
const cameraView = document.getElementById("cameraView");
const cameraVideo = document.getElementById("cameraVideo");
const shutterBtn = document.getElementById("shutterBtn");
const fileInput = document.getElementById("fileInput");
const previewImg = document.getElementById("previewImg");
const scanLine = document.getElementById("scanLine");

const inspectBtn = document.getElementById("inspectBtn");
const inspectBtnText = document.getElementById("inspectBtnText");
const inspectSpinner = document.getElementById("inspectSpinner");

const sampleFernBtn = document.getElementById("sampleFernBtn");
const sampleLichenBtn = document.getElementById("sampleLichenBtn");
const sampleMushroomBtn = document.getElementById("sampleMushroomBtn");

const lookCloserText = document.getElementById("lookCloserText");
const touchFeelText = document.getElementById("touchFeelText");
const scentSurroundingsText = document.getElementById("scentSurroundingsText");
const fieldInquiryText = document.getElementById("fieldInquiryText");
const sensoryScoreBadge = document.getElementById("sensoryScoreBadge");

const journalFeed = document.getElementById("journalFeed");
const statDiscoveriesCount = document.getElementById("statDiscoveriesCount");
const statSensesEngaged = document.getElementById("statSensesEngaged");
const statRangerRank = document.getElementById("statRangerRank");
const clearJournalBtn = document.getElementById("clearJournalBtn");

const ambientToggleBtn = document.getElementById("ambientToggleBtn");
const ambientIcon = document.getElementById("ambientIcon");
const ambientLabel = document.getElementById("ambientLabel");
const heroCtaBtn = document.getElementById("heroCtaBtn");

// ==========================================================================
// INITIALIZATION
// ==========================================================================

document.addEventListener("DOMContentLoaded", () => {
  checkSystemStatus();
  fetchJournal();
  setupEventHandlers();
  // Pre-load fern sample as default preview for immediate aesthetic wow factor
  selectSample("sample_fern", false);
});

function setupEventHandlers() {
  // Tabs
  tabUpload.addEventListener("click", () => switchTab("upload"));
  tabCamera.addEventListener("click", () => switchTab("camera"));

  // File Upload
  dropzoneView.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", handleFileSelect);

  // Drag and drop
  dropzoneView.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzoneView.classList.add("dragover");
  });
  dropzoneView.addEventListener("dragleave", () => {
    dropzoneView.classList.remove("dragover");
  });
  dropzoneView.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzoneView.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleImageFile(e.dataTransfer.files[0]);
    }
  });

  // Camera Shutter
  shutterBtn.addEventListener("click", captureCameraPhoto);

  // Sample Chips
  sampleFernBtn.addEventListener("click", () => selectSample("sample_fern"));
  sampleLichenBtn.addEventListener("click", () => selectSample("sample_lichen"));
  sampleMushroomBtn.addEventListener("click", () => selectSample("sample_mushroom"));

  // Inspect Action
  inspectBtn.addEventListener("click", runInspection);
  heroCtaBtn.addEventListener("click", () => {
    document.getElementById("lens-card").scrollIntoView({ behavior: "smooth" });
    runInspection();
  });

  // Clear Journal
  clearJournalBtn.addEventListener("click", clearJournal);

  // Ambient sound
  ambientToggleBtn.addEventListener("click", toggleAmbientSound);
}

// ==========================================================================
// SYSTEM STATUS CHECK
// ==========================================================================

async function checkSystemStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    if (data.status_label) {
      modelStatusText.textContent = data.status_label;
      systemStatusBadge.style.borderColor = "rgba(163, 230, 53, 0.4)";
    } else if (data.connected) {
      const modelClean = data.active_model.replace(":latest", "");
      modelStatusText.textContent = `${modelClean} active`;
      systemStatusBadge.style.borderColor = "rgba(163, 230, 53, 0.4)";
    } else {
      modelStatusText.textContent = "Field Guide Ready";
      systemStatusBadge.style.borderColor = "rgba(163, 230, 53, 0.3)";
    }
  } catch (err) {
    modelStatusText.textContent = "Field Guide Ready";
  }
}

// ==========================================================================
// VIEWPORT & TAB CONTROLS
// ==========================================================================

function switchTab(mode) {
  if (mode === "upload") {
    tabUpload.classList.add("active");
    tabCamera.classList.remove("active");
    stopCamera();
    cameraView.style.display = "none";
    if (activeImagePayload && previewImg.src) {
      previewImg.style.display = "block";
      dropzoneView.style.display = "none";
    } else {
      dropzoneView.style.display = "flex";
      previewImg.style.display = "none";
    }
  } else if (mode === "camera") {
    tabCamera.classList.add("active");
    tabUpload.classList.remove("active");
    dropzoneView.style.display = "none";
    previewImg.style.display = "none";
    cameraView.style.display = "block";
    startCamera();
  }
}

async function startCamera() {
  try {
    activeCameraStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "environment", width: { ideal: 1280 } },
      audio: false,
    });
    cameraVideo.srcObject = activeCameraStream;
  } catch (err) {
    showToast("⚠️ Camera access unavailable. Please use file upload.");
    switchTab("upload");
  }
}

function stopCamera() {
  if (activeCameraStream) {
    activeCameraStream.getTracks().forEach((track) => track.stop());
    activeCameraStream = null;
  }
}

function captureCameraPhoto() {
  const canvas = document.createElement("canvas");
  canvas.width = cameraVideo.videoWidth || 640;
  canvas.height = cameraVideo.videoHeight || 480;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(cameraVideo, 0, 0, canvas.width, canvas.height);
  const dataUrl = canvas.toDataURL("image/jpeg", 0.9);

  activeImagePayload = { type: "base64", data: dataUrl };
  previewImg.src = dataUrl;
  previewImg.style.display = "block";
  cameraView.style.display = "none";
  stopCamera();
  tabCamera.classList.remove("active");
  tabUpload.classList.add("active");
  showToast("📸 Specimen snapped! Ready to inspect.");
}

function handleFileSelect(e) {
  if (e.target.files && e.target.files[0]) {
    handleImageFile(e.target.files[0]);
  }
}

function handleImageFile(file) {
  activeImagePayload = { type: "file", file: file };
  const reader = new FileReader();
  reader.onload = (e) => {
    previewImg.src = e.target.result;
    previewImg.style.display = "block";
    dropzoneView.style.display = "none";
    showToast(`🌿 Loaded: ${file.name}`);
  };
  reader.readAsDataURL(file);
}

function selectSample(sampleId, notify = true) {
  activeImagePayload = { type: "sample", id: sampleId };
  previewImg.src = `/static/images/${sampleId}.jpg`;
  previewImg.style.display = "block";
  dropzoneView.style.display = "none";
  stopCamera();
  tabCamera.classList.remove("active");
  tabUpload.classList.add("active");
  if (notify) {
    showToast(`🌱 Sample specimen selected (${sampleId.replace("sample_", "")})`);
  }
}

// ==========================================================================
// RUN INSPECTION VIA FASTAPI & OLLAMA
// ==========================================================================

async function runInspection() {
  if (!activeImagePayload) {
    showToast("⚠️ Please upload an image or choose a specimen first!");
    return;
  }

  // Set loading state
  inspectBtn.disabled = true;
  inspectBtnText.textContent = "Observing Specimen...";
  inspectSpinner.style.display = "block";
  scanLine.style.display = "block";

  const formData = new FormData();
  formData.append("model", "moondream");

  if (activeImagePayload.type === "file") {
    formData.append("file", activeImagePayload.file);
  } else if (activeImagePayload.type === "base64") {
    formData.append("image_base64", activeImagePayload.data);
  } else if (activeImagePayload.type === "sample") {
    formData.append("sample_id", activeImagePayload.id);
  }

  try {
    const res = await fetch("/api/inspect", {
      method: "POST",
      body: formData,
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || "Inspection error");
    }

    // Parse and render results
    renderObservation(data.analysis);
    showToast("🌿 Inspection complete! Clues unlocked.");
    fetchJournal();

    // Scroll smoothly to sensory card
    document.getElementById("sensory-card").scrollIntoView({ behavior: "smooth" });

  } catch (err) {
    showToast(`❌ ${err.message}`);
  } finally {
    inspectBtn.disabled = false;
    inspectBtnText.textContent = "🍃 Discover Sensory Clues";
    inspectSpinner.style.display = "none";
    scanLine.style.display = "none";
  }
}

// ==========================================================================
// RENDER SENSORY CLUES
// ==========================================================================

function renderObservation(analysisText) {
  // Reset clue completion statuses
  document.querySelectorAll(".clue-card").forEach((card) => {
    card.classList.remove("completed");
  });

  const lines = analysisText.split("\n").map(l => l.trim()).filter(Boolean);
  let lookCloser = "";
  let touchFeel = "";
  let scent = "";
  let inquiry = "";

  for (let l of lines) {
    if (l.includes("Look Closer") || l.includes("🔎")) {
      lookCloser = l.replace(/.*Look Closer.*?:/i, "").trim().replace(/^\*+|\*+$/g, "");
    } else if (l.includes("Touch & Feel") || l.includes("✋")) {
      touchFeel = l.replace(/.*Touch & Feel.*?:/i, "").trim().replace(/^\*+|\*+$/g, "");
    } else if (l.includes("Scent & Surroundings") || l.includes("👃") || l.includes("Smell")) {
      scent = l.replace(/.*(Scent|Surroundings|Smell).*?:/i, "").trim().replace(/^\*+|\*+$/g, "");
    } else if (l.includes("FIELD INQUIRY") || (l.includes("?") && !inquiry)) {
      if (!l.startsWith("###")) {
        inquiry = l.replace(/.*FIELD INQUIRY.*?:/i, "").replace(/^\*+|\*+$/g, "").trim();
      }
    }
  }

  // Fallback for compact vision models (like moondream) that output natural narrative paragraphs
  if (!lookCloser) {
    // Extract sentences from text
    const sentences = analysisText.split(/(?<=[.?!])\s+/).map(s => s.trim()).filter(Boolean);
    if (sentences.length >= 1) {
      lookCloser = sentences[0];
    }
    if (sentences.length >= 2) {
      touchFeel = "Notice the texture: " + sentences[1];
    } else {
      touchFeel = "Observe the surface texture with your fingertips — is it damp, velvet, or coarse?";
    }
    if (sentences.length >= 3) {
      scent = "Environmental context: " + sentences[2];
    } else {
      scent = "Breathe in the surrounding air. Notice the moist forest soil and adjacent moss aroma.";
    }
    if (!inquiry) {
      inquiry = "How does this specimen adapt to its microclimate and share nutrients with the forest floor?";
    }
  }

  if (lookCloser) lookCloserText.textContent = lookCloser;
  if (touchFeel) touchFeelText.textContent = touchFeel;
  if (scent) scentSurroundingsText.textContent = scent;
  if (inquiry) fieldInquiryText.textContent = `"${inquiry}"`;

  // Bump sensory engagement score
  sensoryXP = Math.min(99, sensoryXP + 4);
  sensoryScoreBadge.textContent = `+ ${sensoryXP}%`;
}

// Interactive checklist click
window.toggleClueCheck = function (element) {
  element.classList.toggle("completed");
  const completed = document.querySelectorAll(".clue-card.completed").length;
  sensoryXP = Math.min(100, 80 + completed * 6);
  sensoryScoreBadge.textContent = `+ ${sensoryXP}%`;
  statSensesEngaged.textContent = `${sensoryXP}%`;

  if (element.classList.contains("completed")) {
    showToast("✨ Sense engaged! Field XP awarded.");
  }
};

// ==========================================================================
// JOURNAL & STATS
// ==========================================================================

async function fetchJournal() {
  try {
    const res = await fetch("/api/journal");
    const data = await res.json();
    renderJournalFeed(data.entries || []);
    statDiscoveriesCount.textContent = data.total || 0;

    // Calculate ranger rank
    const total = data.total || 0;
    if (total >= 10) statRangerRank.textContent = "Master Naturalist";
    else if (total >= 5) statRangerRank.textContent = "Trail Tracker II";
    else if (total >= 1) statRangerRank.textContent = "Trail Tracker I";
    else statRangerRank.textContent = "Novice Scout";

  } catch (err) {
    console.warn("Failed to fetch journal", err);
  }
}

function renderJournalFeed(entries) {
  if (!entries || entries.length === 0) {
    journalFeed.innerHTML = `
      <div class="journal-entry-item">
        <div class="entry-top">
          <span class="entry-badge">Empty Trail</span>
          <span class="entry-time">Ready</span>
        </div>
        <h4 class="entry-title">No specimens logged yet</h4>
        <p class="entry-snippet">Inspect your first specimen outdoor to record your discovery here.</p>
      </div>
    `;
    return;
  }

  journalFeed.innerHTML = entries
    .map(
      (entry) => `
    <div class="journal-entry-item">
      <div class="entry-top">
        <span class="entry-badge">${escapeHtml(entry.specimen_type || "Botanical")}</span>
        <span class="entry-time">${escapeHtml(entry.timestamp || "")}</span>
      </div>
      <h4 class="entry-title">${escapeHtml(entry.title || "Specimen Observation")}</h4>
      <p class="entry-snippet">${escapeHtml((entry.notes || "").slice(0, 110))}...</p>
    </div>
  `
    )
    .join("");
}

async function clearJournal() {
  if (!confirm("Are you sure you want to reset your trail expedition log?")) return;
  try {
    await fetch("/api/journal", { method: "DELETE" });
    fetchJournal();
    showToast("🗑️ Journal reset.");
  } catch (err) {
    showToast("❌ Could not reset journal.");
  }
}

// ==========================================================================
// PROCEDURAL PROCEDURAL FOREST AMBIENT SOUND (WEB AUDIO API)
// ==========================================================================

let audioCtx = null;
let isAudioPlaying = false;
let ambientNodes = [];

function toggleAmbientSound() {
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  }

  if (isAudioPlaying) {
    // Stop audio
    ambientNodes.forEach((node) => {
      try {
        node.stop();
        node.disconnect();
      } catch (e) {}
    });
    ambientNodes = [];
    isAudioPlaying = false;
    ambientToggleBtn.classList.remove("playing");
    ambientIcon.textContent = "🔇";
    ambientLabel.textContent = "Sound Muted";
    showToast("Forest soundscape muted.");
  } else {
    // Start gentle procedural breeze & chirps
    audioCtx.resume();
    createProceduralForestSound();
    isAudioPlaying = true;
    ambientToggleBtn.classList.add("playing");
    ambientIcon.textContent = "🌿";
    ambientLabel.textContent = "Sound Active";
    showToast("🍃 Procedural forest soundscape active.");
  }
}

function createProceduralForestSound() {
  // Pink noise generator for gentle breeze
  const bufferSize = audioCtx.sampleRate * 2;
  const noiseBuffer = audioCtx.createBuffer(1, bufferSize, audioCtx.sampleRate);
  const output = noiseBuffer.getChannelData(0);
  let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;
  for (let i = 0; i < bufferSize; i++) {
    const white = Math.random() * 2 - 1;
    b0 = 0.99886 * b0 + white * 0.0555179;
    b1 = 0.99332 * b1 + white * 0.0750759;
    b2 = 0.96900 * b2 + white * 0.1538520;
    b3 = 0.86650 * b3 + white * 0.3104856;
    b4 = 0.55000 * b4 + white * 0.5329522;
    b5 = -0.7616 * b5 - white * 0.0168980;
    output[i] = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + white * 0.5362) * 0.015;
    b6 = white * 0.115926;
  }

  const whiteNoise = audioCtx.createBufferSource();
  whiteNoise.buffer = noiseBuffer;
  whiteNoise.loop = true;

  // Filter for wind rustling
  const filter = audioCtx.createBiquadFilter();
  filter.type = "lowpass";
  filter.frequency.value = 380;

  const gain = audioCtx.createGain();
  gain.gain.value = 0.6;

  whiteNoise.connect(filter);
  filter.connect(gain);
  gain.connect(audioCtx.destination);
  whiteNoise.start();

  ambientNodes.push(whiteNoise);
}

// ==========================================================================
// TOAST NOTIFICATIONS
// ==========================================================================

let toastTimer = null;
function showToast(message) {
  const toast = document.getElementById("toastNotice");
  toast.querySelector("span").textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.classList.remove("show");
  }, 3200);
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

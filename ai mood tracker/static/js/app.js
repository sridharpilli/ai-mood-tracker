/* ═══════════════════════════════════════════════════════════
   MoodAI — Frontend Logic
   Handles: navigation, API calls, history, charts
   ═══════════════════════════════════════════════════════════ */

"use strict";

// ─── Chart instances (kept so we can destroy before re-draw) ───
let pieChartInst = null;
let barChartInst = null;

// ── Chart.js global defaults ────────────────────────────────
Chart.defaults.font.family = "'DM Sans', system-ui, sans-serif";
Chart.defaults.color       = "#7a6575";

// ══════════════════════════════════════════════
// 1. NAVIGATION
// ══════════════════════════════════════════════

document.querySelectorAll(".nav-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const target = btn.dataset.section;

    document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");

    document.querySelectorAll(".section").forEach(s => s.classList.remove("active"));
    document.getElementById(`section-${target}`).classList.add("active");

    // Lazy-load data when switching tabs
    if (target === "history") loadHistory();
    if (target === "trends")  loadTrends();
  });
});

// ══════════════════════════════════════════════
// 2. CHARACTER COUNTER
// ══════════════════════════════════════════════

const moodInput  = document.getElementById("moodInput");
const charCount  = document.getElementById("charCount");

moodInput.addEventListener("input", () => {
  charCount.textContent = moodInput.value.length;
});

// Allow Ctrl/Cmd + Enter to submit
moodInput.addEventListener("keydown", e => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") analyzeMood();
});

// ══════════════════════════════════════════════
// 3. ANALYSE MOOD  (main action)
// ══════════════════════════════════════════════

async function analyzeMood() {
  const text = moodInput.value.trim();
  const btn  = document.getElementById("analyzeBtn");
  const err  = document.getElementById("errorMsg");

  err.textContent = "";

  if (!text) {
    err.textContent = "Please write something about your mood first.";
    moodInput.focus();
    return;
  }

  // Loading state
  btn.classList.add("loading");
  btn.querySelector(".btn-label").textContent = "Analysing…";

  try {
    const res  = await fetch("/api/analyze", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ text }),
    });

    const data = await res.json();

    if (!res.ok) {
      err.textContent = data.error || "Something went wrong. Please try again.";
      return;
    }

    showResult(data);
    loadStats();          // refresh header stats
    moodInput.value = "";
    charCount.textContent = "0";

  } catch (e) {
    err.textContent = "Network error. Is the server running?";
  } finally {
    btn.classList.remove("loading");
    btn.querySelector(".btn-label").textContent = "Analyse My Mood";
  }
}

// ── Render result card ──────────────────────────────────────
function showResult(data) {
  document.getElementById("resultIdle").classList.add("hidden");

  const content = document.getElementById("resultContent");
  content.classList.remove("hidden");
  // Re-trigger animation
  content.style.animation = "none";
  void content.offsetWidth;
  content.style.animation = "";

  document.getElementById("resultEmoji").textContent = data.emoji;
  document.getElementById("resultMood").textContent  = data.mood;

  const polStr = data.polarity >= 0
    ? `+${data.polarity} polarity`
    : `${data.polarity} polarity`;
  document.getElementById("metaPolarity").textContent   = polStr;
  document.getElementById("metaConfidence").textContent = `${data.confidence}% confidence`;

  // Confidence bar width
  document.getElementById("resultBar").style.width = `${data.confidence}%`;

  // Mood-specific note
  const notes = {
    Happy:   "You're radiating positive energy today! ✨",
    Sad:     "It's okay to feel down. Tomorrow is a new page. 💙",
    Angry:   "Deep breath. Your feelings are valid. 🌬️",
    Neutral: "A steady, balanced day — that's perfectly fine too. 🌿",
  };
  document.getElementById("resultNote").textContent = notes[data.mood] || "";
  document.getElementById("resultTime").textContent = `Logged at ${formatTime(data.timestamp)}`;
}

// ══════════════════════════════════════════════
// 4. HISTORY
// ══════════════════════════════════════════════

async function loadHistory() {
  const list = document.getElementById("historyList");
  list.innerHTML = '<div class="loading-state">Loading your history…</div>';

  try {
    const res  = await fetch("/api/history?limit=20");
    const data = await res.json();

    if (!data.length) {
      list.innerHTML = `
        <div class="empty-state">
          <span class="empty-icon">📭</span>
          No entries yet. Start tracking your mood!
        </div>`;
      return;
    }

    list.innerHTML = data.map((entry, i) => `
      <div class="history-item" style="animation-delay:${i * 0.04}s">
        <span class="h-emoji">${entry.emoji}</span>
        <span class="h-text">${escHtml(entry.text)}</span>
        <div class="h-right">
          <span class="h-mood mood-badge-${entry.mood}">${capitalize(entry.mood)}</span>
          <span class="h-time">${formatTime(entry.created_at)}</span>
        </div>
      </div>`
    ).join("");

  } catch (e) {
    list.innerHTML = '<div class="empty-state">Failed to load history.</div>';
  }
}

// ══════════════════════════════════════════════
// 5. TRENDS / CHARTS
// ══════════════════════════════════════════════

async function loadTrends() {
  try {
    const res  = await fetch("/api/trends");
    const data = await res.json();
    drawPieChart(data.distribution);
    drawBarChart(data.daily);
  } catch (e) {
    console.error("Failed to load trends:", e);
  }
}

// Mood colour palette
const MOOD_COLOURS = {
  happy:   "#f59e0b",
  sad:     "#3b82f6",
  angry:   "#ef4444",
  neutral: "#8b5cf6",
};

function drawPieChart(dist) {
  const ctx    = document.getElementById("pieChart").getContext("2d");
  const labels = Object.keys(dist).map(capitalize);
  const values = Object.values(dist);
  const colors = Object.keys(dist).map(k => MOOD_COLOURS[k]);

  if (pieChartInst) pieChartInst.destroy();

  pieChartInst = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{ data: values, backgroundColor: colors, borderWidth: 2, borderColor: "#f5f0e8" }],
    },
    options: {
      cutout: "62%",
      plugins: {
        legend: {
          position: "bottom",
          labels: { padding: 16, usePointStyle: true, pointStyleWidth: 10 },
        },
      },
      animation: { duration: 800, easing: "easeOutQuart" },
    },
  });
}

function drawBarChart(daily) {
  const ctx = document.getElementById("barChart").getContext("2d");

  if (!daily.length) {
    if (barChartInst) barChartInst.destroy();
    return;
  }

  const labels   = daily.map(d => d.date.slice(5));   // "MM-DD"
  const moods    = ["happy", "sad", "angry", "neutral"];

  const datasets = moods.map(mood => ({
    label:           capitalize(mood),
    data:            daily.map(d => d[mood] || 0),
    backgroundColor: MOOD_COLOURS[mood] + "cc",
    borderColor:     MOOD_COLOURS[mood],
    borderWidth:     1,
    borderRadius:    4,
  }));

  if (barChartInst) barChartInst.destroy();

  barChartInst = new Chart(ctx, {
    type: "bar",
    data: { labels, datasets },
    options: {
      responsive: true,
      scales: {
        x: { stacked: true, grid: { display: false }, ticks: { maxTicksLimit: 14 } },
        y: { stacked: true, beginAtZero: true, ticks: { stepSize: 1 } },
      },
      plugins: {
        legend: { position: "bottom", labels: { padding: 14, usePointStyle: true } },
      },
      animation: { duration: 700, easing: "easeOutQuart" },
    },
  });
}

// ══════════════════════════════════════════════
// 6. STATS BAR
// ══════════════════════════════════════════════

async function loadStats() {
  try {
    const res  = await fetch("/api/stats");
    const data = await res.json();

    document.getElementById("statTotal").textContent   = data.total;
    document.getElementById("statToday").textContent   = data.today;
    document.getElementById("statTopMood").textContent =
      data.top_mood ? (MOOD_META[data.top_mood.mood]?.emoji + " " + capitalize(data.top_mood.mood)) : "—";
    document.getElementById("statPolarity").textContent =
      data.avg_polarity > 0 ? `+${data.avg_polarity}` : `${data.avg_polarity}`;
  } catch (e) {
    console.warn("Could not load stats:", e);
  }
}

const MOOD_META = {
  happy: { emoji: "😊" }, sad: { emoji: "😢" },
  angry: { emoji: "😠" }, neutral: { emoji: "😐" },
};

// ══════════════════════════════════════════════
// 7. UTILITIES
// ══════════════════════════════════════════════

function capitalize(str) { return str.charAt(0).toUpperCase() + str.slice(1); }

function escHtml(str) {
  return str
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function formatTime(ts) {
  if (!ts) return "";
  const d = new Date(ts.replace(" ", "T"));
  const now = new Date();
  const diffMs = now - d;
  const diffMin = Math.floor(diffMs / 60000);

  if (diffMin < 1)  return "Just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24)   return `${diffH}h ago`;

  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

// ══════════════════════════════════════════════
// 8. INITIALISE
// ══════════════════════════════════════════════

loadStats();

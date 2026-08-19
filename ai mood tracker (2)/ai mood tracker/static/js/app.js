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
  document.getElementById("resultMood").textContent  = data.emotion || data.mood;

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
  let noteText = notes[data.mood] || "";
  if (data.swing) {
    noteText += (noteText ? " " : "") + `Mood swing: ${data.swing}.`;
  }
  document.getElementById("resultNote").textContent = noteText;
  
  const recContainer = document.getElementById("recommendationsList");
  if (data.reason && data.suggestions) {
    // SHOW BOTH: Clean format + Old recommendations
    const randomItem = (arr) => arr[Math.floor(Math.random() * arr.length)];
    
    const book = randomItem(data.recommendations.books);
    const quote = randomItem(data.recommendations.quotes);
    const activity = randomItem(data.recommendations.activities);
    const movie = randomItem(data.recommendations.movies);
    const music = randomItem(data.recommendations.music);
    
    const suggestionsList = data.suggestions
      .map(s => `<li style="margin-bottom: 12px; padding: 8px 12px; background: rgba(${data.color === '#f59e0b' ? '245,158,11' : data.color === '#3b82f6' ? '59,130,246' : data.color === '#ef4444' ? '239,68,68' : '139,92,246'}, 0.1); border-left: 3px solid ${data.color}; border-radius: 4px; color: rgba(0,0,0,0.8);">• ${s}</li>`)
      .join("");
    
    recContainer.innerHTML = `
      <div style="font-size: 0.95em; line-height: 1.8; color: var(--text-main); margin-bottom: 20px;">
        <p style="margin: 0 0 10px 0;"><strong style="font-size: 1.05em;">Emotion:</strong> ${data.emoji} <strong>${data.emotion || data.mood}</strong></p>
        <p style="margin: 0 0 10px 0;"><strong style="font-size: 1.05em;">Reason:</strong> ${data.reason}</p>
        <p style="margin: 0 0 12px 0;"><strong style="font-size: 1.05em;">Suggestion:</strong></p>
        <ul style="list-style: none; padding: 0; margin: 0;">
          ${suggestionsList}
        </ul>
      </div>
      
      <hr style="border: none; border-top: 1px solid rgba(0,0,0,0.1); margin: 20px 0;">
      
      <h4 style="margin-top: 0; margin-bottom: 12px; font-size: 0.95em; color: var(--text-main); border-bottom: 1px solid rgba(0,0,0,0.1); padding-bottom: 6px;">More Suggestions:</h4>
      <ul style="list-style: none; padding: 0; font-size: 0.85em; margin: 0; line-height: 1.6; color: rgba(0,0,0,0.7);">
          <li style="margin-bottom: 8px;">📚 <strong>Reads:</strong> <a href="https://www.goodreads.com/search?q=${encodeURIComponent(book)}" target="_blank" style="color: #2563eb; text-decoration: none;" rel="noopener noreferrer">${book}</a></li>
          <li style="margin-bottom: 8px;">💬 <strong>Quote:</strong> "${quote}"</li>
          <li style="margin-bottom: 8px;">🧘 <strong>Activity:</strong> <a href="https://www.google.com/search?q=${encodeURIComponent(activity)}" target="_blank" style="color: #2563eb; text-decoration: none;" rel="noopener noreferrer">${activity}</a></li>
          <li style="margin-bottom: 8px;">🎬 <strong>Watch:</strong> <a href="https://www.youtube.com/results?search_query=${encodeURIComponent(movie + ' movie trailer')}" target="_blank" style="color: #2563eb; text-decoration: none;" rel="noopener noreferrer">${movie}</a></li>
          <li style="margin-bottom: 0;">🎵 <strong>Listen:</strong> <a href="https://www.youtube.com/results?search_query=${encodeURIComponent(music)}" target="_blank" style="color: #2563eb; text-decoration: none;" rel="noopener noreferrer">${music}</a></li>
      </ul>
    `;
    recContainer.style.display = "block";
  } else if (data.recommendations) {
    // FALLBACK: Show old recommendations format
    const randomItem = (arr) => arr[Math.floor(Math.random() * arr.length)];
    
    const book = randomItem(data.recommendations.books);
    const quote = randomItem(data.recommendations.quotes);
    const activity = randomItem(data.recommendations.activities);
    const movie = randomItem(data.recommendations.movies);
    const music = randomItem(data.recommendations.music);

    recContainer.innerHTML = `
      <h4 style="margin-top: 0; margin-bottom: 12px; font-size: 0.95em; color: var(--text-main); border-bottom: 1px solid rgba(0,0,0,0.1); padding-bottom: 6px;">Suggestions for your mood:</h4>
      <ul style="list-style: none; padding: 0; font-size: 0.85em; margin: 0; line-height: 1.6; color: rgba(0,0,0,0.7);">
          <li style="margin-bottom: 8px;">📚 <strong>Reads:</strong> <a href="https://www.goodreads.com/search?q=${encodeURIComponent(book)}" target="_blank" style="color: #2563eb; text-decoration: none;" rel="noopener noreferrer">${book}</a></li>
          <li style="margin-bottom: 8px;">💬 <strong>Quote:</strong> "${quote}"</li>
          <li style="margin-bottom: 8px;">🧘 <strong>Activity:</strong> <a href="https://www.google.com/search?q=${encodeURIComponent(activity)}" target="_blank" style="color: #2563eb; text-decoration: none;" rel="noopener noreferrer">${activity}</a></li>
          <li style="margin-bottom: 8px;">🎬 <strong>Watch:</strong> <a href="https://www.youtube.com/results?search_query=${encodeURIComponent(movie + ' movie trailer')}" target="_blank" style="color: #2563eb; text-decoration: none;" rel="noopener noreferrer">${movie}</a></li>
          <li style="margin-bottom: 0;">🎵 <strong>Listen:</strong> <a href="https://www.youtube.com/results?search_query=${encodeURIComponent(music)}" target="_blank" style="color: #2563eb; text-decoration: none;" rel="noopener noreferrer">${music}</a></li>
      </ul>
    `;
    recContainer.style.display = "block";
  } else {
    recContainer.style.display = "none";
  }

  document.getElementById("resultTime").textContent = `Logged at ${formatTime(data.timestamp)}`;
  
  // Link mood to AI Companion
  lastDetectedMood = data.mood;
  const initialChatMsg = document.querySelector(".ai-message");
  if (initialChatMsg && chatMessages.length === 0) {
      initialChatMsg.textContent = `I see from your tracker that you're feeling ${data.mood} right now. I'm here if you want to talk about it!`;
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
  happy: "#f59e0b",
  excited: "#ff6b35",
  proud: "#6366f1",
  relaxed: "#10b981",
  loved: "#ec4899",
  sad: "#3b82f6",
  angry: "#ef4444",
  fear: "#7c3aed",
  anxiety: "#a78bfa",
  stress: "#f97316",
  lonely: "#0e7490",
  disappointed: "#6b7280",
  neutral: "#8b5cf6",
  confused: "#eab308",
  surprise: "#fb923c",
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
  const moods    = Object.keys(MOOD_COLOURS);

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

// ══════════════════════════════════════════════
// 9. AI COMPANION CHAT
// ══════════════════════════════════════════════

let lastDetectedMood = "unknown";
const chatMessages = [];
const chatHistoryDOM = document.getElementById("chatHistory");
const chatInput = document.getElementById("chatInput");
const sendChatBtn = document.getElementById("sendChatBtn");

if (chatInput) {
  chatInput.addEventListener("keydown", e => {
    if (e.key === "Enter") sendChatMessage();
  });
}

function toggleChat() {
  const panel = document.getElementById("floatingChatPanel");
  if (panel.style.display === "none" || !panel.style.display) {
    panel.style.display = "flex";
  } else {
    panel.style.display = "none";
  }
}

function appendChat(role, content) {
  if (!chatHistoryDOM) return;
  
  const msgDiv = document.createElement("div");
  msgDiv.className = "chat-message";
  
  if (role === "user") {
    // Make user background #2563eb (blue) and align right
    msgDiv.style = "background: #2563eb; color: white; padding: 12px 18px; border-radius: 12px; align-self: flex-end; max-width: 80%; margin-left: auto;";
  } else {
    // Make AI background light blue and align left
    msgDiv.style = "background: rgba(37,99,235,0.1); color: #1e3a8a; padding: 12px 18px; border-radius: 12px; align-self: flex-start; max-width: 80%; margin-right: auto;";
  }
  
  msgDiv.textContent = content;
  chatHistoryDOM.appendChild(msgDiv);
  chatHistoryDOM.scrollTop = chatHistoryDOM.scrollHeight;
}

async function sendChatMessage() {
  const text = chatInput.value.trim();
  if (!text) return;
  
  chatInput.value = "";
  chatInput.disabled = true;
  sendChatBtn.disabled = true;
  sendChatBtn.textContent = "...";
  
  appendChat("user", text);
  chatMessages.push({ role: "user", content: text });
  
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ 
          messages: chatMessages,
          current_mood: lastDetectedMood
      })
    });
    
    const data = await res.json();
    
    if (!res.ok) {
      appendChat("assistant", "Sorry, I'm having trouble connecting to my servers right now.");
    } else {
      appendChat("assistant", data.response);
      chatMessages.push({ role: "assistant", content: data.response });
    }
  } catch (e) {
    appendChat("assistant", "Network error. Please try again.");
  } finally {
    chatInput.disabled = false;
    sendChatBtn.disabled = false;
    sendChatBtn.textContent = "Send";
    chatInput.focus();
  }
}

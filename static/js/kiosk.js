function getCookie(name) {
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
  return match ? decodeURIComponent(match[2]) : null;
}

const video = document.getElementById('video');
const overlay = document.getElementById('overlay');
const ctx = overlay.getContext('2d');
const toast = document.getElementById('toast');
const markedList = document.getElementById('markedList');
const liveCount = document.getElementById('liveCount');
const cameraError = document.getElementById('cameraError');

let inFlight = false;
let markedIds = new Set();
let consecutiveFailures = 0;
const BASE_INTERVAL_MS = 1500;
const MAX_INTERVAL_MS = 15000;
let pollTimer = null;

function scheduleNextPoll() {
  // Exponential backoff on repeated failures (bad camera frame, network
  // blip, server hiccup) so a broken kiosk doesn't hammer the server
  // every 1.5s forever - caps at 15s between attempts.
  const delay = Math.min(BASE_INTERVAL_MS * Math.pow(2, consecutiveFailures), MAX_INTERVAL_MS);
  clearTimeout(pollTimer);
  pollTimer = setTimeout(captureAndSend, delay);
}

// Short beep via Web Audio API - no audio file needed.
function beep() {
  const ctxA = new (window.AudioContext || window.webkitAudioContext)();
  const osc = ctxA.createOscillator();
  const gain = ctxA.createGain();
  osc.connect(gain);
  gain.connect(ctxA.destination);
  osc.frequency.value = 880;
  gain.gain.setValueAtTime(0.2, ctxA.currentTime);
  osc.start();
  osc.stop(ctxA.currentTime + 0.15);
}

function showToast(text) {
  toast.textContent = text;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 2500);
}

function addToSidebar(name, roll, time) {
  const li = document.createElement('li');
  li.style.padding = '8px 0';
  li.style.borderBottom = '1px solid var(--border)';
  li.innerHTML = `<strong>${name}</strong><br><span class="muted">${roll} · ${time}</span>`;
  markedList.prepend(li);
  liveCount.textContent = `(${markedList.children.length})`;
}

function drawBox(face) {
  const { x1, y1, x2, y2 } = face.bbox;
  let color = '#b23b3b'; // unknown = red
  let label = 'Unknown';

  if (face.status === 'matched') {
    color = face.already_marked ? '#c78a1f' : '#1a4d3a'; // amber if already marked, green if new
    label = face.already_marked ? `${face.name} — Already marked ✓` : `${face.name} (${face.roll_number})`;
  } else if (face.status === 'low_confidence') {
    color = '#c78a1f';
    label = `${face.name}? (uncertain)`;
  }

  ctx.strokeStyle = color;
  ctx.lineWidth = 3;
  ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
  ctx.fillStyle = color;
  ctx.font = '16px Inter, sans-serif';
  const textWidth = ctx.measureText(label).width;
  ctx.fillRect(x1, y1 - 24, textWidth + 12, 24);
  ctx.fillStyle = '#fff';
  ctx.fillText(label, x1 + 6, y1 - 6);
}

async function captureAndSend() {
  if (inFlight) { scheduleNextPoll(); return; }
  if (video.videoWidth === 0) { scheduleNextPoll(); return; }
  inFlight = true;

  const tmp = document.createElement('canvas');
  tmp.width = video.videoWidth;
  tmp.height = video.videoHeight;
  tmp.getContext('2d').drawImage(video, 0, 0);
  const image = tmp.toDataURL('image/jpeg', 0.8);

  // Liveness gate: if enabled, only let the backend mark attendance when a
  // real blink was seen in the last 3 seconds (blocks a printed photo).
  const livenessOk = !window.LIVENESS_REQUIRED || (Date.now() - (window.lastBlinkAt || 0) < 3000);
  const sessionIdToSend = livenessOk ? window.SESSION_ID : null;

  try {
    const res = await fetch(window.RECOGNIZE_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken'),
      },
      body: JSON.stringify({ image, session_id: sessionIdToSend }),
    });
    if (!res.ok || !data.ok) {
      consecutiveFailures += 1;
      setConnectionState(false);
      return;
    }

    consecutiveFailures = 0;
    setConnectionState(true);

    overlay.width = video.videoWidth;
    overlay.height = video.videoHeight;
    ctx.clearRect(0, 0, overlay.width, overlay.height);

    for (const face of data.faces) {
      drawBox(face);
      if (face.status === 'matched' && face.marked && !markedIds.has(face.student_id)) {
        markedIds.add(face.student_id);
        beep();
        showToast(`✓ ${face.name} — Marked ${face.marked_at}`);
        addToSidebar(face.name, face.roll_number, face.marked_at);
      }
    }
  } catch (e) {
    consecutiveFailures += 1;
    setConnectionState(false);
  } finally {
    inFlight = false;
    scheduleNextPoll();
  }
}

function setConnectionState(ok) {
  const badge = document.getElementById('connBadge');
  if (!badge) return;
  if (ok) {
    badge.style.display = 'none';
  } else {
    badge.style.display = 'inline-block';
    badge.textContent = consecutiveFailures > 2 ? 'Reconnecting…' : 'Connection issue';
  }
}

navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } })
  .then((stream) => {
    video.srcObject = stream;
    scheduleNextPoll();
  })
  .catch(() => { cameraError.style.display = 'block'; });

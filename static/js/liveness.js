/*
Client-side liveness check: blink detection using MediaPipe FaceMesh's
eye landmarks (Eye Aspect Ratio). Runs client-side (not server-side)
because it needs a per-frame landmark stream at a higher rate than the
1.5s recognition poll, and keeps the heavier MediaPipe model off the
Django/InsightFace process entirely.

Exposes: window.lastBlinkAt (timestamp, ms) - kiosk.js only allows a
mark to be submitted if a blink happened within the last 3 seconds,
so a printed photo held up to the camera can't check someone in.
*/
window.lastBlinkAt = 0;

const LEFT_EYE = [33, 160, 158, 133, 153, 144];
const RIGHT_EYE = [362, 385, 387, 263, 373, 380];
const EAR_BLINK_THRESHOLD = 0.21;

function dist(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function eyeAspectRatio(landmarks, idx) {
  const p = idx.map((i) => landmarks[i]);
  const vertical1 = dist(p[1], p[5]);
  const vertical2 = dist(p[2], p[4]);
  const horizontal = dist(p[0], p[3]);
  return (vertical1 + vertical2) / (2.0 * horizontal);
}

let wasEyeClosed = false;

function onResults(results) {
  if (!results.multiFaceLandmarks || results.multiFaceLandmarks.length === 0) return;
  const landmarks = results.multiFaceLandmarks[0];

  const leftEAR = eyeAspectRatio(landmarks, LEFT_EYE);
  const rightEAR = eyeAspectRatio(landmarks, RIGHT_EYE);
  const avgEAR = (leftEAR + rightEAR) / 2;

  const eyeClosed = avgEAR < EAR_BLINK_THRESHOLD;
  if (wasEyeClosed && !eyeClosed) {
    // transition: closed -> open == one completed blink
    window.lastBlinkAt = Date.now();
  }
  wasEyeClosed = eyeClosed;
}

document.addEventListener('DOMContentLoaded', () => {
  const video = document.getElementById('video');
  const faceMesh = new FaceMesh({
    locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`,
  });
  faceMesh.setOptions({ maxNumFaces: 1, refineLandmarks: true, minDetectionConfidence: 0.5, minTrackingConfidence: 0.5 });
  faceMesh.onResults(onResults);

  async function tick() {
    if (video.readyState >= 2) {
      await faceMesh.send({ image: video });
    }
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
});

function getCookie(name) {
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
  return match ? decodeURIComponent(match[2]) : null;
}

const angleLabels = {
  straight: 'Look straight at the camera',
  left: 'Turn your head slightly LEFT',
  right: 'Turn your head slightly RIGHT',
  up: 'Tilt your chin slightly UP',
  down: 'Tilt your chin slightly DOWN',
};

const angles = window.ENROLL_ANGLES || [];
let angleIndex = 0;

const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const promptEl = document.getElementById('prompt');
const errorEl = document.getElementById('error');
const doneEl = document.getElementById('done');
const captureBtn = document.getElementById('captureBtn');
const dots = document.querySelectorAll('#dots .dot');

function updatePrompt() {
  if (angleIndex >= angles.length) {
    promptEl.style.display = 'none';
    captureBtn.style.display = 'none';
    doneEl.style.display = 'inline-block';
    return;
  }
  promptEl.textContent = angleLabels[angles[angleIndex]] || 'Look at the camera';
}

navigator.mediaDevices.getUserMedia({ video: { width: 480, height: 360 } })
  .then((stream) => { video.srcObject = stream; })
  .catch(() => { errorEl.textContent = 'Camera access denied. Please allow camera permission and reload.'; });

captureBtn.addEventListener('click', async () => {
  if (angleIndex >= angles.length) return;
  errorEl.textContent = '';
  captureBtn.disabled = true;

  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext('2d').drawImage(video, 0, 0);
  const image = canvas.toDataURL('image/jpeg', 0.9);

  try {
    const res = await fetch(window.ENROLL_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken'),
      },
      body: JSON.stringify({ image }),
    });
    const data = await res.json();

    if (!res.ok || !data.ok) {
      errorEl.textContent = data.message || 'Could not capture this frame, try again.';
    } else {
      dots[angleIndex].style.background = '#1a4d3a';
      angleIndex += 1;
      updatePrompt();
    }
  } catch (e) {
    errorEl.textContent = 'Network error, try again.';
  } finally {
    captureBtn.disabled = false;
  }
});

updatePrompt();

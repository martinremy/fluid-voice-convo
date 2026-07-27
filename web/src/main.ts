const startButton = document.getElementById("start") as HTMLButtonElement;
const statusEl = document.getElementById("status") as HTMLParagraphElement;

let pc: RTCPeerConnection | null = null;

function setStatus(text: string): void {
  statusEl.textContent = text;
}

async function startLoopback(): Promise<void> {
  startButton.disabled = true;
  setStatus("Requesting microphone…");

  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

  setStatus("Creating peer connection…");
  pc = new RTCPeerConnection();

  for (const track of stream.getTracks()) {
    pc.addTrack(track, stream);
  }

  pc.ontrack = (event) => {
    const audio = new Audio();
    audio.srcObject = event.streams[0];
    audio.play().catch((err) => setStatus(`Playback error: ${err}`));
  };

  pc.oniceconnectionstatechange = () => {
    if (pc) setStatus(`ICE: ${pc.iceConnectionState}`);
  };

  setStatus("Creating offer…");
  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);

  setStatus("Sending offer to server…");
  const response = await fetch("/offer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sdp: offer.sdp, type: offer.type }),
  });
  if (!response.ok) {
    setStatus(`Server rejected offer: ${response.status}`);
    startButton.disabled = false;
    return;
  }

  const answer = await response.json();
  await pc.setRemoteDescription(answer);
  setStatus("Connected — speak with headphones on");
}

startButton.addEventListener("click", () => {
  startLoopback().catch((err) => {
    setStatus(`Error: ${err}`);
    startButton.disabled = false;
  });
});

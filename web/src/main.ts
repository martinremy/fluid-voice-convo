const startButton = document.getElementById("start") as HTMLButtonElement;
const statusEl = document.getElementById("status") as HTMLParagraphElement;
const partialEl = document.getElementById("partial") as HTMLParagraphElement;
const committedEl = document.getElementById(
  "committed-turns",
) as HTMLDivElement;

let pc: RTCPeerConnection | null = null;

function setStatus(text: string): void {
  statusEl.textContent = text;
}

function renderTranscriptEvent(kind: string, text: string): void {
  if (kind === "closed") {
    partialEl.textContent = "";
    return;
  }
  if (kind === "error") {
    partialEl.textContent = "";
    const err = document.createElement("p");
    err.className = "error";
    err.textContent = `Error: ${text}`;
    committedEl.appendChild(err);
    return;
  }
  if (kind === "partial") {
    partialEl.textContent = text;
    return;
  }
  if (kind === "committed") {
    partialEl.textContent = "";
    const turn = document.createElement("p");
    turn.textContent = text;
    committedEl.appendChild(turn);
  }
}

async function startLoopback(): Promise<void> {
  startButton.disabled = true;
  setStatus("Requesting microphone…");

  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

  setStatus("Creating peer connection…");
  pc = new RTCPeerConnection();

  // The browser creates the transcript data channel; the server receives it
  // and sends transcript events back as JSON {kind, text}.
  const transcriptChannel = pc.createDataChannel("transcript");
  transcriptChannel.onmessage = (event) => {
    try {
      const { kind, text } = JSON.parse(event.data) as {
        kind: string;
        text: string;
      };
      renderTranscriptEvent(kind, text);
    } catch {
      // ignore malformed messages
    }
  };

  for (const track of stream.getTracks()) {
    pc.addTrack(track, stream);
  }

  pc.oniceconnectionstatechange = () => {
    if (pc) setStatus(`ICE: ${pc.iceConnectionState}`);
  };

  // Log data channel state so we can see whether SCTP establishes. This is the
  // layer that must come up before the server can send transcript events.
  const logDcState = () =>
    console.log(`[transcript channel] state=${transcriptChannel.readyState}`);
  logDcState();
  transcriptChannel.onopen = () => {
    logDcState();
    setStatus("Connected — speak (transcript appears below)");
  };
  transcriptChannel.onclose = logDcState;
  transcriptChannel.onerror = (e) =>
    console.log("[transcript channel] error", e);

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
  // Don't claim "Connected" here — ICE/SCTP may still be negotiating. The
  // data channel's onopen handler sets the connected status once SCTP is up.
  setStatus("Connecting…");
}

startButton.addEventListener("click", () => {
  startLoopback().catch((err) => {
    setStatus(`Error: ${err}`);
    startButton.disabled = false;
  });
});

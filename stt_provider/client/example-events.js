const socket = new WebSocket("ws://localhost:8000/stt/stream?api_key=YOUR_KEY");

socket.onmessage = (event) => {
  const data = JSON.parse(event.data);

  switch (data.type) {
    case "session.started":
      console.log("STT session started:", data);
      break;
    case "transcript.partial":
      console.log("PARTIAL:", data.text);
      break;
    case "transcript.final":
      console.log("FINAL:", data.text);
      break;
    case "session.flushed":
      console.log("Session flushed");
      break;
    default:
      console.log("Unknown event:", data);
  }
};

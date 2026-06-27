/** Minimal mic recorder using the MediaRecorder API. Returns a webm/opus blob,
 *  which Sarvam STT accepts directly. */
import { useRef, useState } from "react";

export function useRecorder() {
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const resolveRef = useRef<((b: Blob) => void) | null>(null);

  async function start() {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      chunksRef.current = [];
      mr.ondataavailable = (e) => e.data.size && chunksRef.current.push(e.data);
      mr.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        resolveRef.current?.(blob);
      };
      mediaRef.current = mr;
      mr.start();
      setRecording(true);
    } catch (e) {
      setError("मायक्रोफोन उपलब्ध नाही · microphone unavailable");
    }
  }

  function stop(): Promise<Blob> {
    return new Promise((resolve) => {
      resolveRef.current = resolve;
      mediaRef.current?.stop();
      setRecording(false);
    });
  }

  return { recording, error, start, stop };
}

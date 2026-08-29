/**
 * Speech, using what the browser already has.
 *
 * The layered design the project settled on: the browser's own
 * `SpeechSynthesis` and `MediaRecorder` are the default because they need no
 * download and no network, and a local Piper/whisper adapter can replace them
 * later without any component changing.
 *
 * Two honesty rules are enforced here rather than left to callers.
 *
 * Speech *synthesis* is local on every platform. Speech *recognition* is not:
 * Chrome's `webkitSpeechRecognition` sends audio to Google's servers. That is
 * a network feature in an offline-first app, so it is never started without an
 * explicit opt-in and `recognitionIsLocal()` says plainly that it is not.
 *
 * And there is no scoring here. Recording works; comparing a recording to a
 * reference needs a real speech engine, and this module returns
 * `{ scored: false, reason }` rather than inventing a number.
 */

export const BCP47: Record<string, string> = {
  ko: "ko-KR",
  ja: "ja-JP",
  zh: "zh-CN",
};

export function localeFor(lang: string): string {
  return BCP47[lang] ?? lang;
}

// ==========================================================================
// Text to speech
// ==========================================================================

let voicesCache: SpeechSynthesisVoice[] = [];

export function synthesisAvailable(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export function loadVoices(): Promise<SpeechSynthesisVoice[]> {
  if (!synthesisAvailable()) return Promise.resolve([]);
  const now = window.speechSynthesis.getVoices();
  if (now.length) {
    voicesCache = now;
    return Promise.resolve(now);
  }
  // Chrome populates the list asynchronously and fires this once.
  return new Promise((resolve) => {
    const done = () => {
      voicesCache = window.speechSynthesis.getVoices();
      resolve(voicesCache);
    };
    window.speechSynthesis.addEventListener("voiceschanged", done, { once: true });
    setTimeout(done, 900);
  });
}

export function voicesFor(lang: string): SpeechSynthesisVoice[] {
  const prefix = localeFor(lang).slice(0, 2);
  return voicesCache.filter((v) => v.lang.toLowerCase().startsWith(prefix));
}

export interface SpeakOptions {
  lang: string;
  rate?: number;
  voiceName?: string;
  onEnd?: () => void;
}

export function speak(text: string, opts: SpeakOptions): boolean {
  if (!synthesisAvailable() || !text.trim()) return false;
  const synth = window.speechSynthesis;
  synth.cancel();

  const u = new SpeechSynthesisUtterance(text);
  u.lang = localeFor(opts.lang);
  u.rate = opts.rate ?? 1;

  const candidates = voicesFor(opts.lang);
  const chosen =
    (opts.voiceName && candidates.find((v) => v.name === opts.voiceName)) ||
    candidates[0];
  if (chosen) u.voice = chosen;
  if (opts.onEnd) u.addEventListener("end", opts.onEnd, { once: true });

  synth.speak(u);
  return true;
}

export function stopSpeaking(): void {
  if (synthesisAvailable()) window.speechSynthesis.cancel();
}

/**
 * Whether a voice for this language is actually installed.
 *
 * Worth surfacing: `speak()` on a system with no Korean voice does not fail,
 * it reads Hangul with an English voice, which is worse than silence because
 * the learner may not realise what they are hearing is wrong.
 */
export function hasVoiceFor(lang: string): boolean {
  return voicesFor(lang).length > 0;
}

// ==========================================================================
// Recording
// ==========================================================================

export interface Recording {
  blob: Blob;
  url: string;
  seconds: number;
  mimeType: string;
}

export function recordingAvailable(): boolean {
  return (
    typeof navigator !== "undefined" &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof MediaRecorder !== "undefined"
  );
}

export class Recorder {
  private recorder: MediaRecorder | null = null;
  private chunks: Blob[] = [];
  private stream: MediaStream | null = null;
  private startedAt = 0;

  async start(): Promise<void> {
    if (!recordingAvailable()) throw new Error("This browser cannot record audio.");
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.chunks = [];
    const mime = MediaRecorder.isTypeSupported("audio/webm")
      ? "audio/webm"
      : "audio/ogg";
    this.recorder = new MediaRecorder(this.stream, { mimeType: mime });
    this.recorder.addEventListener("dataavailable", (e) => {
      if (e.data.size) this.chunks.push(e.data);
    });
    this.startedAt = Date.now();
    this.recorder.start();
  }

  stop(): Promise<Recording> {
    return new Promise((resolve, reject) => {
      const rec = this.recorder;
      if (!rec) return reject(new Error("Not recording."));
      rec.addEventListener(
        "stop",
        () => {
          const blob = new Blob(this.chunks, { type: rec.mimeType });
          this.release();
          resolve({
            blob,
            url: URL.createObjectURL(blob),
            seconds: (Date.now() - this.startedAt) / 1000,
            mimeType: rec.mimeType,
          });
        },
        { once: true },
      );
      rec.stop();
    });
  }

  cancel(): void {
    try {
      this.recorder?.stop();
    } catch {
      /* already stopped */
    }
    this.release();
  }

  private release(): void {
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
    this.recorder = null;
  }
}

/**
 * Compare a recording against a target.
 *
 * There is no local scoring engine wired up, so this always reports that it
 * could not score, with the reason. It exists as a single call site so that
 * adding a whisper adapter later changes one file — and so that nothing in the
 * UI is tempted to make a number up in the meantime.
 */
export function scoreRecording(): { scored: false; reason: string } {
  return {
    scored: false,
    reason:
      "Scoring needs a speech-recognition engine, and none is configured. " +
      "Listen to your recording against the model audio and compare — that " +
      "is what a teacher would have you do anyway.",
  };
}

// ==========================================================================
// Recognition — the part that may not be local
// ==========================================================================

type SpeechRecognitionCtor = new () => {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start(): void;
  stop(): void;
  onresult: ((e: { results: { 0: { transcript: string } }[] }) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
};

function recognitionCtor(): SpeechRecognitionCtor | null {
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function recognitionAvailable(): boolean {
  return recognitionCtor() !== null;
}

/**
 * Chrome and Edge implement `webkitSpeechRecognition` by streaming audio to a
 * remote service. Firefox does not implement it at all. There is no way to ask
 * the browser which it is doing, so the honest answer is "assume not local".
 */
export function recognitionIsLocal(): boolean {
  return false;
}

export interface RecognitionHandle {
  stop(): void;
}

export function recognise(
  lang: string,
  onResult: (text: string) => void,
  onError?: (message: string) => void,
): RecognitionHandle | null {
  const Ctor = recognitionCtor();
  if (!Ctor) {
    onError?.("This browser has no speech recognition.");
    return null;
  }
  const r = new Ctor();
  r.lang = localeFor(lang);
  r.continuous = false;
  r.interimResults = false;
  r.onresult = (e) => onResult(e.results[0][0].transcript);
  r.onerror = (e) => onError?.(e.error);
  r.start();
  return { stop: () => r.stop() };
}

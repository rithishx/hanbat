/**
 * The only place that talks to the backend.
 *
 * Two things are enforced here rather than in components. Every content call
 * carries a language code, because the API is language-scoped and a call that
 * forgets one silently gets the learner's active language — which is right
 * often enough to hide the bug and wrong often enough to matter. And a 409 is
 * not an error to be swallowed: it means "this language is not ready yet", and
 * it carries the reason, which the UI shows rather than rendering an empty page.
 */

import type {
  AiStatus, Confusion, Dashboard, Difficulty, Exercise, Explanation, Grade,
  GradeOutcome, GrammarPoint, HealthReport, Language, Lesson, LessonSummary,
  LevelDetails, Me, Mistake, OnboardingQuestion, Recommendation, ReviewItem,
  RuntimeInfo, ScriptUnit, SearchResults, Settings, SpeechCapabilities,
  SrsSummary, VocabWord, WritingSystem,
} from "./types";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** A language that is registered but not finished. Rendered as a roadmap. */
export class LanguageNotReady extends ApiError {
  constructor(readonly language: string, readonly note: string) {
    super(409, note || "This language is not ready yet.");
    this.name = "LanguageNotReady";
  }
}

type Query = Record<string, string | number | boolean | undefined | null>;

function qs(params?: Query): string {
  if (!params) return "";
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

async function request<T>(
  path: string,
  init?: RequestInit & { params?: Query },
): Promise<T> {
  const { params, ...rest } = init ?? {};
  let res: Response;
  try {
    res = await fetch(`/api${path}${qs(params)}`, {
      headers: { "Content-Type": "application/json" },
      ...rest,
    });
  } catch (e) {
    // The backend is not running. Say that, rather than "failed to fetch".
    throw new ApiError(
      0,
      "Cannot reach the local server. Is it running on port 8756?",
      e,
    );
  }

  if (res.status === 204) return undefined as T;

  let body: unknown;
  const text = await res.text();
  try {
    body = text ? JSON.parse(text) : undefined;
  } catch {
    body = text;
  }

  if (!res.ok) {
    const detail = (body as { detail?: unknown })?.detail ?? body;
    if (res.status === 409 && detail && typeof detail === "object") {
      const d = detail as { error?: string; message?: string; language?: string };
      if (d.error === "language_not_ready") {
        throw new LanguageNotReady(d.language ?? "", d.message ?? "");
      }
    }
    const message =
      typeof detail === "string"
        ? detail
        : (detail as { message?: string })?.message ?? `Request failed (${res.status})`;
    throw new ApiError(res.status, message, detail);
  }
  return body as T;
}

const get = <T,>(path: string, params?: Query) => request<T>(path, { params });
const post = <T,>(path: string, body?: unknown, params?: Query) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body ?? {}), params });
const patch = <T,>(path: string, body?: unknown, params?: Query) =>
  request<T>(path, { method: "PATCH", body: JSON.stringify(body ?? {}), params });

// ==========================================================================

export const api = {
  // -- the app itself ------------------------------------------------------
  health: () => get<HealthReport>("/health"),
  runtime: () => get<RuntimeInfo>("/runtime"),
  reloadContent: () => post<{ ok: boolean; counts: unknown }>("/content/reload"),

  // -- learner -------------------------------------------------------------
  me: () => get<Me>("/me"),
  onboardingQuestions: () =>
    get<{ greeting: { native: string; english: string }; questions: OnboardingQuestion[] }>(
      "/onboarding/questions",
    ),
  onboard: (body: {
    language: string;
    experience: string;
    goal?: string;
    minutes?: number;
    name?: string;
  }) =>
    post<{ starting_level: string; needs_placement: boolean; message?: string }>(
      "/onboarding",
      body,
    ),
  placementTest: (lang: string, seed?: number) =>
    get<{ sections: { skill: string; title: string; exercises: Exercise[] }[] }>(
      "/placement",
      { lang, seed },
    ),
  submitPlacement: (lang: string, scores: Record<string, number>) =>
    post<{ level: string; details: LevelDetails; message: string }>(
      "/placement",
      { scores },
      { lang },
    ),
  settings: () => get<{ settings: Settings }>("/settings"),
  // PATCH, not POST: a settings save sends only what changed, and posting a
  // partial object to a replace endpoint would silently reset the rest.
  saveSettings: (changes: Partial<Settings>) =>
    patch<{ settings: Settings }>("/settings", { settings: changes }),

  // -- languages -----------------------------------------------------------
  languages: () =>
    get<{ languages: Language[]; active: string; default: string }>("/languages"),
  language: (code: string) => get<Language>(`/languages/${code}`),
  setActiveLanguage: (language: string) =>
    post<{ active: string }>("/languages/active", { language }),

  // -- content -------------------------------------------------------------
  lessons: (lang: string) =>
    get<{ language: string; lessons: LessonSummary[] }>("/lessons", { lang }),
  lesson: (id: string, lang: string) => get<Lesson>(`/lessons/${id}`, { lang }),
  lessonExercises: (id: string, lang: string, opts?: { step?: string; seed?: number }) =>
    get<{ lesson_id: string; count: number; exercises: Exercise[] }>(
      `/lessons/${id}/exercises`,
      { lang, ...opts },
    ),
  saveLessonProgress: (
    id: string,
    lang: string,
    body: { status: string; score?: number; seconds?: number },
  ) => post<{ ok: boolean; xp?: number }>(`/lessons/${id}/progress`, body, { lang }),
  units: (lang: string) =>
    get<{ units: { id: string; level: string; lessons: number; completed: number; percent: number }[] }>(
      "/units",
      { lang },
    ),

  vocab: (lang: string, params?: Query) =>
    get<{ count: number; words: VocabWord[] }>("/vocab", { lang, ...params }),
  vocabTopics: (lang: string) =>
    get<{ topics: { topic: string; count: number }[] }>("/vocab/topics", { lang }),
  vocabWord: (id: string, lang: string) => get<VocabWord>(`/vocab/${id}`, { lang }),

  grammar: (lang: string, level?: string) =>
    get<{ points: GrammarPoint[] }>("/grammar", { lang, level }),
  grammarPoint: (id: string, lang: string) => get<GrammarPoint>(`/grammar/${id}`, { lang }),

  writingSystems: (lang: string) =>
    get<{ writing_systems: WritingSystem[] }>("/writing", { lang }),
  scriptUnits: (system: string, lang: string) =>
    get<{ units: ScriptUnit[]; writing_system: string }>(`/writing/${system}/units`, { lang }),
  compose: (parts: string[], lang: string) =>
    get<{ result: string; formula?: string }>("/writing/compose", {
      parts: parts.join(","),
      lang,
    }),
  decompose: (text: string, lang: string) =>
    get<{ parts: { char: string; formula?: string; parts?: string[] }[] }>(
      "/writing/decompose",
      { text, lang },
    ),

  pronounce: (text: string, lang: string, casual?: boolean) =>
    get<Explanation>("/pronounce", { text, lang, casual }),
  transliterate: (text: string, lang: string, level?: number) =>
    get<{
      text: string;
      scheme: string;
      full: string;
      faded: string;
      fully_removable: boolean;
      warnings: string[];
    }>("/transliterate", { text, lang, level }),
  conjugate: (word: string, lang: string, pos?: string) =>
    get<Record<string, unknown>>("/conjugate", { word, lang, pos }),
  search: (q: string, lang: string) => get<SearchResults>("/search", { q, lang }),

  // -- study ---------------------------------------------------------------
  /** `spec` is a generator spec — the same shape a lesson step carries. */
  practice: (
    lang: string,
    body: { spec: Record<string, unknown>; seed?: number; level?: string },
  ) => post<{ count: number; exercises: Exercise[] }>("/practice", body, { lang }),
  practiceKinds: (lang: string) =>
    get<{ kinds: string[] }>("/practice/kinds", { lang }),
  answer: (
    lang: string,
    body: {
      exercise_id?: string;
      kind: string;
      skill: string;
      correct: boolean;
      item_type?: string;
      item_id?: string;
      expected?: string;
      given?: string;
      seconds?: number;
    },
  ) => post<{ ok: boolean; confusion?: Confusion | null }>("/answer", body, { lang }),
  session: (lang: string, body: { seconds: number; kind?: string }) =>
    post<{ ok: boolean; minutes_today: number }>("/session", body, { lang }),

  reviewQueue: (lang: string, limit?: number) =>
    get<{ count: number; items: ReviewItem[]; summary: SrsSummary }>("/review/queue", {
      lang,
      limit,
    }),
  mistakeSummary: (lang: string) =>
    get<{ total: number; by_category: Record<string, number>; mistakes: Mistake[] }>(
      "/mistakes",
      { lang },
    ),
  reviewSummary: (lang: string) =>
    get<SrsSummary & { forecast: { date: string; count: number }[] }>("/review/summary", {
      lang,
    }),
  gradeReview: (
    lang: string,
    body: { item_type: string; item_id: string; grade: Grade },
  ) => post<GradeOutcome>("/review/grade", body, { lang }),
  enqueue: (lang: string, items: { item_type: string; item_id: string }[]) =>
    post<{ added: number }>("/review/enqueue", { items }, { lang }),

  // -- progress ------------------------------------------------------------
  dashboard: (lang: string) => get<Dashboard>("/dashboard", { lang }),
  progress: (lang: string) =>
    get<{
      language: string;
      level_scheme: string;
      ladder: LevelDetails[];
      level: string;
      skills: Record<string, unknown>;
      [k: string]: unknown;
    }>("/progress", { lang }),
  progressAll: () =>
    get<{
      languages: {
        code: string;
        name: string;
        flag: string;
        native_name: string;
        status: string;
        started: boolean;
        level: string;
        xp: number;
        known: { all: number; vocab: number; grammar: number; script: number };
        due_now: number;
        script_mastery: number;
      }[];
    }>("/progress/all"),
  recommendations: (lang: string) =>
    get<{ recommendations: Recommendation[] }>("/recommendations", { lang }),
  resolveMistake: (id: string, lang: string) =>
    post<{ ok: boolean }>(`/mistakes/${id}/resolve`, {}, { lang }),
  miniCourse: (confusionId: string, lang: string) =>
    get<{ id: string; title: string; steps: { heading: string; body: string }[] }>(
      `/mini-course/${confusionId}`,
      { lang },
    ),

  // -- speech --------------------------------------------------------------
  speechCapabilities: (lang: string) => get<SpeechCapabilities>("/speech/capabilities", { lang }),
  speechDifficulties: (lang: string) =>
    get<{ difficulties: Difficulty[] }>("/speech/difficulties", { lang }),

  // -- AI (always optional) ------------------------------------------------
  aiStatus: () => get<AiStatus>("/ai/status"),
  ask: (
    lang: string,
    body: {
      message: string;
      history?: { role: string; content: string }[];
      mode?: "auto" | "correct" | "explain";
    },
  ) =>
    post<{
      available: boolean;
      text: string;
      reason?: string;
      error?: string;
      /** The tutor's own guard: the model handed over the answer too fast. */
      gave_away_the_answer?: boolean;
      collapse_answer?: boolean;
    }>("/ai/ask", body, { lang }),
  aiScenarios: (lang: string) =>
    get<{ scenarios: { id: string; title: string; setting: string; level: string }[] }>(
      "/ai/scenarios",
      { lang },
    ),

  // -- data ----------------------------------------------------------------
  exportUrl: () => "/api/data/export/file",
  exportVocabUrl: (lang: string) => `/api/data/export/vocab.csv?lang=${lang}`,
  exportAnkiUrl: (lang: string) => `/api/data/export/anki.txt?lang=${lang}`,
  backups: () => get<{ backups: { name: string; size: number; created: string }[] }>(
    "/data/backup/list",
  ),
  importData: (payload: unknown) =>
    post<{ ok: boolean; imported: Record<string, number>; warnings: string[] }>(
      "/data/import",
      payload,
    ),
};

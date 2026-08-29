/**
 * Shapes returned by the local API.
 *
 * These are hand-written rather than generated, and deliberately loose in
 * places: several endpoints return payloads whose shape is defined by the
 * *language module*, not by the shared core — a Korean pronunciation
 * explanation is a chain of sound-change rules and a Mandarin one is a tone
 * trace. Pretending those are one type would mean inventing a union that
 * satisfies neither. Where the shape is genuinely language-defined, the type
 * says so.
 */

export type LangCode = string;

export type LanguageStatus = "complete" | "in_progress" | "foundation" | "planned";

export interface WritingSystem {
  id: string;
  name: string;
  native_name: string;
  has_stroke_order: boolean;
  is_closed_inventory: boolean;
  unit_count: number | null;
  teaching_order: number;
  description: string;
  units_loaded?: number;
  known?: number;
  mastery?: number;
}

export interface Language {
  code: LangCode;
  name: string;
  native_name: string;
  flag: string;
  iso3: string;
  writing_systems: WritingSystem[];
  capabilities: string[];
  status: LanguageStatus;
  status_note: string;
  uses_spaces: boolean;
  level_scheme?: string;
  is_usable?: boolean;
}

export interface Settings {
  explanation_language: "en" | "target" | "both";
  native_ui: boolean;
  romanization: "always" | "auto" | "never";
  romanization_level: number;
  show_translations: boolean;
  font_size: "small" | "medium" | "large" | "xlarge";
  theme: "light" | "dark" | "system";
  dyslexia_font: boolean;
  high_contrast: boolean;
  reduce_motion: boolean;
  daily_goal_minutes: number;
  new_cards_per_day: number;
  reviews_per_day: number;
  difficulty: "gentle" | "adaptive" | "hard";
  audio_autoplay: boolean;
  playback_rate: number;
  require_typing: boolean;
  tts_engine: "browser" | "piper" | "none";
  tts_voice: string;
  stt_engine: "browser" | "whisper" | "none";
  microphone_enabled: boolean;
  ai_provider: "ollama" | "lmstudio" | "llamacpp" | "openai_compatible" | "disabled";
  ai_model: string;
  ai_temperature: number;
  ai_context_length: number;
  ai_base_url: string;
  ai_socratic: boolean;
  allow_network: boolean;
}

export interface Streak {
  current: number;
  longest: number;
  last_active_date: string | null;
  freezes: number;
}

export interface Me {
  id: number;
  name: string;
  active_language: LangCode;
  onboarded: boolean;
  settings: Settings;
  streak: Streak;
  languages: { language: LangCode; level: string; xp: number }[];
}

export interface SkillScore {
  skill: string;
  name: string;
  native_name: string;
  score: number;
  attempts: number;
  confidence: number;
}

export interface SrsSummary {
  total: number;
  by_state: Record<string, number>;
  due_now: number;
  due_tomorrow: number;
  accuracy: number | null;
  known: number;
}

export interface LevelDetails {
  level: string;
  name: string;
  scheme: string;
  index: number;
  of: number;
  can_do?: string[];
  milestone?: string;
  vocabulary?: string;
  [k: string]: unknown;
}

export interface Dashboard {
  language: { code: LangCode; name: string; native_name: string; flag: string };
  greeting: { native: string; english: string };
  level: string;
  level_details: LevelDetails;
  estimated_level: string;
  xp: number;
  streak: Streak;
  today: {
    minutes_done: number;
    goal_minutes: number;
    percent: number;
    reviews_due: number;
    new_available: number;
  };
  srs: SrsSummary;
  known: { vocab: number; grammar: number; script: number; all: number };
  script_mastery: number;
  skills: Record<string, SkillScore>;
  next_lesson?: LessonSummary | null;
  weak_areas?: unknown[];
  strong_areas?: unknown[];
  confusions?: Confusion[];
  recommendations?: Recommendation[];
}

export interface Recommendation {
  kind: string;
  title: string;
  reason: string;
  priority: number;
  /** Where to send the learner. The shape depends on `kind`. */
  payload?: { lesson_id?: string; confusion_id?: string; [k: string]: unknown };
}

export interface Confusion {
  id: string;
  title: string;
  one_line: string;
  language: LangCode;
  count?: number;
  warrants_mini_course?: boolean;
}

export interface LessonSummary {
  id: string;
  language: LangCode;
  level: string;
  unit: string;
  ordinal: number;
  title: string;
  title_native: string;
  summary: string;
  objectives: string[];
  prerequisites: string[];
  est_minutes: number;
  tags: string[];
  status?: string;
  locked?: boolean;
  blocked_by?: string[];
  percent?: number;
}

/** A lesson step. `type` decides how it renders; the rest is step-specific. */
export interface LessonStep {
  step: string;
  type: string;
  heading?: string;
  body?: string | string[];
  note?: string;
  instruction?: string;
  points?: string[];
  items?: unknown[];
  questions?: { q: string; a: string }[];
  generator?: { type: string; [k: string]: unknown };
  [k: string]: unknown;
}

export interface Lesson extends LessonSummary {
  body: { steps?: LessonStep[]; introduces?: Record<string, string[]>; [k: string]: unknown };
  vocabulary: string[];
  grammar: string[];
}

export interface Exercise {
  kind: string;
  prompt: string;
  answer: unknown;
  options: string[];
  explain: string;
  audio: string;
  data: Record<string, unknown>;
  skill: string;
  difficulty: number;
  item_type: string;
  item_id: string;
  hints: boolean;
  exercise_id?: string;
  step?: string;
}

export interface VocabWord {
  id: string;
  language: LangCode;
  term: string;
  meaning: string;
  pos: string;
  topic: string;
  level: string;
  reading: string;
  transliteration: string;
  pronunciation: string;
  example_native: string;
  example_en: string;
  counter: string;
  notes: string;
  register: string;
  frequency_rank: number | null;
  drill_forms?: { form_id: string; form: string; label: string; category: string }[];
  pronunciation_explained?: Explanation;
}

export interface GrammarPoint {
  id: string;
  language: LangCode;
  name: string;
  name_native: string;
  level: string;
  category: string;
  ordinal: number;
  meaning: string;
  structure: string;
  formality: string;
  attaches_to: string;
  simple: string;
  technical: string;
  examples: { target?: string; english?: string; note?: string; pinyin?: string }[];
  mistakes: { wrong: string; right: string; why: string }[];
  contrast_points?: GrammarPoint[];
  similar_points?: GrammarPoint[];
}

/** The step shape is shared even though what a step *means* is not. */
export interface ExplanationStep {
  rule_id: string;
  rule_name: string;
  child_explanation: string;
  linguistic_explanation: string;
  before?: string;
  after?: string;
  [k: string]: unknown;
}

export interface Explanation {
  written?: string;
  spoken: string;
  changed?: boolean;
  summary?: string;
  steps: ExplanationStep[];
  [k: string]: unknown;
}

export interface ScriptUnit {
  id: string;
  language: LangCode;
  writing_system: string;
  unit: string;
  kind: string;
  name: string;
  transliteration: string;
  teaching_stage: number;
  data: Record<string, unknown>;
  known?: boolean;
}

export interface AiProviderStatus {
  id: string;
  name: string;
  available: boolean;
  models: string[];
  base_url: string;
  error: string;
  hint: string;
  local?: boolean;
}

export interface AiStatus {
  selected_provider: string;
  selected_model: string;
  enabled: boolean;
  available: boolean;
  providers: AiProviderStatus[];
  note?: string;
}

export interface SpeechCapabilities {
  language: LangCode;
  tts: {
    engine: string;
    browser_available: boolean;
    note: string;
    local_engines: { id: string; name: string; installed: boolean; note: string }[];
  };
  stt: {
    engine: string;
    browser_available: boolean;
    browser_caveat?: string;
    note?: string;
    scoring_available?: boolean;
    local_engines?: { id: string; name: string; installed: boolean; note: string }[];
  };
  audio_files?: { count: number; note: string };
}

export interface OnboardingQuestion {
  id: string;
  question: string;
  type: string;
  options: {
    value: string | number;
    label: string;
    native?: string;
    note?: string;
    enabled?: boolean;
  }[];
}

export interface HealthReport {
  ok: boolean;
  offline: boolean;
  version?: string;
  languages: Record<string, Record<string, number>>;
  content_errors: string[];
  content_warnings?: string[];
}

export interface NetworkFeature {
  id: string;
  name: string;
  what_it_sends: string;
  where: string;
  enabled_by_default: boolean;
}

export interface RuntimeInfo {
  version: string;
  offline_capable: boolean;
  ai_available: boolean;
  ai_provider: string;
  db_path: string;
  content_dir: string;
  network_features: NetworkFeature[];
}

// ==========================================================================
// Review, practice and search
// ==========================================================================

export type Grade = "again" | "hard" | "good" | "easy";

export interface Card {
  id: number;
  item_type: string;
  item_id: string;
  state: "new" | "learning" | "review" | "difficult" | "mastered";
  ease: number;
  interval_days: number;
  repetitions: number;
  lapses: number;
  streak: number;
  due_at: string | null;
  total_reviews: number;
  total_correct: number;
  accuracy: number | null;
}

/**
 * A queue entry.
 *
 * `content` is the item the card points at — a vocabulary row, a script unit,
 * a grammar point. Its shape depends on `card.item_type`, and it can be null
 * when a card outlives the content it referenced (a word removed from the
 * curriculum, say), which the UI has to survive rather than crash on.
 */
export interface ReviewItem {
  card: Card;
  preview: Record<Grade, string>;
  content: Record<string, unknown> | null;
}

export interface GradeOutcome {
  card: Card;
  interval_days: number;
  due_at: string;
  state: string;
  explanation?: string;
  [k: string]: unknown;
}

export interface Mistake {
  id: number;
  language: LangCode;
  at: string;
  category: string;
  expected: string;
  given: string;
  item_type: string;
  item_id: string;
  times_seen: number;
  resolved: number;
  explanation: string;
  confusion_id: string;
  lesson_id: string;
  /** Present when the mistake matched a known confusion pair. */
  confusion?: { title: string; one_line: string };
}

export interface Difficulty {
  id: string;
  title: string;
  contrast: string[];
  why_hard: string;
  fix: string;
  severity: string;
  minimal_pairs?: string[][];
  causes_misunderstanding?: boolean;
  simple?: string;
}

export interface SearchHit {
  ref: string;
  kind: string;
  language: LangCode;
  term: string;
  english: string;
  extra?: string;
}

export interface SearchResults {
  language: LangCode;
  query: string;
  total: number;
  results: Record<string, SearchHit[]>;
  pronunciation?: Explanation;
  conjugation?: Record<string, unknown>;
}

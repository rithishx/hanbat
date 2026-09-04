/**
 * Routing, and the two gates in front of it.
 *
 * A learner who has not been through onboarding is sent there, because every
 * other screen needs to know which language they are learning and roughly
 * where they are. And if the backend is unreachable the app says so plainly
 * rather than rendering empty shells — "no lessons found" and "the server is
 * not running" look identical to a user and are completely different problems.
 */

import { Navigate, Route, Routes } from "react-router-dom";
import { Shell } from "./components/Shell";
import { Loading } from "./components/ui";
import { useApp } from "./lib/app-context";

import Dashboard from "./pages/Dashboard";
import Session from "./pages/Session";
import Onboarding from "./pages/Onboarding";
import Placement from "./pages/Placement";
import Lessons from "./pages/Lessons";
import LessonPlayer from "./pages/LessonPlayer";
import Review from "./pages/Review";
import Practice from "./pages/Practice";
import Writing from "./pages/Writing";
import Vocabulary from "./pages/Vocabulary";
import Grammar from "./pages/Grammar";
import Pronunciation from "./pages/Pronunciation";
import Conjugation from "./pages/Conjugation";
import Mistakes from "./pages/Mistakes";
import Remediation from "./pages/Remediation";
import Tutor from "./pages/Tutor";
import Search from "./pages/Search";
import Progress from "./pages/Progress";
import Languages from "./pages/Languages";
import Settings from "./pages/Settings";

export default function App() {
  const { loading, error, me, refresh } = useApp();

  if (loading) {
    return (
      <div className="grid min-h-dvh place-items-center">
        <Loading what="Hanbat" />
      </div>
    );
  }

  if (error || !me) {
    return (
      <div className="grid min-h-dvh place-items-center p-6">
        <div className="card max-w-lg p-8">
          <h1 className="mb-2 text-xl font-bold">The local server is not answering</h1>
          <p className="mb-4 text-sm leading-relaxed text-muted">
            {error ?? "No learner record came back."} Hanbat runs entirely on this
            machine, so nothing is wrong with your connection — the backend just
            is not running.
          </p>
          <pre className="mb-4 overflow-x-auto rounded-xl bg-paper p-3 text-xs">
{`cd backend
python3 -m uvicorn app.main:app --port 8756`}
          </pre>
          <button className="btn-primary" onClick={() => void refresh()}>
            Try again
          </button>
        </div>
      </div>
    );
  }

  if (!me.onboarded) {
    return (
      <Routes>
        <Route path="/welcome" element={<Onboarding />} />
        <Route path="/placement" element={<Placement />} />
        <Route path="*" element={<Navigate to="/welcome" replace />} />
      </Routes>
    );
  }

  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/session" element={<Session />} />
        <Route path="/learn" element={<Lessons />} />
        <Route path="/learn/:lessonId" element={<LessonPlayer />} />
        <Route path="/review" element={<Review />} />
        <Route path="/practice" element={<Practice />} />
        <Route path="/writing" element={<Writing />} />
        <Route path="/vocabulary" element={<Vocabulary />} />
        <Route path="/grammar" element={<Grammar />} />
        <Route path="/grammar/:pointId" element={<Grammar />} />
        <Route path="/pronunciation" element={<Pronunciation />} />
        <Route path="/conjugation" element={<Conjugation />} />
        <Route path="/mistakes" element={<Mistakes />} />
        <Route path="/fix/:pointId" element={<Remediation />} />
        <Route path="/tutor" element={<Tutor />} />
        <Route path="/search" element={<Search />} />
        <Route path="/progress" element={<Progress />} />
        <Route path="/languages" element={<Languages />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/placement" element={<Placement />} />
        <Route path="/welcome" element={<Navigate to="/" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Shell>
  );
}

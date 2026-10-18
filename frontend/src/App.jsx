import { Routes, Route, Link } from 'react-router-dom'
import { GraduationCap } from 'lucide-react'

import AppLayout from './components/AppLayout.jsx'
import { useLanguage } from './lib/i18n.jsx'
import { buttonClasses } from './components/ui.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Library from './pages/Library.jsx'
import Tutor from './pages/Tutor.jsx'
import Quiz from './pages/Quiz.jsx'
import Revision from './pages/Revision.jsx'
import Lessons from './pages/Lessons.jsx'
import Flashcards from './pages/Flashcards.jsx'

function NotFound() {
  const { t } = useLanguage()
  return (
    <main className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
      <GraduationCap className="h-10 w-10 text-slate-300" aria-hidden="true" />
      <h1 className="text-xl font-bold text-slate-700">{t.common.notFound}</h1>
      <Link to="/" className={buttonClasses({ variant: 'secondary' })}>
        {t.common.backHome}
      </Link>
    </main>
  )
}

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Dashboard />} />
        <Route path="library" element={<Library />} />
        <Route path="lessons" element={<Lessons />} />
        <Route path="tutor" element={<Tutor />} />
        <Route path="quiz" element={<Quiz />} />
        <Route path="flashcards" element={<Flashcards />} />
        <Route path="revision" element={<Revision />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}

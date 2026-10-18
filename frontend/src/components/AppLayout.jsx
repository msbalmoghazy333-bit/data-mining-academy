/**
 * Application shell: sticky header (brand, progress pill, language toggle),
 * a collapsible desktop sidebar, and a mobile drawer + bottom navigation.
 *
 * Sidebar collapse is remembered in localStorage. Mobile keeps the five most
 * used destinations in the bottom bar; "More" opens the full drawer.
 */

import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  BookOpen,
  ChevronsLeft,
  ChevronsRight,
  GraduationCap,
  Languages,
  LayoutDashboard,
  Layers,
  Library,
  ListChecks,
  Menu,
  MoreHorizontal,
  RefreshCcw,
  Sparkles,
  TrendingUp,
  X,
} from 'lucide-react'

import { useLanguage } from '../lib/i18n.jsx'
import { pct } from '../lib/format.js'
import { useSummary } from '../lib/summaryStore.js'
import { ProgressBar } from './ui.jsx'

const NAV = [
  { key: 'dashboard', to: '/', icon: LayoutDashboard, end: true },
  { key: 'library', to: '/library', icon: Library },
  { key: 'lessons', to: '/lessons', icon: BookOpen },
  { key: 'tutor', to: '/tutor', icon: Sparkles },
  { key: 'quiz', to: '/quiz', icon: ListChecks },
  { key: 'flashcards', to: '/flashcards', icon: Layers },
  { key: 'revision', to: '/revision', icon: RefreshCcw },
]

const BOTTOM_KEYS = ['dashboard', 'library', 'tutor', 'quiz', 'flashcards']

const SIDEBAR_KEY = 'dma-sidebar-collapsed'

function navItemClass({ isActive }) {
  return [
    'flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors',
    'focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal-600',
    isActive
      ? 'bg-teal-50 font-semibold text-teal-700'
      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
  ].join(' ')
}

/** Brand block shared by header / sidebar / drawer. */
function Brand() {
  const { t } = useLanguage()
  return (
    <div className="flex items-center gap-2.5">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-teal-600 text-white shadow-sm">
        <GraduationCap className="h-5 w-5" aria-hidden="true" />
      </span>
      <span className="min-w-0">
        <span className="block truncate text-sm font-extrabold text-slate-900">
          {t.app.title}
        </span>
        <span className="block truncate text-[11px] text-slate-500">{t.app.tagline}</span>
      </span>
    </div>
  )
}

/** Course mastery pill — driven by the shared dashboard summary. */
function ProgressPill({ inline = false }) {
  const { t } = useLanguage()
  const summary = useSummary()
  const data = summary.data

  const total = data?.topics?.total ?? 0
  const mastered = data?.topics?.mastery?.mastered ?? 0
  const value = pct(mastered, total)
  const title = value === null ? t.header.progressEmpty : `${t.header.progress}: ${value}%`

  return (
    <div
      title={title}
      className={`w-full items-center gap-2.5 rounded-full border border-slate-200 bg-white px-3.5 py-1.5 shadow-sm ${
        inline ? 'flex' : 'hidden sm:flex'
      }`}
    >
      <TrendingUp className="h-4 w-4 shrink-0 text-teal-600" aria-hidden="true" />
      <span className="text-xs font-medium text-slate-500">{t.header.progress}</span>
      <span className="text-sm font-bold tabular-nums text-slate-900">
        {value === null ? '—' : `${value}%`}
      </span>
      <ProgressBar value={value} className="w-14" />
    </div>
  )
}

/** Language switch button — shows the *other* language. */
function LanguageToggle() {
  const { t, toggle } = useLanguage()
  return (
    <button
      type="button"
      onClick={toggle}
      title={t.lang.hint}
      className="flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 shadow-sm transition-colors hover:bg-slate-50 hover:text-teal-700"
    >
      <Languages className="h-4 w-4 text-teal-600" aria-hidden="true" />
      {t.lang.toggle}
    </button>
  )
}

/** One sidebar/drawer link. */
function NavItem({ item, collapsed = false, onNavigate }) {
  const { t } = useLanguage()
  const Icon = item.icon
  return (
    <NavLink
      to={item.to}
      end={item.end ?? false}
      className={({ isActive }) => navItemClass({ isActive })}
      onClick={onNavigate}
      title={collapsed ? t.nav[item.key] : undefined}
    >
      <Icon className="h-5 w-5 shrink-0" aria-hidden="true" />
      {!collapsed && <span className="truncate">{t.nav[item.key]}</span>}
    </NavLink>
  )
}

function SidebarInner({ collapsed, onCollapse, onNavigate }) {
  const { t, dir } = useLanguage()
  const CollapseIcon = dir === 'rtl' ? (collapsed ? ChevronsLeft : ChevronsRight) : collapsed ? ChevronsRight : ChevronsLeft

  return (
    <>
      <nav className="flex flex-1 flex-col gap-1 overflow-y-auto px-3 py-3">
        {NAV.map((item) => (
          <NavItem
            key={item.key}
            item={item}
            collapsed={collapsed}
            onNavigate={onNavigate}
          />
        ))}
      </nav>
      <div className="border-t border-slate-100 px-3 py-3">
        <button
          type="button"
          onClick={onCollapse}
          title={collapsed ? t.nav.expand : t.nav.collapse}
          className="hidden w-full items-center justify-center gap-2 rounded-xl px-3 py-2 text-sm font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900 lg:flex"
        >
          <CollapseIcon className="h-4 w-4 shrink-0" aria-hidden="true" />
          {!collapsed && <span>{t.nav.collapse}</span>}
        </button>
      </div>
    </>
  )
}

export default function AppLayout() {
  const { t, isRTL } = useLanguage()
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return window.localStorage.getItem(SIDEBAR_KEY) === '1'
    } catch {
      return false
    }
  })
  const [drawerOpen, setDrawerOpen] = useState(false)

  // Close the drawer whenever the route changes (e.g. browser back/forward;
  // regular navigation closes it via each link's onClick).
  useEffect(() => {
    setDrawerOpen(false)
  }, [location.pathname])

  const toggleCollapse = () => {
    setCollapsed((previous) => {
      try {
        window.localStorage.setItem(SIDEBAR_KEY, previous ? '0' : '1')
      } catch {
        /* ignore */
      }
      return !previous
    })
  }

  const closeDrawer = () => setDrawerOpen(false)
  const openDrawer = () => setDrawerOpen(true)

  const bottomItems = NAV.filter((item) => BOTTOM_KEYS.includes(item.key))

  return (
    <div className="min-h-screen">
      {/* ------------------------------ header ------------------------------ */}
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="flex h-16 items-center gap-3 px-4 sm:px-6">
          <button
            type="button"
            onClick={openDrawer}
            aria-label={t.nav.menu}
            className="rounded-xl p-2 text-slate-600 hover:bg-slate-100 lg:hidden"
          >
            <Menu className="h-5 w-5" aria-hidden="true" />
          </button>

          <div className="lg:hidden">
            <Brand />
          </div>
          <div className="hidden lg:flex">
            <Brand />
          </div>

          <div className="ms-auto flex items-center gap-2 sm:gap-3">
            <ProgressPill />
            <LanguageToggle />
          </div>
        </div>
      </header>

      <div className="flex">
        {/* --------------------------- desktop sidebar --------------------------- */}
        <aside
          className={`sticky top-16 hidden h-[calc(100vh-4rem)] shrink-0 flex-col border-slate-200 bg-white transition-[width] duration-200 lg:flex ${
            isRTL ? 'border-l' : 'border-r'
          } ${collapsed ? 'w-[4.75rem]' : 'w-72'}`}
        >
          <SidebarInner
            collapsed={collapsed}
            onCollapse={toggleCollapse}
            onNavigate={closeDrawer}
          />
        </aside>

        {/* ------------------------------ mobile drawer ------------------------------ */}
        {drawerOpen && (
          <div className="fixed inset-0 z-40 lg:hidden">
            <div
              className="absolute inset-0 bg-slate-900/50"
              onClick={closeDrawer}
              aria-hidden="true"
            />
            <div
              role="dialog"
              aria-modal="true"
              className={`absolute bottom-0 top-16 flex w-72 max-w-[85vw] flex-col border-slate-200 bg-white shadow-2xl ${
                isRTL ? 'start-0 border-l' : 'start-0 border-r'
              }`}
            >
              <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
                <span className="text-sm font-bold text-slate-500">{t.nav.more}</span>
                <button
                  type="button"
                  onClick={closeDrawer}
                  aria-label={t.nav.closeMenu}
                  className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                >
                  <X className="h-5 w-5" aria-hidden="true" />
                </button>
              </div>
              <div className="border-b border-slate-100 px-4 pt-3">
                <ProgressPill inline />
              </div>
              <SidebarInner collapsed={false} onCollapse={closeDrawer} onNavigate={closeDrawer} />
            </div>
          </div>
        )}

        {/* -------------------------------- content -------------------------------- */}
        <main className="min-w-0 flex-1 px-4 pb-24 pt-6 sm:px-6 lg:pb-10">
          <Outlet />
        </main>
      </div>

      {/* ---------------------------- mobile bottom nav ---------------------------- */}
      <nav
        aria-label="primary"
        className="fixed bottom-0 inset-x-0 z-30 border-t border-slate-200 bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden"
      >
        <div className="grid grid-cols-6">
          {bottomItems.map((item) => {
            const Icon = item.icon
            return (
              <NavLink
                key={item.key}
                to={item.to}
                end={item.end ?? false}
                className={({ isActive }) =>
                  [
                    'flex flex-col items-center gap-0.5 py-2.5 text-[10px] font-medium transition-colors',
                    isActive ? 'text-teal-700' : 'text-slate-500 hover:text-slate-800',
                  ].join(' ')
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      className={`h-5 w-5 ${isActive ? 'text-teal-600' : ''}`}
                      aria-hidden="true"
                    />
                    <span className="max-w-full truncate px-1">{t.nav[item.key]}</span>
                  </>
                )}
              </NavLink>
            )
          })}
          <button
            type="button"
            onClick={openDrawer}
            className="flex flex-col items-center gap-0.5 py-2.5 text-[10px] font-medium text-slate-500 hover:text-slate-800"
          >
            <MoreHorizontal className="h-5 w-5" aria-hidden="true" />
            <span className="px-1">{t.nav.more}</span>
          </button>
        </div>
      </nav>
    </div>
  )
}

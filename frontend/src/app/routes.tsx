import { createBrowserRouter } from 'react-router-dom'
import { AppShell } from './AppShell'
import { HomePage } from '@/features/home/HomePage'
import { RecordPage } from '@/features/record/RecordPage'
import { ProjectsPage } from '@/features/projects/ProjectsPage'
import { ProjectDetailPage } from '@/features/projects/ProjectDetailPage'
import { FootagePage } from '@/features/footage/FootagePage'
import { MotionLibraryPage } from '@/features/library/MotionLibraryPage'
import { SettingsPage } from '@/features/settings/SettingsPage'
import { NotFoundPage } from '@/features/home/NotFoundPage'
import { ForgotPasswordPage, LoginPage, RegisterPage, ResetPasswordPage } from '@/features/auth/AuthPages'
import { LandingPage } from '@/features/landing/LandingPage'
import { RequireAuth } from '@/app/RequireAuth'

export const router = createBrowserRouter([
  // Public
  { path: '/', element: <LandingPage /> },
  { path: '/login', element: <LoginPage /> },
  { path: '/register', element: <RegisterPage /> },
  { path: '/forgot-password', element: <ForgotPasswordPage /> },
  { path: '/reset-password/:uid/:token', element: <ResetPasswordPage /> },
  {
    // Everything below needs a logged-in user
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    children: [
      { path: 'dashboard', element: <HomePage /> },
      { path: 'record', element: <RecordPage /> },
      { path: 'footage', element: <FootagePage /> },
      { path: 'projects', element: <ProjectsPage /> },
      { path: 'projects/:projectId', element: <ProjectDetailPage /> },
      { path: 'recordings', element: <MotionLibraryPage /> },
      { path: 'settings', element: <SettingsPage /> },
      { path: 'settings/:section', element: <SettingsPage /> },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
])

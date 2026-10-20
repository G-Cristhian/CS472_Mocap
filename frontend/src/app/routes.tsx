import { createBrowserRouter, Navigate } from 'react-router-dom'
import { AppShell } from './AppShell'
import { RequireAuth } from '@/app/RequireAuth'
import { LandingPage } from '@/features/landing/LandingPage'
import { ForgotPasswordPage, LoginPage, RegisterPage, ResetPasswordPage } from '@/features/auth/AuthPages'
import { HomePage } from '@/features/home/HomePage'
import { ProjectsPage } from '@/features/projects/ProjectsPage'
import { ProjectDetailPage } from '@/features/projects/ProjectDetailPage'
import { MotionPage } from '@/features/motions/MotionPage'
import { MotionsPage } from '@/features/motions/MotionsPage'
import { RecordingsPage } from '@/features/library/RecordingsPage'
import { RecordingPage } from '@/features/recordings/RecordingPage'
import { StreamingPage } from '@/features/streaming/StreamingPage'
import { SettingsPage } from '@/features/settings/SettingsPage'
import { NotFoundPage } from '@/features/home/NotFoundPage'

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
      { path: 'projects', element: <ProjectsPage /> },
      { path: 'projects/:projectId', element: <ProjectDetailPage /> },
      { path: 'motions', element: <MotionsPage /> },
      { path: 'motions/:motionId', element: <MotionPage /> },
      { path: 'recordings', element: <RecordingsPage /> },
      // "new" records from one camera; any other id previews that recording
      { path: 'recordings/:recordingId', element: <RecordingPage /> },
      { path: 'streaming', element: <StreamingPage /> },
      { path: 'record', element: <Navigate to="/recordings/new" replace /> },
      { path: 'settings', element: <SettingsPage /> },
      { path: 'settings/:section', element: <SettingsPage /> },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
])

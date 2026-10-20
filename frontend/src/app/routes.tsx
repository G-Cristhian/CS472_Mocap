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

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'record', element: <RecordPage /> },
      { path: 'footage', element: <FootagePage /> },
      { path: 'projects', element: <ProjectsPage /> },
      { path: 'projects/:projectId', element: <ProjectDetailPage /> },
      { path: 'library', element: <MotionLibraryPage /> },
      { path: 'settings', element: <SettingsPage /> },
      { path: 'settings/:section', element: <SettingsPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])

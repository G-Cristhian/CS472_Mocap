import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'
import { SettingsProvider } from '@/app/SettingsProvider'
import { StudioProvider } from '@/app/StudioProvider'
import { router } from '@/app/routes'
import '@/styles/global.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <SettingsProvider>
      <StudioProvider>
        <RouterProvider router={router} />
      </StudioProvider>
    </SettingsProvider>
  </StrictMode>,
)

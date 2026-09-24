import { useEffect, type ReactNode } from 'react'
import { CloseIcon } from './Icons'
import './Modal.css'

export function Modal({
  title,
  subtitle,
  onClose,
  children,
}: {
  title: string
  subtitle?: string
  onClose: () => void
  children: ReactNode
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="modal__backdrop" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <h2>{title}</h2>
        {subtitle && <p className="modal__sub">{subtitle}</p>}
        {children}
      </div>
    </div>
  )
}

export function Toast({
  message,
  actionLabel,
  onAction,
  onClose,
}: {
  message: ReactNode
  actionLabel?: string
  onAction?: () => void
  onClose: () => void
}) {
  return (
    <div className="toast" role="status">
      <span className="dot dot--live" />
      <span>{message}</span>
      {actionLabel && (
        <button className="btn btn--sm" onClick={onAction}>
          {actionLabel}
        </button>
      )}
      <button className="iconbtn" aria-label="Dismiss" onClick={onClose}>
        <CloseIcon size={16} />
      </button>
    </div>
  )
}

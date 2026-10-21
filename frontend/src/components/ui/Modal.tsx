import { useEffect, type ReactNode } from 'react'
import './Modal.css'

export function Modal({
  title,
  subtitle,
  onClose,
  wide = false,
  children,
}: {
  title: string
  subtitle?: string
  onClose: () => void
  /** A wider box, for content like a grid of previews */
  wide?: boolean
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
        className={wide ? 'modal modal--wide' : 'modal'}
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

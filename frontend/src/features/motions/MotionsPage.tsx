import { useState } from 'react'
import { useStudio } from '@/app/StudioProvider'
import { MotionCard } from '@/components/ui/MotionCard'
import { NewMotionDialog } from '@/components/ui/NewMotionDialog'
import { PlusIcon } from '@/components/ui/Icons'

/** Every motion across all projects. A motion is one skeleton built from 2 to 4 recordings. */
export function MotionsPage() {
  const { motions } = useStudio()
  const [dialog, setDialog] = useState(false)

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="page-title">Motions</h1>
          <p className="page-sub">Every skeleton you have built, across all projects.</p>
        </div>
        <button className="btn btn-project" onClick={() => setDialog(true)}>
          <PlusIcon />
          New motion
        </button>
      </div>

      {motions.length === 0 ? (
        <div className="empty">No motions yet.</div>
      ) : (
        <div className="grid-cards">
          {motions.map((motion) => (
            <MotionCard key={motion.id} motion={motion} />
          ))}
        </div>
      )}

      {dialog && <NewMotionDialog onClose={() => setDialog(false)} />}
    </div>
  )
}

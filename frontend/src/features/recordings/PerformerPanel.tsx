import { useEffect, useState, type FormEvent } from 'react'
import { createPerformer, listPerformers, updatePerformer, type Performer } from '@/lib/performers'
import { setRecordingPerformer } from '@/lib/recordings'

const NONE = ''
const NEW = 'new'

/** The editable details of a performer. Height is text while typing; empty means no height. */
interface Draft {
  full_name: string
  height: string
  email: string
  phone: string
}

interface Props {
  recordingId: string
  performerId: number | null
  /** The logged-in user's name, used as the default performer when none is chosen yet */
  accountName: string
  onSaved: (performerId: number | null) => void
}

/** Who is in this recording: pick someone from your list, or add a new performer, then save. */
export function PerformerPanel({ recordingId, performerId, accountName, onSaved }: Props) {
  const [performers, setPerformers] = useState<Performer[] | null>(null)
  const [choice, setChoice] = useState<string>(performerId != null ? String(performerId) : NEW)
  const [name, setName] = useState(accountName)
  const [height, setHeight] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<Draft>({ full_name: '', height: '', email: '', phone: '' })
  const [detailsSaving, setDetailsSaving] = useState(false)

  const selected = performers?.find((p) => String(p.id) === choice) ?? null

  useEffect(() => {
    listPerformers()
      .then((list) => {
        setPerformers(list)
        // Nothing chosen yet: default to the account holder if they are already in the list
        if (!performerId) {
          const sameName = list.find((p) => p.full_name === accountName)
          if (sameName) setChoice(String(sameName.id))
        }
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Could not load performers.'))
  }, [performerId, accountName])

  async function onSave(e: FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      let target: number | null = null
      if (choice === NEW) {
        const created = await createPerformer({
          full_name: name.trim(),
          height_m: height ? Number(height) : null,
          email: email.trim(),
          phone: phone.trim(),
        })
        target = created.id
      } else if (choice !== NONE) {
        target = Number(choice)
      }

      await setRecordingPerformer(recordingId, target)
      setPerformers(await listPerformers())
      setChoice(target == null ? NONE : String(target))
      onSaved(target)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the performer.')
    } finally {
      setSaving(false)
    }
  }

  function startEditing(p: Performer) {
    setDraft({
      full_name: p.full_name,
      height: p.height_m != null ? String(p.height_m) : '',
      email: p.email,
      phone: p.phone,
    })
    setEditing(true)
  }

  // Saves the chosen performer's details. Separate from Save performer, which only assigns them to this recording.
  async function onSaveDetails() {
    if (!selected) return
    setDetailsSaving(true)
    setError(null)
    try {
      await updatePerformer(selected.id, {
        full_name: draft.full_name.trim(),
        height_m: draft.height ? Number(draft.height) : null,
        email: draft.email.trim(),
        phone: draft.phone.trim(),
      })
      setPerformers(await listPerformers())
      setEditing(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the performer details.')
    } finally {
      setDetailsSaving(false)
    }
  }

  const canSave = !saving && performers !== null && (choice !== NEW || name.trim() !== '')
  const canSaveDetails = !detailsSaving && draft.full_name.trim() !== ''

  return (
    <form className="performer-panel" onSubmit={onSave}>
      <label className="field">
        <span className="field__label">Performer</span>
        <select
          className="select"
          value={choice}
          disabled={performers === null}
          onChange={(e) => {
            setChoice(e.target.value)
            setEditing(false)
          }}
        >
          <option value={NONE}>No performer</option>
          {performers?.map((p) => (
            <option key={p.id} value={String(p.id)}>
              {p.full_name}
            </option>
          ))}
          <option value={NEW}>Add new performer…</option>
        </select>
      </label>

      {selected && !editing && (
        <button type="button" className="btn btn--ghost btn--sm" onClick={() => startEditing(selected)}>
          Edit details
        </button>
      )}

      {selected && editing && (
        <div className="performer-panel__details">
          <label className="field">
            <span className="field__label">Full name</span>
            <input
              className="input"
              value={draft.full_name}
              onChange={(e) => setDraft({ ...draft, full_name: e.target.value })}
            />
          </label>
          <label className="field">
            <span className="field__label">Height (m)</span>
            <input
              className="input"
              type="number"
              min="1"
              max="2.5"
              step="0.01"
              placeholder="e.g. 1.75"
              value={draft.height}
              onChange={(e) => setDraft({ ...draft, height: e.target.value })}
            />
          </label>
          <label className="field">
            <span className="field__label">Email</span>
            <input
              className="input"
              type="email"
              value={draft.email}
              onChange={(e) => setDraft({ ...draft, email: e.target.value })}
            />
          </label>
          <label className="field">
            <span className="field__label">Phone</span>
            <input
              className="input"
              type="tel"
              value={draft.phone}
              onChange={(e) => setDraft({ ...draft, phone: e.target.value })}
            />
          </label>
          <div className="performer-panel__actions">
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              disabled={!canSaveDetails}
              onClick={onSaveDetails}
            >
              {detailsSaving ? 'Saving…' : 'Save details'}
            </button>
            <button type="button" className="btn btn--ghost btn--sm" onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {choice === NEW && (
        <>
          <label className="field">
            <span className="field__label">Full name</span>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="field">
            <span className="field__label">Height (m)</span>
            <input
              className="input"
              type="number"
              min="1"
              max="2.5"
              step="0.01"
              placeholder="e.g. 1.75"
              value={height}
              onChange={(e) => setHeight(e.target.value)}
            />
          </label>
          <label className="field">
            <span className="field__label">Email</span>
            <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label className="field">
            <span className="field__label">Phone</span>
            <input className="input" type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} />
          </label>
        </>
      )}

      {error && (
        <p role="alert" style={{ color: 'var(--pink)', fontSize: 14 }}>
          {error}
        </p>
      )}

      <button type="submit" className="btn btn--ghost btn--sm" disabled={!canSave}>
        {saving ? 'Saving…' : 'Save performer'}
      </button>
    </form>
  )
}

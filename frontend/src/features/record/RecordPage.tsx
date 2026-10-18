import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '@/app/AuthProvider'
import { displayName } from '@/lib/auth'
import { StickFigure } from '@/components/ui/StickFigure'
import { Toast } from '@/components/ui/Modal'
import { AlertIcon, CloseIcon, InfoIcon, LayoutIcon } from '@/components/ui/Icons'
import { cameras as seedCameras } from '@/lib/data'
import type { Camera } from '@/types'
import './record.css'

type Layout = 'quad' | 'split' | 'single'

function formatElapsed(seconds: number) {
  const m = Math.floor(seconds / 60)
    .toString()
    .padStart(2, '0')
  const s = (seconds % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}

export function RecordPage() {
  const { user: account } = useAuth()
  const [tab, setTab] = useState<'capture' | 'cameras'>('capture')
  const [cams, setCams] = useState<Camera[]>(seedCameras)
  const [layout, setLayout] = useState<Layout>('quad')
  const [alertOpen, setAlertOpen] = useState(true)
  const [toast, setToast] = useState<'calibration' | 'saved' | null>('calibration')

  const [performer, setPerformer] = useState('self')
  const [model, setModel] = useState('balanced')
  const [smoothing, setSmoothing] = useState(1)
  const [hands, setHands] = useState(false)
  const [face, setFace] = useState(false)
  const [lockFeet, setLockFeet] = useState(false)

  const [recording, setRecording] = useState(false)
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    if (!recording) return
    const id = window.setInterval(() => setElapsed((e) => e + 1), 1000)
    return () => window.clearInterval(id)
  }, [recording])

  const online = cams.filter((c) => c.status === 'streaming').length
  const visible = layout === 'single' ? cams.slice(0, 1) : layout === 'split' ? cams.slice(0, 2) : cams

  function reconnect(id: number) {
    setCams((list) => list.map((c) => (c.id === id ? { ...c, status: 'streaming' } : c)))
    setAlertOpen(false)
  }

  return (
    <div className="record">
      <aside className="record__side">
        <div className="record__tabs" role="tablist" aria-label="Recording setup">
          <button role="tab" aria-selected={tab === 'capture'} onClick={() => setTab('capture')}>
            Capture
          </button>
          <button role="tab" aria-selected={tab === 'cameras'} onClick={() => setTab('cameras')}>
            Cameras
          </button>
        </div>

        {tab === 'capture' ? (
          <>
            <div className="record__form">
              <label className="field">
                <span className="field__label">Performer</span>
                <span className="field__hint">Who is wearing the calibration suit.</span>
                <select
                  className="select"
                  value={performer}
                  onChange={(e) => setPerformer(e.target.value)}
                >
                  <option value="self">{account ? displayName(account) : 'You'} — Suit A</option>
                  <option value="ada">Ada R. — Suit B</option>
                  <option value="guest">Guest performer — no suit</option>
                </select>
              </label>

              <label className="field">
                <span className="field__label">Motion model</span>
                <span className="field__hint">How much work the AI does between suit markers.</span>
                <select className="select" value={model} onChange={(e) => setModel(e.target.value)}>
                  <option value="balanced">Balanced — suit leads, AI fills gaps</option>
                  <option value="suit">Suit only — no AI inference</option>
                  <option value="ai">AI led — suit corrects drift</option>
                </select>
              </label>

              <div className="field">
                <span className="field__label">Smoothing</span>
                <span className="field__hint">Higher values remove jitter but soften fast moves.</span>
                <div className="slider" style={{ marginTop: 12 }}>
                  <input
                    type="range"
                    min={0}
                    max={3}
                    step={0.1}
                    value={smoothing}
                    aria-label="Smoothing"
                    onChange={(e) => setSmoothing(Number(e.target.value))}
                  />
                  <span className="slider__value">{smoothing.toFixed(1)}x</span>
                </div>
              </div>

              <div className="field">
                <span className="field__label">Capture these too</span>
                <div className="record__checks">
                  <label className="check">
                    <input type="checkbox" checked={hands} onChange={(e) => setHands(e.target.checked)} />
                    Hands and fingers
                  </label>
                  <label className="check">
                    <input type="checkbox" checked={face} onChange={(e) => setFace(e.target.checked)} />
                    Face
                  </label>
                  <label className="check">
                    <input
                      type="checkbox"
                      checked={lockFeet}
                      onChange={(e) => setLockFeet(e.target.checked)}
                    />
                    Lock feet to the floor
                  </label>
                </div>
              </div>
            </div>

            <div className="record__foot">
              <div className="note">
                <InfoIcon />
                <span>
                  After the clap, <b>stand still and upright, facing the cameras, for a couple of
                  seconds</b>. This measures your height; without it the take can't be processed.
                </span>
              </div>
              <div className="note">
                <InfoIcon />
                <span>
                  These apply to new recordings only. <b>You can change this later</b> — nothing here
                  is locked in once you hit record.
                </span>
              </div>
              <button
                className={`btn btn--block ${recording ? 'btn--ghost' : 'btn--pink'}`}
                onClick={() => {
                  if (recording) {
                    setRecording(false)
                    setElapsed(0)
                    setToast('saved')
                  } else {
                    setRecording(true)
                    setToast(null)
                  }
                }}
              >
                <span className="dot dot--rec" />
                {recording ? `Stop recording · ${formatElapsed(elapsed)}` : 'Start recording'}
              </button>
            </div>
          </>
        ) : (
          <div className="camlist">
            {cams.map((cam) => (
              <div className="camlist__item" key={cam.id}>
                <span className={`dot ${cam.status === 'streaming' ? 'dot--live' : 'dot--off'}`} />
                <div className="stack">
                  <strong>{cam.label}</strong>
                  <span className="camlist__meta">
                    {cam.resolution} · {cam.fps} fps
                  </span>
                </div>
                <span className="spacer" />
                {cam.status === 'streaming' ? (
                  <span className="badge badge--suit">Streaming</span>
                ) : (
                  <button className="btn btn--sm btn--ghost" onClick={() => reconnect(cam.id)}>
                    Reconnect
                  </button>
                )}
              </div>
            ))}
            <div className="note" style={{ marginTop: 8 }}>
              <InfoIcon />
              <span>
                Cameras are genlocked to the suit clock. A camera that reconnects mid-take is blended
                back in on the next frame.
              </span>
            </div>
            <Link className="btn btn--ghost" to="/settings/calibration">
              Open scene calibration
            </Link>
          </div>
        )}
      </aside>

      <section className="record__main">
        <div className="record__statusbar">
          <span className="chip chip--static">
            <span className="dot dot--live" />
            Skeleton ready
          </span>
          <span className="chip chip--static">
            {online} of {cams.length} cameras streaming
          </span>
          {recording && (
            <span className="chip chip--static" style={{ color: 'var(--pink)', fontWeight: 700 }}>
              <span className="dot dot--rec" />
              Recording {formatElapsed(elapsed)}
            </span>
          )}
          <span className="spacer" />
          <label className="row" style={{ gap: 8 }}>
            <LayoutIcon />
            <span style={{ fontWeight: 700 }}>Layout:</span>
            <select
              className="select"
              style={{ width: 'auto', marginTop: 0 }}
              value={layout}
              aria-label="Camera layout"
              onChange={(e) => setLayout(e.target.value as Layout)}
            >
              <option value="quad">Quad</option>
              <option value="split">Split</option>
              <option value="single">Single</option>
            </select>
          </label>
        </div>

        <div className="record__grid" data-layout={layout}>
          {visible.map((cam) => (
            <div
              key={cam.id}
              className={`camtile${cam.status === 'offline' ? ' camtile--offline' : ''}`}
            >
              <span className="camtile__label">
                <span
                  className={`camtile__dot${cam.status === 'offline' ? ' camtile__dot--off' : ''}`}
                />
                {cam.label}
              </span>
              {cam.status === 'streaming' ? (
                <StickFigure pose={cam.id % 2 ? 'stand' : 'walk'} color="var(--blue)" size={130} />
              ) : (
                <span>Waiting for signal</span>
              )}
              {recording && cam.status === 'streaming' && (
                <span className="camtile__rec">REC {formatElapsed(elapsed)}</span>
              )}
            </div>
          ))}
        </div>

        {alertOpen && cams.some((c) => c.status === 'offline') && (
          <div className="alert">
            <AlertIcon />
            <span>
              <b>Camera 3 lost connection.</b> Recording can continue on 3 cameras — accuracy around
              the left side may drop.
            </span>
            <span className="spacer" />
            <button className="btn btn--sm btn--ghost" onClick={() => reconnect(3)}>
              Reconnect
            </button>
            <button className="iconbtn" aria-label="Dismiss alert" onClick={() => setAlertOpen(false)}>
              <CloseIcon size={16} />
            </button>
          </div>
        )}
      </section>

      {toast === 'calibration' && (
        <Toast
          message={<>Calibration saved to <b>Suit A</b></>}
          actionLabel="Undo"
          onAction={() => setToast(null)}
          onClose={() => setToast(null)}
        />
      )}
      {toast === 'saved' && (
        <Toast
          message="Take saved to Recordings"
          actionLabel="View"
          onAction={() => setToast(null)}
          onClose={() => setToast(null)}
        />
      )}
    </div>
  )
}

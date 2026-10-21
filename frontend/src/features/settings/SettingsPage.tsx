import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useSettings, type TextSize } from '@/app/SettingsProvider'
import {
  AccessibilityIcon,
  CalibrateIcon,
  DeviceIcon,
  InfoIcon,
  LinkIcon,
} from '@/components/ui/Icons'
import { savedDevices } from '@/lib/data'
import './settings.css'

const SECTIONS = [
  { id: 'devices', title: 'Saved devices', sub: 'Suits, gloves and cameras', Icon: DeviceIcon },
  { id: 'calibration', title: 'Scene calibration', sub: 'Floor, volume and markers', Icon: CalibrateIcon },
  { id: 'api', title: 'API and integrations', sub: 'Keys, webhooks, engines', Icon: LinkIcon },
  { id: 'accessibility', title: 'Accessibility', sub: 'Motion, sound, text spacing', Icon: AccessibilityIcon },
] as const

type SectionId = (typeof SECTIONS)[number]['id']

const TEXT_SIZES: { id: TextSize; label: string }[] = [
  { id: 'small', label: 'Small' },
  { id: 'default', label: 'Default' },
  { id: 'large', label: 'Large' },
  { id: 'xlarge', label: 'Extra large' },
]

export function SettingsPage() {
  const { section } = useParams()
  const { settings, update, save, reset } = useSettings()
  const active: SectionId = SECTIONS.some((s) => s.id === section)
    ? (section as SectionId)
    : 'accessibility'

  return (
    <div className="page">
      <h1 className="page-title" style={{ marginBottom: 34 }}>
        Settings
      </h1>

      <div className="settings">
        <nav className="settings__nav" aria-label="Settings sections">
          {SECTIONS.map(({ id, title, sub, Icon }) => (
            <Link
              key={id}
              to={`/settings/${id}`}
              className="settings__navitem"
              aria-current={active === id}
            >
              <span className="settings__icon">
                <Icon />
              </span>
              <span>
                <strong>{title}</strong>
                <span>{sub}</span>
              </span>
            </Link>
          ))}
        </nav>

        <section>
          {active === 'accessibility' && (
            <>
              <h2 className="settings__title">Accessibility</h2>
              <p className="settings__sub">
                Tune how the app looks, moves and sounds. Changes apply to every screen.
              </p>

              <div className="settings__cols">
                <div className="settings__stack">
                  <fieldset className="fieldset">
                    <legend>Motion</legend>
                    <label className="field">
                      <span className="field__label">Interface animation</span>
                      <span className="field__hint">
                        Reduced keeps things in place and removes sliding and easing.
                      </span>
                      <select
                        className="select"
                        value={settings.animation}
                        onChange={(e) =>
                          update({ animation: e.target.value as typeof settings.animation })
                        }
                      >
                        <option value="full">Full</option>
                        <option value="reduced">Reduced</option>
                        <option value="none">None</option>
                      </select>
                    </label>
                    <label className="check" style={{ marginTop: 16 }}>
                      <input
                        type="checkbox"
                        checked={settings.freezeViewport}
                        onChange={(e) => update({ freezeViewport: e.target.checked })}
                      />
                      Freeze the 3D viewport until I press play
                    </label>
                  </fieldset>

                  <fieldset className="fieldset">
                    <legend>Sound</legend>
                    <label className="check">
                      <input
                        type="checkbox"
                        checked={settings.toneOnTake}
                        onChange={(e) => update({ toneOnTake: e.target.checked })}
                      />
                      Tone at the start and end of a take
                    </label>
                    <label className="check">
                      <input
                        type="checkbox"
                        checked={settings.soundOnErrors}
                        onChange={(e) => update({ soundOnErrors: e.target.checked })}
                      />
                      Sound on errors and disconnections
                    </label>
                    <div className="field" style={{ marginTop: 16 }}>
                      <span className="field__label">Cue volume</span>
                      <div className="slider" style={{ marginTop: 10 }}>
                        <input
                          type="range"
                          min={0}
                          max={100}
                          value={settings.cueVolume}
                          aria-label="Cue volume"
                          onChange={(e) => update({ cueVolume: Number(e.target.value) })}
                        />
                        <span className="slider__value">{settings.cueVolume}%</span>
                      </div>
                    </div>
                  </fieldset>
                </div>

                <fieldset className="fieldset">
                  <legend>Text and spacing</legend>
                  <div className="field">
                    <span className="field__label">Text size</span>
                    <span className="field__hint">Applies to every screen, not just this one.</span>
                    <div className="sizes">
                      {TEXT_SIZES.map((s) => (
                        <button
                          key={s.id}
                          aria-pressed={settings.textSize === s.id}
                          onClick={() => update({ textSize: s.id })}
                        >
                          {s.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="field" style={{ marginTop: 22 }}>
                    <span className="field__label">Letter spacing</span>
                    <div className="slider" style={{ marginTop: 10 }}>
                      <input
                        type="range"
                        min={0}
                        max={0.2}
                        step={0.01}
                        value={settings.letterSpacing}
                        aria-label="Letter spacing"
                        onChange={(e) => update({ letterSpacing: Number(e.target.value) })}
                      />
                      <span className="slider__value">{settings.letterSpacing.toFixed(2)}em</span>
                    </div>
                  </div>

                  <div className="field" style={{ marginTop: 18 }}>
                    <span className="field__label">Word spacing</span>
                    <span className="field__hint">
                      Widens the gap between words without stretching the line.
                    </span>
                    <div className="slider" style={{ marginTop: 10 }}>
                      <input
                        type="range"
                        min={0}
                        max={0.4}
                        step={0.01}
                        value={settings.wordSpacing}
                        aria-label="Word spacing"
                        onChange={(e) => update({ wordSpacing: Number(e.target.value) })}
                      />
                      <span className="slider__value">{settings.wordSpacing.toFixed(2)}em</span>
                    </div>
                  </div>

                  <div className="field" style={{ marginTop: 18 }}>
                    <span className="field__label">Line height</span>
                    <div className="slider" style={{ marginTop: 10 }}>
                      <input
                        type="range"
                        min={1.2}
                        max={2.2}
                        step={0.1}
                        value={settings.lineHeight}
                        aria-label="Line height"
                        onChange={(e) => update({ lineHeight: Number(e.target.value) })}
                      />
                      <span className="slider__value">{settings.lineHeight.toFixed(1)}</span>
                    </div>
                  </div>

                  <label className="check" style={{ marginTop: 18 }}>
                    <input
                      type="checkbox"
                      checked={settings.underlineLinks}
                      onChange={(e) => update({ underlineLinks: e.target.checked })}
                    />
                    Always underline links
                  </label>
                </fieldset>
              </div>

              <div className="settings__preview">
                <p style={{ fontWeight: 700 }}>Preview</p>
                <div className="settings__previewbox">
                  <h4>Sprint Cycle — Take 04</h4>
                  <p>
                    Recorded from Suit A with four cameras. The AI filled in the forearms and head
                    where the suit has no sensor.
                  </p>
                </div>
              </div>
            </>
          )}

          {active === 'devices' && (
            <>
              <h2 className="settings__title">Saved devices</h2>
              <p className="settings__sub">
                Suits, gloves and camera rigs this studio has paired before.
              </p>
              <div className="settings__stack" style={{ marginTop: 26 }}>
                {savedDevices.map((d) => (
                  <div className="devicerow" key={d.id}>
                    <span className="settings__icon">
                      <DeviceIcon />
                    </span>
                    <div className="stack">
                      <strong>{d.name}</strong>
                      <span style={{ color: 'var(--muted)', fontSize: 13 }}>{d.kind}</span>
                    </div>
                    <span className="spacer" />
                    <span className="mono" style={{ color: 'var(--muted)', fontSize: 13 }}>
                      {d.battery}% · seen {d.lastSeen.toLowerCase()}
                    </span>
                    <span className={`badge badge--${d.status === 'Connected' ? 'suit' : 'review'}`}>
                      {d.status}
                    </span>
                    <button className="btn btn--sm btn--ghost">
                      Rename
                    </button>
                    <button className="btn btn--sm btn--danger">
                      Forget
                    </button>
                  </div>
                ))}
              </div>
            </>
          )}

          {active === 'calibration' && (
            <>
              <h2 className="settings__title">Scene calibration</h2>
              <p className="settings__sub">
                Where the floor is, how big the capture volume is, and which marker set the suit uses.
              </p>
              <div className="settings__cols">
                <fieldset className="fieldset">
                  <legend>Volume</legend>
                  <label className="field">
                    <span className="field__label">Floor height</span>
                    <input className="input mono" defaultValue="0.00 m" />
                  </label>
                  <label className="field" style={{ marginTop: 16 }}>
                    <span className="field__label">Capture volume</span>
                    <span className="field__hint">Width × depth × height, in metres.</span>
                    <input className="input mono" defaultValue="6.0 × 6.0 × 3.2" />
                  </label>
                  <label className="check" style={{ marginTop: 16 }}>
                    <input type="checkbox" defaultChecked />
                    Lock feet to the floor plane
                  </label>
                </fieldset>

                <fieldset className="fieldset">
                  <legend>Markers</legend>
                  <label className="field">
                    <span className="field__label">Marker set</span>
                    <select className="select" defaultValue="17">
                      <option value="17">17-point full body</option>
                      <option value="23">23-point full body + hands</option>
                      <option value="34">34-point full body + face</option>
                    </select>
                  </label>
                  <p className="note" style={{ marginTop: 18 }}>
                    <InfoIcon />
                    <span>
                      Last calibrated <b>today at 09:14</b> from Suit A. Recalibrating clears the
                      current skeleton offsets.
                    </span>
                  </p>
                  <button
                    className="btn btn--primary"
                    style={{ marginTop: 18 }}
                  >
                    Recalibrate now
                  </button>
                </fieldset>
              </div>
            </>
          )}

          {active === 'api' && (
            <>
              <h2 className="settings__title">API and integrations</h2>
              <p className="settings__sub">
                Keys for the capture API, webhooks for finished takes, and the engines you stream to.
              </p>
              <div className="settings__cols">
                <fieldset className="fieldset">
                  <legend>Keys</legend>
                  <div className="keyrow">
                    <div className="stack">
                      <strong>Studio key</strong>
                      <code>mcp_live_••••••••••4f2a</code>
                    </div>
                    <span className="spacer" />
                    <button className="btn btn--sm btn--ghost">
                      Copy
                    </button>
                  </div>
                  <div className="keyrow" style={{ borderBottom: 0 }}>
                    <div className="stack">
                      <strong>Read-only key</strong>
                      <code>mcp_read_••••••••••91c7</code>
                    </div>
                    <span className="spacer" />
                    <button className="btn btn--sm btn--ghost">
                      Rotate
                    </button>
                  </div>
                </fieldset>

                <fieldset className="fieldset">
                  <legend>Webhook</legend>
                  <label className="field">
                    <span className="field__label">Take finished</span>
                    <span className="field__hint">Called once a take is processed and stored.</span>
                    <input className="input mono" defaultValue="https://hooks.example.edu/mocap" />
                  </label>
                  <label className="check" style={{ marginTop: 16 }}>
                    <input type="checkbox" defaultChecked />
                    Include the confidence report
                  </label>
                </fieldset>

                <fieldset className="fieldset">
                  <legend>Engines</legend>
                  <label className="check">
                    <input type="checkbox" defaultChecked />
                    Unreal Engine 5 — Live Link
                  </label>
                  <label className="check">
                    <input type="checkbox" />
                    Unity — Mocap Relay
                  </label>
                  <label className="check">
                    <input type="checkbox" defaultChecked />
                    Blender bridge
                  </label>
                </fieldset>
              </div>
            </>
          )}

          <div className="settings__footer">
            <p className="note">
              <InfoIcon />
              <span>
                <b>You can change this later</b> — every setting here can be adjusted at any time,
                and nothing you have recorded is affected.
              </span>
            </p>
            <button
              className="btn btn--ghost"
              onClick={() => {
                reset()
              }}
            >
              Reset to defaults
            </button>
            <button
              className="btn btn--primary"
              onClick={() => {
                save()
              }}
            >
              Save changes
            </button>
          </div>
        </section>
      </div>

    </div>
  )
}

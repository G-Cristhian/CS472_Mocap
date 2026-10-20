import { Link, Navigate } from 'react-router-dom'
import { useAuth } from '@/app/AuthProvider'
import { LogoMark } from '@/components/ui/Icons'
import './landing.css'

const STEPS = [
  {
    title: 'Place your phones',
    text: 'Set up two to four cameras in an arc around the space, all facing the performer. Phones you already own are enough.',
  },
  {
    title: 'Clap once',
    text: 'The clap lines every video up on one clock, so each frame lines up with the same moment on every camera.',
  },
  {
    title: 'Stand, then move',
    text: 'A few seconds standing upright sets the real height. About ten seconds of walking and turning lets the cameras calibrate themselves.',
  },
  {
    title: 'Get the motion',
    text: 'Receive 3D joint positions in metres and a skeleton file that opens in Blender or any tool that reads BVH.',
  },
]

const REASONS = [
  {
    title: 'No markers, no suit',
    text: 'The pose tracker reads the body straight from video. Nothing to strap on, nothing to stick on.',
  },
  {
    title: 'Calibrates itself',
    text: 'The cameras are placed from the performer’s own movement, so there is no checkerboard to print or carry.',
  },
  {
    title: 'Open formats',
    text: 'Export BVH skeletons and JSON joint data. Your footage and your results stay yours to use anywhere.',
  },
  {
    title: 'Works with what you have',
    text: 'iPhone lens data is read from the video automatically. Webcams work too, with a field-of-view setting.',
  },
]

const USES = [
  {
    title: 'Coaches and athletes',
    text: 'Compare a technique from several angles at once, and review it frame by frame.',
  },
  {
    title: 'Dancers and choreographers',
    text: 'Capture a routine and review it as a 3D figure, not just as video.',
  },
  {
    title: 'Animators and game developers',
    text: 'Start a character animation from a real performance instead of keyframing it from scratch.',
  },
  {
    title: 'Clinics and researchers',
    text: 'Record movement in a room you already have, without booking a motion capture studio.',
  },
]

// The skeleton in the hero, in the same layout as the logo's joints
const SKELETON_LINES =
  'M160 82V105M125 115H195M125 115L105 160L95 205M195 115L215 160L225 205M125 115L140 180M195 115L180 180M140 180H180M140 180L145 225L140 270M180 180L175 225L180 270'

const JOINTS = [
  { cx: 160, cy: 60, r: 22, fill: '#e31c79' },
  { cx: 125, cy: 115, r: 15, fill: '#6d4aff' },
  { cx: 195, cy: 115, r: 15, fill: '#6d4aff' },
  { cx: 105, cy: 160, r: 13, fill: '#5b8cff' },
  { cx: 215, cy: 160, r: 13, fill: '#5b8cff' },
  { cx: 95, cy: 205, r: 13, fill: '#5b8cff' },
  { cx: 225, cy: 205, r: 13, fill: '#5b8cff' },
  { cx: 140, cy: 180, r: 15, fill: '#6d4aff' },
  { cx: 180, cy: 180, r: 15, fill: '#6d4aff' },
  { cx: 145, cy: 225, r: 13, fill: '#5b8cff' },
  { cx: 175, cy: 225, r: 13, fill: '#5b8cff' },
  { cx: 140, cy: 270, r: 13, fill: '#5b8cff' },
  { cx: 180, cy: 270, r: 13, fill: '#5b8cff' },
]

export function LandingPage() {
  const { user, loading } = useAuth()

  // Logged-in users skip the marketing page
  if (loading) return null
  if (user) return <Navigate to="/projects" replace />

  return (
    <div className="landing">
      <header className="landing__header">
        <Link to="/" className="landing__brand">
          <LogoMark size={50} />
          <span>MotionBoxPro</span>
        </Link>
        <nav className="landing__nav" aria-label="Landing page">
          <div className="landing__links">
            <a href="#how">How it works</a>
            <a href="#why">Why MotionBoxPro</a>
            <a href="#who">Who it’s for</a>
          </div>
          <div className="landing__actions">
            <Link to="/login">Log in</Link>
            <Link className="btn btn--primary btn--sm" to="/register">
              Get started
            </Link>
          </div>
        </nav>
      </header>

      <main>
        <section className="landing__hero">
          <div>
            <p className="landing__eyebrow">Markerless motion capture</p>
            <h1>Motion capture from the phones you already own.</h1>
            <p className="landing__lead">
              Film a performance with two to four phones or webcams. MotionBoxPro turns the footage into a 3D
              skeleton you can play back and export, with no markers and no studio.
            </p>
            <div className="landing__ctas">
              <Link className="btn btn--primary" to="/register">
                Start capturing
              </Link>
              <a className="btn btn--ghost" href="#how">
                See how it works
              </a>
            </div>
          </div>

          <figure className="landing__stage">
            <svg viewBox="0 0 320 300" fill="none" aria-hidden="true">
              <path d={SKELETON_LINES} stroke="#fff" strokeOpacity="0.4" strokeWidth="9" strokeLinecap="round" strokeLinejoin="round" />
              {JOINTS.map((joint, i) => (
                <circle
                  key={i}
                  className="landing__joint"
                  cx={joint.cx}
                  cy={joint.cy}
                  r={joint.r}
                  fill={joint.fill}
                  style={{ animationDelay: `${(i * 0.2) % 2.4}s` }}
                />
              ))}
            </svg>
            <figcaption>Illustration: joints tracked on every frame</figcaption>
          </figure>
        </section>

        <section className="landing__section" id="how">
          <p className="landing__eyebrow">How it works</p>
          <h2 className="landing__h2">From a few recordings to a skeleton in four steps.</h2>
          <ol className="landing__steps">
            {STEPS.map((step, i) => (
              <li className="landing__step" key={step.title}>
                <span className="landing__num">0{i + 1}</span>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="landing__section" id="why">
          <p className="landing__eyebrow">Why MotionBoxPro</p>
          <h2 className="landing__h2">Studio-style results without the studio.</h2>
          <ul className="landing__grid">
            {REASONS.map((reason) => (
              <li className="landing__card" key={reason.title}>
                <h3>{reason.title}</h3>
                <p>{reason.text}</p>
              </li>
            ))}
          </ul>
        </section>

        <section className="landing__section" id="who">
          <p className="landing__eyebrow">Who it’s for</p>
          <h2 className="landing__h2">Anyone who needs to see movement in 3D.</h2>
          <ul className="landing__grid">
            {USES.map((use) => (
              <li className="landing__card" key={use.title}>
                <h3>{use.title}</h3>
                <p>{use.text}</p>
              </li>
            ))}
          </ul>
        </section>

        <section className="landing__section">
          <div className="landing__band">
            <h2>Record your first take.</h2>
            <p>Create an account, set up two phones, and see your movement as a 3D skeleton.</p>
            <div className="landing__ctas landing__ctas--center">
              <Link className="btn btn--white" to="/register">
                Create account
              </Link>
              <Link className="btn btn--outline-white" to="/login">
                Log in
              </Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="landing__footer">
        <span>© {new Date().getFullYear()} MotionBoxPro</span>
        <nav aria-label="Footer">
          <Link to="/login">Log in</Link>
          <Link to="/register">Sign up</Link>
        </nav>
      </footer>
    </div>
  )
}

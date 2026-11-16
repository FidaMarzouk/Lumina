import { OpenDoor } from '../art/Illustrations'
import Logo from '../brand/Logo'
import Horizon from '../paper/Horizon'
import { HelpLink } from '../layout/Header'
import AppearanceMenu from '../ui/AppearanceMenu'
import RingButton from '../ui/RingButton'
import { ArrowIcon } from '../ui/Icons'

function LandingPage({ onStart, onHelp, user, onLogIn, appearance }) {
  return (
    <div className="landing">
      <header className="rulebar">
        <span className="brand" role="img" aria-label="Lumina"><Logo /></span>
        <Horizon slow={appearance.night} />
        <nav className="rulebar-links" aria-label="Page">
          <a href="#how">How it works</a>
          {user
            ? <span className="rulebar-who">Hi{user.display_name ? `, ${user.display_name}` : ''}</span>
            : <button type="button" className="link-quiet" onClick={onLogIn}>Log in</button>}
          <AppearanceMenu appearance={appearance} />
          <HelpLink onHelp={onHelp} />
        </nav>
      </header>

      <section className="hero" aria-labelledby="hero-title">
        <div className="hero-copy">
          <h1 id="hero-title" className="display">Say what's<br />on your<br />mind</h1>
          <p className="kicker">A quiet place to talk, out loud or in writing</p>
          <span className="bar" aria-hidden="true" />
        </div>
        <OpenDoor className="hero-art" />
        <button type="button" className="pill-cta" onClick={onStart}>
          <span className="pill-word">Start talking</span>
          <span className="ring-btn ring-static" aria-hidden="true"><ArrowIcon /></span>
        </button>
      </section>

      <section id="how" className="how" aria-labelledby="how-title">
        <div className="how-copy">
          <h2 id="how-title" className="display display-md">Talk it through,<br />at your pace</h2>
          <dl className="dots">
            <div><dt>Talk or text 24/7, Lumina listens</dt><dd>Sometimes you just need to say things out loud. You can talk to Lumina like you would on a phone call or text.</dd></div>
            <div><dt>Grounded in scientific research</dt><dd>Lumina is designed for human psychology, drawing on real medical literature and scientific research.</dd></div>
            <div><dt>Here to support</dt><dd>Lumina offers a space for emotional support and reflection, alongside, not instead of, professional care.</dd></div>
          </dl>
          <RingButton label="Start talking" onClick={onStart} className="how-go" />
        </div>
      </section>
    </div>
  )
}

export default LandingPage

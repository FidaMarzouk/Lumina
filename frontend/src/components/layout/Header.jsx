import Logo from '../brand/Logo'
import Horizon from '../paper/Horizon'
import AppearanceMenu from '../ui/AppearanceMenu'
import { ChatIcon, CompassIcon, DaySunIcon, LighthouseIcon, NewChatIcon, PenIcon, SlidersIcon, SparkIcon, UserIcon } from '../ui/Icons'

// Signed-in people move between talking, today's desk, their journal, journeys and insights; the open
// conversation carries on. The pages are page-marker tabs clipped to the top of the notebook: each its own
// colour, the open one pulled all the way out, the others slide out a little when the pointer reaches them.
const PAGES = [
  { id: 'app', label: 'Talk', Icon: ChatIcon, tone: 'coral' },
  { id: 'today', label: 'Today', Icon: DaySunIcon, tone: 'butter' },
  { id: 'journal', label: 'Journal', Icon: PenIcon, tone: 'mint' },
  { id: 'journeys', label: 'Journeys', Icon: CompassIcon, tone: 'peach' },
  { id: 'insights', label: 'Insights', Icon: SparkIcon, tone: 'sage' },
]

// "Get help" is the same everywhere: a tiny lighthouse, plain and always visible.
export const HelpLink = ({ onHelp }) => (
  <button type="button" className="link-help" onClick={onHelp}><LighthouseIcon />Get help</button>
)

function Header({ view = 'app', onNavigate, onHome, onNewChat, onHelp, onSettings, user, onAccount, onSignIn, appearance }) {
  return (
    <header className="rulebar rulebar-app">
      <button type="button" className="brand" onClick={onHome} aria-label="Lumina, back to the start page"><Logo /></button>
      <Horizon slow={appearance.night} />
      <HelpLink onHelp={onHelp} />
      {/* On phones these wrap onto their own row under the header. */}
      {user && (
        <nav className="marker-tabs" aria-label="Pages">
          {PAGES.map(({ id, label, Icon, tone }) => (
            <button key={id} type="button" className={`marker is-${tone} ${view === id ? 'is-current' : ''}`}
                    aria-current={view === id ? 'page' : undefined} onClick={() => onNavigate(id)}>
              <span className="marker-flag"><Icon /><span className="marker-label">{label}</span></span>
            </button>
          ))}
        </nav>
      )}
      <div className="rulebar-links">
        <AppearanceMenu appearance={appearance} />
        {view === 'app' && (
          <button type="button" className="link-quiet" onClick={onNewChat} aria-label="New chat">
            <NewChatIcon /><span className="label-wide">New chat</span>
          </button>
        )}
        {user ? (
          <button type="button" className="link-quiet" onClick={onAccount} aria-label="Your account">
            <UserIcon /><span className="label-wide">{user.display_name || 'Account'}</span>
          </button>
        ) : (
          <button type="button" className="link-quiet" onClick={onSignIn}>
            <UserIcon /><span className="label-wide">Sign up</span>
          </button>
        )}
        {view === 'app' && (
          <button type="button" className="link-quiet only-narrow" onClick={onSettings} aria-label="Style and voice settings">
            <SlidersIcon />
          </button>
        )}
      </div>
    </header>
  )
}

export default Header

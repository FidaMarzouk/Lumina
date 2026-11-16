import { useCallback, useEffect, useRef, useState } from 'react'
import Header from './components/layout/Header'
import ChatWindow from './components/chat/ChatWindow'
import InputBar from './components/chat/InputBar'
import LandingPage from './components/landing/LandingPage'
import AuthPage from './components/auth/AuthPage'
import JourneysPage from './components/screens/JourneysPage'
import InsightsPage from './components/screens/InsightsPage'
import TodayPage from './components/screens/TodayPage'
import JournalPage from './components/screens/JournalPage'
import Pond from './components/orb/Pond'
import PaperDefs from './components/paper/PaperDefs'
import NightSky from './components/paper/NightSky'
import BreathingPebble from './components/ui/BreathingPebble'
import Sparkles from './components/ui/Sparkles'
import HelpSheet from './components/ui/HelpSheet'
import CrisisPanel from './components/ui/CrisisPanel'
import Preferences from './components/ui/Preferences'
import SettingsSheet from './components/ui/SettingsSheet'
import AccountSheet from './components/ui/AccountSheet'
import { useAuth } from './hooks/useAuth'
import { useChat } from './hooks/useChat'
import { useVoice } from './hooks/useVoice'
import { usePersisted } from './hooks/usePersisted'
import { useAppearance } from './hooks/useDaylight'
import { fetchJar } from './api/personal.js'
import { styleById } from './components/ui/styles'

const STATUS = {
  listening: 'Listening',
  thinking: 'Thinking',
  speaking: 'Speaking',
  idle: 'Ready when you are',
}

function App() {
  // landing → (auth, unless signed in or continuing as a guest) → app; signed in, app ⇄ journeys ⇄ insights
  const [view, setView] = useState('landing')
  const [authMode, setAuthMode] = useState('register')
  const [accountOpen, setAccountOpen] = useState(false)
  const started = view === 'app'
  // The conversation stays open while a signed-in person looks at their journeys or insights.
  const inside = ['app', 'today', 'journal', 'journeys', 'insights'].includes(view)
  const [persona, setPersona] = usePersisted('lumina.style', 'listener')
  const [gender, setGender] = usePersisted('lumina.voice', 'female')
  // No sound by default: replies are read aloud only once the person turns it on.
  const [voiceOn, setVoiceOn] = usePersisted('lumina.readAloud', false)
  const [helpOpen, setHelpOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [listening, setListening] = useState(false)
  const pondRef = useRef(null)

  const appearance = useAppearance()
  const { paper, night } = appearance
  const auth = useAuth()
  const chat = useChat(persona, { token: auth.token, active: inside })
  const voice = useVoice({ gender, soft: night })
  const { speak, cancel, unlock, startMic, stopMic } = voice
  // What the person has kept in their jar, shown on hard days at the start of a conversation.
  const [helped, setHelped] = useState([])
  useEffect(() => {
    if (!auth.token || view !== 'app') return
    let live = true
    fetchJar(auth.token).then(j => { if (live) setHelped(j.kept.map(i => i.text)) }).catch(() => {})
    return () => { live = false }
  }, [auth.token, view])

  // Read each new reply aloud once (the greeting included), after the reply has arrived.
  const lastAi = [...chat.messages].reverse().find(m => m.role === 'ai')
  const spokenRef = useRef(null)
  useEffect(() => {
    if (!started || !voiceOn || chat.isTyping || !lastAi || spokenRef.current === lastAi.id) return
    spokenRef.current = lastAi.id
    speak(lastAi.text)
  }, [started, voiceOn, chat.isTyping, lastAi, speak])

  const send = useCallback(text => {
    unlock()
    cancel()
    chat.sendUserMessage(text)
  }, [unlock, cancel, chat])

  const onListeningChange = useCallback(on => {
    setListening(on)
    if (on) { unlock(); cancel(); startMic() } else stopMic()
  }, [unlock, cancel, startMic, stopMic])

  const listen = useCallback(text => { unlock(); speak(text) }, [unlock, speak])

  const start = () => { unlock(); setView(auth.status === 'guest' ? 'auth' : 'app') }
  const openAuth = mode => { cancel(); setAuthMode(mode); setView('auth') }
  const home = () => { cancel(); setView('landing') }
  // The open conversation is summarised before the token is revoked.
  const accountAuth = {
    ...auth,
    logout: async () => { await chat.endConversation(); await auth.logout(); setView('app') },
    deleteAccount: async password => { await auth.deleteAccount(password); setView('app') },
  }
  const navigate = next => { cancel(); setView(next) }
  // A journey step is a new, guided conversation (the current one is closed and summarised).
  const startJourney = journeyId => { cancel(); chat.startWith({ mode: 'guided', journeyId }); setView('app') }
  const newChat = () => { cancel(); chat.resetSession() }

  const help = <HelpSheet open={helpOpen} onClose={() => setHelpOpen(false)} />

  if (view === 'landing') {
    return (
      <>
        <PaperDefs />
        <Sparkles night={night} />
        {paper === 'night' && <NightSky />}
        <LandingPage onStart={start} onHelp={() => setHelpOpen(true)} user={auth.user} onLogIn={() => openAuth('login')}
                     appearance={appearance} />
        <BreathingPebble />
        {help}
      </>
    )
  }
  if (view === 'auth') {
    return (
      <>
        <PaperDefs />
        <Sparkles night={night} />
        {paper === 'night' && <NightSky />}
        <AuthPage key={authMode} initialMode={authMode} auth={auth} onDone={() => setView('app')}
                  onGuest={() => setView('app')} onHome={home} onHelp={() => setHelpOpen(true)}
                  appearance={appearance} />
        <BreathingPebble />
        {help}
      </>
    )
  }

  const mode = listening ? 'listening' : chat.isTyping ? 'thinking' : voice.speaking ? 'speaking' : 'idle'
  const style = styleById(persona)
  const prefs = idPrefix => (
    <Preferences
      idPrefix={idPrefix}
      persona={persona} onPersona={setPersona}
      gender={gender} onGender={setGender}
      voiceOn={voiceOn} onVoiceOn={on => { if (!on) cancel(); setVoiceOn(on) }}
    />
  )

  return (
    <div className="app">
      <PaperDefs />
        <Sparkles night={night} />
      {paper === 'night' && <NightSky />}
      <Header view={view} onNavigate={navigate} onHome={home} onNewChat={newChat} onHelp={() => setHelpOpen(true)}
              onSettings={() => setSettingsOpen(true)} user={auth.user} onAccount={() => setAccountOpen(true)}
              onSignIn={() => openAuth('register')} appearance={appearance} />

      {view === 'today' && auth.token && (
        <div className="page-scroll"><TodayPage token={auth.token} name={auth.user?.display_name} onStartJourney={startJourney}
                                                onTalk={() => navigate('app')} onInsights={() => navigate('insights')}
                                                onJournal={() => navigate('journal')} /></div>
      )}
      {view === 'journal' && auth.token && (
        <div className="page-scroll"><JournalPage token={auth.token} user={auth.user} onTalk={() => navigate('app')}
                                                  onHelp={() => setHelpOpen(true)} /></div>
      )}
      {view === 'journeys' && auth.token && (
        <div className="page-scroll"><JourneysPage token={auth.token} onStartJourney={startJourney} onTalk={() => navigate('app')} /></div>
      )}
      {view === 'insights' && auth.token && (
        <div className="page-scroll"><InsightsPage token={auth.token} name={auth.user?.display_name} onOpenAccount={() => setAccountOpen(true)} /></div>
      )}

      <main className="room" hidden={view !== 'app'}>
        <aside className="stage" aria-label="Lumina's voice">
          <div className="stage-orb">
            <Pond ref={pondRef} mode={mode} persona={persona} getLevel={voice.getLevel} label={`Lumina: ${STATUS[mode]}`} />
          </div>
          {mode === 'idle'
            ? <p className="stage-status"><strong className="stage-style">{style.label}</strong>{style.tip}</p>
            : <p className="stage-status is-active">{STATUS[mode]}</p>}
          <div className="stage-prefs">{prefs('side')}</div>
          <BreathingPebble className="breath-inline" />
        </aside>

        <section className="conversation" aria-label="Conversation">
          <ChatWindow messages={chat.messages} isTyping={chat.isTyping} onListen={listen} session={chat.session}
                      onStarter={send} onSuggest={auth.user ? () => navigate('journeys') : null}
                      onLeaveGuided={() => chat.startWith({ mode: 'open' })}
                      onWeather={chat.setWeather} onTear={chat.addLuminaLine} helped={auth.token ? helped : []}
                      night={night} onProposal={chat.resolveProposal} />
          {chat.error && <p className="error" role="alert">{chat.error}</p>}
          {chat.crisis && <CrisisPanel key={chat.crisis} subtype={chat.crisis} />}
          <InputBar onSend={send} disabled={chat.isTyping} onListeningChange={onListeningChange}
                    onType={() => pondRef.current?.stir()} />
        </section>
      </main>

      {view !== 'app' && <BreathingPebble />}
      <SettingsSheet open={settingsOpen} onClose={() => setSettingsOpen(false)}>{prefs('sheet')}</SettingsSheet>
      <AccountSheet open={accountOpen && !!auth.user} onClose={() => setAccountOpen(false)} auth={accountAuth} />
      {help}
    </div>
  )
}

export default App

import { STYLES } from './styles'

// Conversation style as five pebbles, with the voice options laid out underneath (reading replies aloud is off
// until the person turns it on).
// Rendered beside the pond on wide screens and in a sheet on phones, so `idPrefix` keeps the two copies'
// form ids distinct. The pebbles are radio buttons underneath, so arrow keys move between them.
function Preferences({ idPrefix, persona, onPersona, gender, onGender, voiceOn, onVoiceOn, serverVoice }) {
  return (
    <div className="prefs">
      <fieldset className="pref-group">
        <legend className="sr-only">Conversation style</legend>
        <div className="pebbles">
          {STYLES.map(({ id, label, tip, Icon }) => (
            <label key={id} className="pebble-opt" title={tip}>
              <input type="radio" name={`${idPrefix}-style`} value={id} checked={persona === id}
                     onChange={() => onPersona(id)} aria-describedby={`${idPrefix}-tip-${id}`} />
              <span className="pebble" aria-hidden="true"><Icon /></span>
              <span className="pebble-name">{label}</span>
              <span id={`${idPrefix}-tip-${id}`} className="sr-only">{tip}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="pref-group pref-voice">
        <legend className="pref-title hand">Lumina's voice</legend>
        <div className="seg" role="radiogroup" aria-label="Voice">
          {['female', 'male'].map(g => (
            <label key={g} className="seg-opt">
              <input type="radio" name={`${idPrefix}-voice`} value={g} checked={gender === g} onChange={() => onGender(g)} />
              <span>{g === 'female' ? 'Female' : 'Male'}</span>
            </label>
          ))}
        </div>
        <label className="switch">
          <input type="checkbox" role="switch" checked={voiceOn} onChange={e => onVoiceOn(e.target.checked)} />
          <span className="switch-track" aria-hidden="true" />
          <span>Read replies aloud</span>
        </label>
        {serverVoice === false && (
          <p className="pref-note">Using your browser's built-in voice. For the natural voice, install the voice extra on the server.</p>
        )}
      </fieldset>
    </div>
  )
}

export default Preferences

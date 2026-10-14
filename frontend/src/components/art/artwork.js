// The hand-painted illustrations from the Lumina brief (backgrounds made transparent, WebP).
// Decorative: always rendered with alt="" next to text that carries the meaning.
import gardener from '../../assets/art/gardener.webp'
import horizonChair from '../../assets/art/horizon-chair.webp'
import leafFace from '../../assets/art/leaf-face.webp'
import openDoor from '../../assets/art/open-door.webp'
import restingCloud from '../../assets/art/resting-cloud.webp'
import runner from '../../assets/art/runner.webp'
import thornsHug from '../../assets/art/thorns-hug.webp'

export const ART = { gardener, horizonChair, leafFace, openDoor, restingCloud, runner, thornsHug }

// One picture per journey, chosen for what the journey is about.
const JOURNEY_ART = {
  thought_record: leafFace,          // untangling a thought
  behavioural_activation: runner,    // small steps back to what lifts you
  grounding_anxiety: horizonChair,   // steadying the storm
  sleep_reset: restingCloud,         // a gentler path to sleep
  self_compassion: thornsHug,        // being on your own side
  reconnecting: openDoor,            // reaching back toward people
  values_and_direction: gardener,    // tending what matters
}

export const journeyArt = id => JOURNEY_ART[id] ?? gardener

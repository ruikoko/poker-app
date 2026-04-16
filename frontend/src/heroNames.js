// Central list of hero aliases and friend group — single source of truth.
//
// HERO_NAMES   → user's own accounts across all poker sites.
//                Used to mark players as hero in replayer/tables,
//                colour badges, select the hero seat, etc.
//
// FRIEND_NICKS → hero + team/friend accounts that should be
//                EXCLUDED from the villain database.
//                Imported by villains list logic and related code.
//
// Matching is always case-insensitive. Values are stored lowercase.
// When a nickname appears in different forms on different sites
// (ex. "freeolivença" vs "freeoliven&ccedil;a"), both variants
// are listed so all formats match.

export const HERO_NAMES = new Set([
  // Generic marker used by anonymised HH
  'hero',

  // Lobbarize account list (April 2026)
  'thinvalium',
  'lauro dermio',
  'lauro derm',          // truncated form seen in some screenshots
  'schadenfreud',
  'kabalaharris',
  'ruing',               // 888 account
  'misterpoker1973',
  'gajodopao',
  'koumpounophobia',
  'cringemeariver',
  'cr7dagreta',
  'rail iota',
  'queleiteon',
  'trapatonigpt',
  'dapanal',
  'dapanal?',            // literal ? as it appears on some sites
  'narsa114',
  'patodesisto',
  'nuncabatman',
  'proctocolectomy',
  'pelosinthenancy',
  'pelosintenancy',      // alternate spelling on another site
  'pelosithenancy',      // variant seen in legacy data
  'pagachorari',
  'sticklapisse',
  'autoswiperight',
  'paidaskengas',
  'freeolivença',
  'freeoliven&ccedil;a', // HTML-encoded variant
  'robyoungbff',
  'pokerfan1967',
  'kokonakueka',
  'cunetejaune',
  'leportugay8',
  'cr7dapussy',
  'ederbutdor',
  'opaidasputas',
  'hollywoodpimp',
  'aturatu',
  'opaidelas',
  'covfef3',
  'iuse2bspewer',
])

// Friend / team group nicks — NOT hero, but also NOT villains.
// Used to filter these players out of the villain profile database.
const FRIEND_ONLY_NICKS = [
  '1otario', 'a lagardere', 'abutrinzi', 'algorhythm',
  'amazeswhores', 'arr0zdepat0', 'avecamos', 'beijamyrola',
  'cattleking', 'cavalitos', 'cmaculatum', 'coconacueca',
  'crashcow', 'decode', 'deusfumo', 'djobidjoba87',
  'dlncredible', 'eitaqdelicia', 'el kingzaur', 'etonelespute',
  'flightrisk', 'floptwist', 'godsmoke', 'golimar666',
  'grenouille', 'grenouiile', 'hmhm', 'huntermilf',
  'i<3kebab', 'ipaysor', 'jackpito', 'joao barbosa',
  'johngeologic', 'karluz', 'klklwoku', 'lendiadbisca',
  'lewinsky', 'ltbau', 'luckytobme', 'luckytobvsu',
  'milffinder', 'milfodds', 'mmaboss', 'mrpeco',
  'mrpecoo', 'neurose', 'obviamente.', 'ohum',
  'pec0', 'priest lucy', 'quimterro', 'quimtrega',
  'rapinzi', 'rapinzi12', 'rapinzi1988', 'rapinzigg',
  'rosanorte', 'ryandays', 'sapinzi', 'sapz',
  'shaamp00', 'shrug', 'takiozaur', 'thanatos',
  'toniextractor', 'tonixtractor', 'tonixtractor2',
  'traumatizer', 'vanaldinho', 'vascodagamba',
  'vtmizer', 'zen17', 'zen1to',
  // Hash-based nick seen on Winamax.fr
  'c78d63886ce0850aa6e75c3b58d63b',
  // Historical aliases preserved from legacy FRIEND_NICKS
  'andacasa', 'jeandouca',
]

// FRIEND_NICKS = all hero accounts + friend-only accounts.
// Using a Set automatically deduplicates any overlap.
export const FRIEND_NICKS = new Set([...HERO_NAMES, ...FRIEND_ONLY_NICKS])

export function isHero(name) {
  if (!name) return false
  return HERO_NAMES.has(String(name).toLowerCase().trim())
}

export function isFriend(name) {
  if (!name) return false
  return FRIEND_NICKS.has(String(name).toLowerCase().trim())
}

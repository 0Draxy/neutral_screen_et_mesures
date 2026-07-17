/*
  RP2040 - Pilotage relais 28 VDC - V2.12.3 R8 selection Neutral screen + chronometrie EA

  Etat fonctionnel V2.12.3 R8 :
  - BE sur GP14, BR sur GP15 et selection 28/32 V sur GP26.
  - LED RGB interne WS2812 sur GP16 pilotee par commandes serie LED;...
  - Sequence Neutral Screen non bloquante avec settle, pulse et retombee relais.
  - Pulses courts executes en section critique pour respecter les temps relais.
  - Lecture des contacts R1-R4/T1-T4 avec pull-up externes.
  - Mesure chronometrique BE/BR et monostable avec capture GPIO rapide.
  - Horodatage apres lecture gpio_get_all(), overflow explicite et LOOP_MAX_US.
  - Mesure tension : capture au premier passage complet avant rebonds, puis validation stable.
  - Trame HELLO annonce V2_12_3_R8 et la capacite EA_CHRONO_NO_GP26.

  Principe inchange :
  - Le PC/IHM ne pilote jamais les fronts en temps reel.
  - Le Python convertit chaque champ en microsecondes.
  - Le RP2040 recoit uniquement des durees en microsecondes.
  - Alarme materielle Pico SDK + sorties GPIO directes.
  - Durees longues en uint64_t.

  Commandes serie :
    START_US;MONO;ON_US;OFF_US;SET_US;RESET_US;CYCLES
    START_US;BISTABLE;ON_US;OFF_US;SET_US;RESET_US;CYCLES
    PULSE_US;BE;DUREE_US[;EA] -> pulse BE ; suffixe EA = ne pas commuter GP26
    PULSE_US;BR;DUREE_US[;EA] -> pulse BR ; suffixe EA = ne pas commuter GP26
    PULSE_US;BEBR;DUREE_US    -> selection tension basse puis pulse BE+BR
    MEASURE_CONTACTS;BE;CAPTURE_US;PULSE_US;NB_INV[;EA]  -> chronometrie contacts BE
    MEASURE_CONTACTS;BR;CAPTURE_US;PULSE_US;NB_INV[;EA]  -> chronometrie contacts BR
    MEASURE_MONO;ON;CAPTURE_US;HOLD_US;NB_INV[;EA]       -> chronometrie monostable enclenchement GP14
    MEASURE_MONO;OFF;CAPTURE_US;HOLD_US;NB_INV[;EA]      -> chronometrie monostable declenchement GP14
    VOLTAGE_CFG;RATIO_U6;OFFSET_MV;STABLE_US          -> calibration ADS1115
    VOLTAGE_SCAN;ARM;PICKUP|DROPOUT;NB_INV            -> armement mesure tension
    VOLTAGE_SCAN;CANCEL                                -> annulation mesure tension
    COIL_HOLD;BE|BR|ON|OFF                             -> maintien bobine choisie pendant rampe EA (ON=BE compat.)
    ADS?                                               -> etat et tension ADS1115
    LED;CONNECTED / BOOT / CYCLE_DONE / BE / BR / BEBR / SELECT32 / ACCEPT / REJECT / ERROR
    STOP / PAUSE / RESUME / STATUS?

  Broches :
    GP14 -> MOSFET 1 -> bobine monostable ou bobine SET
    GP15 -> MOSFET 2 -> bobine RESET
    GP16 -> LED RGB interne WS2812 de la RP2040-Zero
    GP26 -> MOSFET relais 5 Vdc selection tension basse/haute
    GP0  -> SDA ADS1115
    GP1  -> SCL ADS1115
*/

#include <Arduino.h>
#include <Adafruit_NeoPixel.h>
#include <Wire.h>

#if !defined(ARDUINO_ARCH_RP2040)
#error "Ce sketch est prevu pour une carte RP2040."
#endif

#include "pico/time.h"
#include "pico/sync.h"
#include "hardware/gpio.h"
#include "hardware/sync.h"

static const uint8_t PIN_SORTIE_1 = 14;
static const uint8_t PIN_SORTIE_2 = 15;
static const uint8_t PIN_SELECT_32V = 26;   // commande MOSFET du relais inverseur tension basse/haute
static const uint8_t PIN_LED_INTERNE = 25;
static const uint8_t PIN_LED_RGB = 16;      // LED RGB interne WS2812 de la RP2040-Zero
static const uint8_t LED_RGB_COUNT = 1;
static const uint8_t LED_RGB_BRIGHTNESS = 50;


// ADS1115 : mesure locale de la tension réellement appliquée à la bobine.
// A0 reçoit la sortie du pont 39 kΩ / 3,3 kΩ. Alimentation ADS = 3,3 V.
static const uint8_t PIN_ADS_SDA = 0;
static const uint8_t PIN_ADS_SCL = 1;
static const uint8_t ADS1115_ADDR = 0x48;
static const uint16_t ADS1115_CONFIG_CONT_A0_4096_860SPS = 0xC2E3;
static const uint64_t ADS_SAMPLE_PERIOD_US = 1200ULL;
static const uint32_t VOLTAGE_RATIO_U6_DEFAULT = 12818182UL; // 12,818182
static const int32_t VOLTAGE_OFFSET_MV_DEFAULT = 0;
static const uint32_t VOLTAGE_STABLE_US_DEFAULT = 3000UL;

Adafruit_NeoPixel ledRgb(LED_RGB_COUNT, PIN_LED_RGB, NEO_GRB + NEO_KHZ800);

enum LedRgbMode : uint8_t {
  LED_MODE_BOOT = 0,
  LED_MODE_CONNECTED,
  LED_MODE_CYCLE_DONE,
  LED_MODE_PULSE_BE,
  LED_MODE_PULSE_BR,
  LED_MODE_PULSE_BEBR,
  LED_MODE_SELECT32,
  LED_MODE_ACCEPT,
  LED_MODE_REJECT,
  LED_MODE_ERROR
};

LedRgbMode ledRgbMode = LED_MODE_BOOT;
uint32_t ledRgbModeStartMs = 0UL;
uint32_t ledRgbDerniereCouleur = 0xFFFFFFFFUL;
uint32_t ledRgbDernierUpdateMs = 0UL;
volatile uint8_t ledRgbModeMachinePending = 255u;

static const uint8_t PIN_CONTACT_RESET_1 = 10;
static const uint8_t PIN_CONTACT_RESET_2 = 11;
static const uint8_t PIN_CONTACT_RESET_3 = 6;
static const uint8_t PIN_CONTACT_RESET_4 = 7;

static const uint8_t PIN_CONTACT_LATCH_1 = 12;
static const uint8_t PIN_CONTACT_LATCH_2 = 13;
static const uint8_t PIN_CONTACT_LATCH_3 = 8;
static const uint8_t PIN_CONTACT_LATCH_4 = 9;

// Les 8 contacts utilisent des résistances de pull-up EXTERNES.
// Câblage attendu : entrée GPxx -> résistance 10 kΩ -> 3V3 RP2040,
// et contact sec entre entrée GPxx et GND.
// Contact ouvert = HIGH = 0 / LED éteinte.
// Contact fermé vers GND = LOW = 1 / LED allumée.
static const bool CONTACTS_PULLUP_EXTERNES = true;

static const uint32_t MASK_SORTIE_1 = (1u << PIN_SORTIE_1);
static const uint32_t MASK_SORTIE_2 = (1u << PIN_SORTIE_2);
static const uint32_t MASK_SELECT_32V = (1u << PIN_SELECT_32V);
static const uint32_t MASK_LED = (1u << PIN_LED_INTERNE);
static const uint32_t MASK_ALL = MASK_SORTIE_1 | MASK_SORTIE_2 | MASK_LED;

static const uint64_t NEUTRAL_SELECTION_SETTLE_US = 20000ULL;  // 20 ms collage relais selection avant le pulse
static const uint64_t NEUTRAL_RELEASE_SETTLE_US = 20000ULL;     // 20 ms retombee relais selection apres un pulse en voie haute

static const uint64_t MIN_US = 1ULL;
static const uint64_t MAX_US = 4294967295000ULL;  // 4 294 967 295 ms ~ 1193 h
static const uint32_t STATUS_PERIOD_MS = 1000UL;

static const uint64_t CONTACT_SAMPLE_PERIOD_US = 250ULL;
static const uint64_t CONTACT_CHANGE_MIN_SEND_US = 1000ULL;
static const uint64_t CONTACT_HEARTBEAT_PERIOD_US = 250000ULL;
static const uint64_t SORTIE_CHANGE_MIN_SEND_US = 1000ULL;
static const uint64_t NEUTRAL_DIRECT_MAX_US = 1000ULL;

static const uint64_t MEASURE_CAPTURE_MIN_US = 1000ULL;
static const uint64_t MEASURE_CAPTURE_MAX_US = 100000ULL;
static const uint16_t MEASURE_MAX_EVENTS = 192;

enum ModeRelais : uint8_t {
  MODE_MONO = 0,
  MODE_BISTABLE = 1
};

enum EtatMachine : uint8_t {
  ETAT_ARRET = 0,
  ETAT_MONO_ON,
  ETAT_MONO_OFF,
  ETAT_BI_PULSE_SET,
  ETAT_BI_WAIT_ON,
  ETAT_BI_PULSE_RESET,
  ETAT_BI_WAIT_OFF,
  ETAT_PAUSE,
  ETAT_NEUTRAL_PULSE
};

// ---------------------------------------------------------------------------
// Verrou materiel pour proteger les acces partages ISR <-> loop.
// On utilise save_and_disable_interrupts / restore_interrupts : tres court,
// suffisant car l'alarme et la loop tournent sur le meme coeur.
// ---------------------------------------------------------------------------
// Sections critiques imbricables/repetables dans une meme fonction :
// chaque CRIT_ENTER ouvre un bloc { qui declare sa propre variable d'IRQ,
// CRIT_EXIT ferme ce bloc. Les deux doivent donc toujours aller par paire.
#define CRIT_ENTER() do { uint32_t __irq = save_and_disable_interrupts()
#define CRIT_EXIT()  restore_interrupts(__irq); } while (0)

volatile ModeRelais modeRelais = MODE_MONO;
volatile EtatMachine etat = ETAT_ARRET;
volatile EtatMachine etatAvantPause = ETAT_ARRET;

// Parametres de temps : ecrits par loop (commandes), lus par ISR.
volatile uint64_t onUs = 1000000ULL;
volatile uint64_t offUs = 1000000ULL;
volatile uint64_t pulseSetUs = 30000ULL;
volatile uint64_t pulseResetUs = 30000ULL;

volatile uint64_t cyclesDemandes = 0ULL;
volatile uint64_t cyclesEffectues = 0ULL;

volatile uint64_t nextDeadlineUs = 0ULL;
volatile uint64_t remainingPauseUs = 0ULL;

volatile bool running = false;
volatile bool paused = false;
volatile bool neutralPulseActive = false;
volatile bool neutralPulseDone = false;

// Sequence Neutral non bloquante (settle -> pulse -> retombee) pilotee
// par alarmes chainees au lieu d'un busy_wait de 20 ms qui gelait la serie,
// la lecture contacts et la prise en compte d'un STOP.
enum NeutralPhase : uint8_t {
  NEUTRAL_NONE = 0,
  NEUTRAL_SETTLE,   // attente collage relais selection avant le pulse
  NEUTRAL_PULSE_ON, // pulse en cours (sorties actives), pulses > 1000 us
  NEUTRAL_RELEASE   // attente retombee relais selection apres pulse en voie haute
};
volatile NeutralPhase neutralPhase = NEUTRAL_NONE;
volatile uint8_t neutralPattern = 0u;
volatile uint64_t neutralDureeUs = 0ULL;
volatile uint8_t neutralCodePulse = 3u;
volatile bool neutralUtilise32V = false;

volatile alarm_id_t currentAlarm = 0;

String ligneSerie = "";
String neutralLastType = "";
uint32_t dernierStatusMs = 0UL;

uint8_t contactReset1Cached = 0u;
uint8_t contactReset2Cached = 0u;
uint8_t contactReset3Cached = 0u;
uint8_t contactReset4Cached = 0u;
uint8_t contactLatch1Cached = 0u;
uint8_t contactLatch2Cached = 0u;
uint8_t contactLatch3Cached = 0u;
uint8_t contactLatch4Cached = 0u;
uint8_t contactsCachedBits = 0u;
uint8_t contactsLastSentBits = 255u;
bool contactsChangedPending = true;
uint64_t dernierSampleContactsUs = 0ULL;
uint64_t dernierEnvoiContactsUs = 0ULL;

volatile uint8_t sortiesCachedPattern = 0u;
uint8_t sortiesLastSentPattern = 255u;
volatile bool sortiesChangedPending = true;
uint64_t dernierEnvoiSortiesUs = 0ULL;

volatile bool pulseEventPending = false;
volatile uint8_t pulseEventPattern = 0u;
volatile uint8_t pulseEventCode = 0u;
volatile uint64_t pulseEventDurationUs = 0ULL;

volatile bool selection32Active = false;
bool selectionChangedPending = true;
uint64_t dernierEnvoiSelectionUs = 0ULL;

struct MeasureEvent {
  uint32_t tUs;
  uint8_t contactIndex;
  uint8_t state;
};

MeasureEvent measureEvents[MEASURE_MAX_EVENTS];


enum VoltageScanMode : uint8_t {
  VSCAN_NONE = 0,
  VSCAN_PICKUP,
  VSCAN_DROPOUT
};

bool ads1115Ok = false;
uint8_t adsFailureCount = 0u;
int16_t ads1115Raw = 0;
int32_t adsCoilMv = 0;
uint64_t adsDernierSampleUs = 0ULL;
uint64_t adsDernierEnvoiUs = 0ULL;
uint32_t voltageRatioU6 = VOLTAGE_RATIO_U6_DEFAULT;
int32_t voltageOffsetMv = VOLTAGE_OFFSET_MV_DEFAULT;
uint32_t voltageStableUs = VOLTAGE_STABLE_US_DEFAULT;

bool coilHoldActive = false;
uint8_t coilHoldPattern = 0u;
bool voltageScanActive = false;
VoltageScanMode voltageScanMode = VSCAN_NONE;
uint8_t voltageScanNbInv = 0;
uint64_t voltageScanStartUs = 0ULL;
// Capture tension : le premier passage dans l'état cible est mémorisé une seule fois.
// Les rebonds ultérieurs ne remplacent jamais cette valeur. La stabilité demandée
// sert uniquement à confirmer que le transfert s'est réellement terminé.
uint64_t voltageCandidateStartUs[5] = {0,0,0,0,0}; // instant du premier passage
uint64_t voltageStableStartUs[5] = {0,0,0,0,0};    // début de la période stable courante
int32_t voltageCandidateMv[5] = {-1,-1,-1,-1,-1};
int16_t voltageCandidateRaw[5] = {-1,-1,-1,-1,-1};
bool voltageCandidateActive[5] = {false,false,false,false,false}; // premier passage déjà capturé
int32_t voltageResultMv[5] = {-1,-1,-1,-1,-1}; // 0..3 inverseurs, 4 global
int16_t voltageResultRaw[5] = {-1,-1,-1,-1,-1};
uint64_t voltageResultTimeUs[5] = {0,0,0,0,0}; // instant du premier passage, avant rebonds
bool voltageResultDone[5] = {false,false,false,false,false};

// --- Helpers atomiques pour uint64_t partages ---------------------------------
static inline uint64_t atomicLoad64(volatile uint64_t *p) {
  uint64_t v;
  CRIT_ENTER();
  v = *p;
  CRIT_EXIT();
  return v;
}

static inline void atomicStore64(volatile uint64_t *p, uint64_t v) {
  CRIT_ENTER();
  *p = v;
  CRIT_EXIT();
}

// ---------------------------------------------------------------------------
static inline void appliquerSelection32(bool active) {
  if (selection32Active != active) {
    selection32Active = active;
    selectionChangedPending = true;
  }
  gpio_put(PIN_SELECT_32V, active ? 1 : 0);
}

void preparerSelectionTensionNeutral(bool utiliser32V) {
  // On applique seulement la selection ici. Le delai d'etablissement
  // (collage relais) n'est PLUS un busy_wait bloquant : il est gere par la
  // sequence d'alarmes (phase NEUTRAL_SETTLE) pour ne pas geler serie/contacts.
  appliquerSelection32(utiliser32V);
}

static inline void appliquerSorties(uint8_t pattern) {
  uint8_t patternSorties = pattern & 0x03u;

  if (patternSorties != sortiesCachedPattern) {
    sortiesCachedPattern = patternSorties;
    sortiesChangedPending = true;
  }

  uint32_t setMask = 0;
  if (pattern & 0x01) setMask |= MASK_SORTIE_1;
  if (pattern & 0x02) setMask |= MASK_SORTIE_2;
  if (pattern & 0x04) setMask |= MASK_LED;

  gpio_put_masked(MASK_ALL, setMask);
}

void noterEvenementPulse(uint8_t patternSorties, uint64_t dureeUs, uint8_t codePulse) {
  // Appelable depuis ISR ou loop : on ecrit le bloc d'un coup.
  pulseEventPattern = patternSorties & 0x03u;
  pulseEventDurationUs = dureeUs;
  pulseEventCode = codePulse;
  pulseEventPending = true;
}

// dureeEtat lit des uint64 partages : appele depuis ISR (irq deja off) et loop.
// On ne reprotege pas dans l'ISR (deja atomique), mais l'appel loop passe par
// des wrappers atomiques quand necessaire.
uint64_t dureeEtatRaw(EtatMachine e) {
  switch (e) {
    case ETAT_MONO_ON:       return onUs;
    case ETAT_MONO_OFF:      return offUs;
    case ETAT_BI_PULSE_SET:  return pulseSetUs;
    case ETAT_BI_WAIT_ON:    return onUs;
    case ETAT_BI_PULSE_RESET:return pulseResetUs;
    case ETAT_BI_WAIT_OFF:   return offUs;
    default:                 return 0ULL;
  }
}

void appliquerSortieEtat(EtatMachine e) {
  switch (e) {
    case ETAT_MONO_ON:
      appliquerSorties(0x01 | 0x04);
      ledRgbModeMachinePending = LED_MODE_PULSE_BE;
      break;
    case ETAT_MONO_OFF:
      appliquerSorties(0x00);
      ledRgbModeMachinePending = LED_MODE_CONNECTED;
      break;
    case ETAT_BI_PULSE_SET:
      appliquerSorties(0x01 | 0x04);
      ledRgbModeMachinePending = LED_MODE_PULSE_BE;
      noterEvenementPulse(0x01, pulseSetUs, 1u);
      break;
    case ETAT_BI_WAIT_ON:
      appliquerSorties(0x04);
      ledRgbModeMachinePending = LED_MODE_CONNECTED;
      break;
    case ETAT_BI_PULSE_RESET:
      appliquerSorties(0x02 | 0x04);
      ledRgbModeMachinePending = LED_MODE_PULSE_BR;
      noterEvenementPulse(0x02, pulseResetUs, 2u);
      break;
    case ETAT_BI_WAIT_OFF:
      appliquerSorties(0x00);
      ledRgbModeMachinePending = LED_MODE_CONNECTED;
      break;
    default:
      appliquerSorties(0x00);
      break;
  }
}

bool cyclesTermines() {
  if (cyclesDemandes == 0ULL) return false;
  return cyclesEffectues >= cyclesDemandes;
}

EtatMachine prochainEtatApresFinPhase() {
  switch (etat) {
    case ETAT_MONO_ON:
      return ETAT_MONO_OFF;
    case ETAT_MONO_OFF:
      cyclesEffectues++;
      if (cyclesTermines()) return ETAT_ARRET;
      return ETAT_MONO_ON;
    case ETAT_BI_PULSE_SET:
      return ETAT_BI_WAIT_ON;
    case ETAT_BI_WAIT_ON:
      return ETAT_BI_PULSE_RESET;
    case ETAT_BI_PULSE_RESET:
      return ETAT_BI_WAIT_OFF;
    case ETAT_BI_WAIT_OFF:
      cyclesEffectues++;
      if (cyclesTermines()) return ETAT_ARRET;
      return ETAT_BI_PULSE_SET;
    default:
      return ETAT_ARRET;
  }
}

// ISR d'alarme : interruptions deja desactivees dans ce contexte.
int64_t timingAlarmCallback(alarm_id_t id, void *user_data) {
  (void)id;
  (void)user_data;

  if (!running || paused || neutralPulseActive || etat == ETAT_ARRET || etat == ETAT_PAUSE) {
    appliquerSorties(0x00);
    currentAlarm = 0;
    return 0;
  }

  EtatMachine prochain = prochainEtatApresFinPhase();

  if (prochain == ETAT_ARRET) {
    etat = ETAT_ARRET;
    running = false;
    paused = false;
    appliquerSorties(0x00);
    ledRgbModeMachinePending = LED_MODE_CYCLE_DONE;
    currentAlarm = 0;
    return 0;
  }

  etat = prochain;
  appliquerSortieEtat(etat);

  uint64_t d = dureeEtatRaw(etat);
  if (d < MIN_US) d = MIN_US;

  nextDeadlineUs += d;

  uint64_t maintenant = time_us_64();

  if (nextDeadlineUs <= maintenant) {
    nextDeadlineUs = maintenant + MIN_US;
    return 1;
  }

  uint64_t diff = nextDeadlineUs - maintenant;
  if (diff > 0x7FFFFFFFFFFFFFFFULL) diff = 0x7FFFFFFFFFFFFFFFULL;
  return (int64_t)diff;
}

// --- Sequence Neutral non bloquante : callbacks chaines -----------------------
// Declarations anticipees.
int64_t neutralSettleCallback(alarm_id_t id, void *user_data);
int64_t neutralPulseEndCallback(alarm_id_t id, void *user_data);
int64_t neutralReleaseCallback(alarm_id_t id, void *user_data);

// Fin propre de la sequence neutral : sorties OFF, selection basse, etat ARRET.
void terminerSequenceNeutral() {
  appliquerSorties(0x00);
  appliquerSelection32(false);  // retour securise tension basse / NC
  neutralPhase = NEUTRAL_NONE;
  neutralPulseActive = false;
  neutralPulseDone = true;
  etat = ETAT_ARRET;
  running = false;
  paused = false;
  currentAlarm = 0;
}

// Drapeau : pulse courte prete a etre executee en section critique cote loop.
volatile bool neutralPulseCourtePending = false;

// Fin du settle : on lance reellement le pulse. Pour une pulse longue, on arme
// l'alarme de fin. Pour une pulse courte (<= 1000 us), on delegue a la loop
// l'execution en section critique (jitter minimal) : on ne fait pas de busy_wait
// long dans ce contexte d'alarme. Contexte ISR (irq deja off).
int64_t neutralSettleCallback(alarm_id_t id, void *user_data) {
  (void)id; (void)user_data;
  currentAlarm = 0;

  if (neutralPhase != NEUTRAL_SETTLE) {
    return 0;
  }

  neutralPhase = NEUTRAL_PULSE_ON;

  if (neutralDureeUs <= NEUTRAL_DIRECT_MAX_US) {
    // Pulse courte : la loop l'execute en section critique tres bientot.
    neutralPulseCourtePending = true;
    return 0;
  }

  // Pulse longue : sorties actives + alarme de fin.
  appliquerSorties(neutralPattern | 0x04);
  noterEvenementPulse(neutralPattern, neutralDureeUs, neutralCodePulse);

  uint64_t d = neutralDureeUs;
  if (d < MIN_US) d = MIN_US;
  currentAlarm = add_alarm_in_us(d, neutralPulseEndCallback, NULL, true);
  return 0;
}

// Fin du pulse : sorties OFF. Si on etait en voie haute, on attend la retombee
// du relais avant de rendre la main ; sinon on termine directement.
int64_t neutralPulseEndCallback(alarm_id_t id, void *user_data) {
  (void)id; (void)user_data;
  currentAlarm = 0;

  if (neutralPhase != NEUTRAL_PULSE_ON) {
    return 0;
  }

  appliquerSorties(0x00);

  if (neutralUtilise32V) {
    // Repasser en voie basse et laisser le relais retomber avant fin.
    appliquerSelection32(false);
    neutralPhase = NEUTRAL_RELEASE;
    currentAlarm = add_alarm_in_us(NEUTRAL_RELEASE_SETTLE_US, neutralReleaseCallback, NULL, true);
    return 0;
  }

  terminerSequenceNeutral();
  return 0;
}

int64_t neutralReleaseCallback(alarm_id_t id, void *user_data) {
  (void)id; (void)user_data;
  currentAlarm = 0;
  if (neutralPhase != NEUTRAL_RELEASE) {
    return 0;
  }
  terminerSequenceNeutral();
  return 0;
}

// Annulation atomique : on capture l'id et on le remet a 0 sous IRQ off,
// puis on annule hors section critique (cancel_alarm peut etre un peu long).
void cancelCurrentAlarm() {
  alarm_id_t a;
  CRIT_ENTER();
  a = currentAlarm;
  currentAlarm = 0;
  CRIT_EXIT();
  if (a > 0) {
    cancel_alarm(a);
  }
}

void planifierEtatCourant(uint64_t dureeUs) {
  if (dureeUs < MIN_US) dureeUs = MIN_US;
  alarm_id_t a = add_alarm_in_us(dureeUs, timingAlarmCallback, NULL, true);
  CRIT_ENTER();
  nextDeadlineUs = time_us_64() + dureeUs;
  currentAlarm = a;
  CRIT_EXIT();
}

void demarrerEssai() {
  cancelCurrentAlarm();

  CRIT_ENTER();
  neutralPulseActive = false;
  neutralPulseDone = false;
  cyclesEffectues = 0ULL;
  remainingPauseUs = 0ULL;
  paused = false;
  running = true;
  if (modeRelais == MODE_MONO) etat = ETAT_MONO_ON;
  else etat = ETAT_BI_PULSE_SET;
  CRIT_EXIT();

  appliquerSortieEtat(etat);
  planifierEtatCourant(dureeEtatRaw(etat));
}

void stopEssai() {
  cancelCurrentAlarm();

  CRIT_ENTER();
  running = false;
  paused = false;
  neutralPulseActive = false;
  neutralPulseDone = false;
  neutralPhase = NEUTRAL_NONE;          // annule toute sequence neutral en cours
  neutralPulseCourtePending = false;
  etat = ETAT_ARRET;
  etatAvantPause = ETAT_ARRET;
  remainingPauseUs = 0ULL;
  CRIT_EXIT();

  voltageScanActive = false;
  voltageScanMode = VSCAN_NONE;
  coilHoldActive = false;
  coilHoldPattern = 0u;
  appliquerSorties(0x00);
  appliquerSelection32(false);  // tension basse par defaut
}

void pauseEssai() {
  if (!running || paused || neutralPulseActive || etat == ETAT_ARRET) return;

  uint64_t maintenant = time_us_64();
  uint64_t deadline = atomicLoad64(&nextDeadlineUs);
  uint64_t reste = (deadline <= maintenant) ? MIN_US : (deadline - maintenant);

  cancelCurrentAlarm();

  CRIT_ENTER();
  remainingPauseUs = reste;
  etatAvantPause = etat;
  etat = ETAT_PAUSE;
  paused = true;
  CRIT_EXIT();

  appliquerSorties(0x00);
}

void reprendreEssai() {
  if (!running || !paused || neutralPulseActive || etat != ETAT_PAUSE) return;

  uint64_t reste = atomicLoad64(&remainingPauseUs);
  if (reste < MIN_US) reste = MIN_US;

  CRIT_ENTER();
  paused = false;
  etat = etatAvantPause;
  CRIT_EXIT();

  appliquerSortieEtat(etat);
  planifierEtatCourant(reste);
}

// Pulse courte (<= 1000 us) : exécutée en section critique pour le jitter, mais
// SEULEMENT apres le settle. Appelee depuis la loop quand la phase settle est finie.
void executerPulseCourteEnSectionCritique() {
  noterEvenementPulse(neutralPattern, neutralDureeUs, neutralCodePulse);

  noInterrupts();
  appliquerSorties(neutralPattern | 0x04);
  busy_wait_us_32((uint32_t)neutralDureeUs);
  appliquerSorties(0x00);
  interrupts();

  if (neutralUtilise32V) {
    appliquerSelection32(false);
    neutralPhase = NEUTRAL_RELEASE;
    alarm_id_t a = add_alarm_in_us(NEUTRAL_RELEASE_SETTLE_US, neutralReleaseCallback, NULL, true);
    CRIT_ENTER();
    currentAlarm = a;
    CRIT_EXIT();
  } else {
    terminerSequenceNeutral();
    // neutralPulseDone declenchera l'envoi STATUS dans la loop.
  }
}

void demarrerPulseNeutral(uint8_t pattern, uint64_t dureeUs, const String &typePulse, bool utiliser32V) {
  if (dureeUs < MIN_US) dureeUs = MIN_US;

  cancelCurrentAlarm();

  uint8_t codePulse = 3u;
  if (typePulse == "BR") codePulse = 4u;
  else if (typePulse == "BEBR") codePulse = 5u;

  CRIT_ENTER();
  running = false;
  paused = false;
  neutralPulseDone = false;
  neutralPulseActive = true;
  etat = ETAT_NEUTRAL_PULSE;
  neutralPattern = pattern;
  neutralDureeUs = dureeUs;
  neutralCodePulse = codePulse;
  neutralUtilise32V = utiliser32V;
  neutralPhase = NEUTRAL_SETTLE;
  CRIT_EXIT();
  neutralLastType = typePulse;

  // Applique la selection tension immediatement ; le delai d'etablissement
  // (collage relais) est gere par l'alarme de settle, sans bloquer la loop.
  appliquerSelection32(utiliser32V);

  alarm_id_t a = add_alarm_in_us(NEUTRAL_SELECTION_SETTLE_US, neutralSettleCallback, NULL, true);
  CRIT_ENTER();
  currentAlarm = a;
  CRIT_EXIT();
}

const char *modeTexte() {
  return (modeRelais == MODE_MONO) ? "MONO" : "BISTABLE";
}

const char *etatTexte() {
  switch (etat) {
    case ETAT_ARRET:          return "ARRET";
    case ETAT_MONO_ON:        return "MONO_ON";
    case ETAT_MONO_OFF:       return "MONO_OFF";
    case ETAT_BI_PULSE_SET:   return "BI_PULSE_SET";
    case ETAT_BI_WAIT_ON:     return "BI_WAIT_ON";
    case ETAT_BI_PULSE_RESET: return "BI_PULSE_RESET";
    case ETAT_BI_WAIT_OFF:    return "BI_WAIT_OFF";
    case ETAT_PAUSE:          return "PAUSE";
    case ETAT_NEUTRAL_PULSE:  return "NEUTRAL_PULSE";
    default:                  return "INCONNU";
  }
}

void printUint64(uint64_t value) {
  char temp[24];
  uint8_t index = 0;
  if (value == 0ULL) { Serial.print('0'); return; }
  while (value > 0ULL && index < sizeof(temp)) {
    temp[index++] = (char)('0' + (value % 10ULL));
    value /= 10ULL;
  }
  while (index > 0) Serial.print(temp[--index]);
}

uint8_t composerBitsContactsDepuisGpio() {
  uint32_t g = gpio_get_all();

  uint8_t r1 = (g & (1u << PIN_CONTACT_RESET_1)) ? 0u : 1u;
  uint8_t r2 = (g & (1u << PIN_CONTACT_RESET_2)) ? 0u : 1u;
  uint8_t r3 = (g & (1u << PIN_CONTACT_RESET_3)) ? 0u : 1u;
  uint8_t r4 = (g & (1u << PIN_CONTACT_RESET_4)) ? 0u : 1u;

  uint8_t l1 = (g & (1u << PIN_CONTACT_LATCH_1)) ? 0u : 1u;
  uint8_t l2 = (g & (1u << PIN_CONTACT_LATCH_2)) ? 0u : 1u;
  uint8_t l3 = (g & (1u << PIN_CONTACT_LATCH_3)) ? 0u : 1u;
  uint8_t l4 = (g & (1u << PIN_CONTACT_LATCH_4)) ? 0u : 1u;

  return (uint8_t)(
    (r1 << 0) | (r2 << 1) | (r3 << 2) | (r4 << 3) |
    (l1 << 4) | (l2 << 5) | (l3 << 6) | (l4 << 7)
  );
}

void appliquerBitsContacts(uint8_t bits) {
  contactReset1Cached = (bits >> 0) & 0x01u;
  contactReset2Cached = (bits >> 1) & 0x01u;
  contactReset3Cached = (bits >> 2) & 0x01u;
  contactReset4Cached = (bits >> 3) & 0x01u;

  contactLatch1Cached = (bits >> 4) & 0x01u;
  contactLatch2Cached = (bits >> 5) & 0x01u;
  contactLatch3Cached = (bits >> 6) & 0x01u;
  contactLatch4Cached = (bits >> 7) & 0x01u;

  contactsCachedBits = bits;
}

void mettreAJourContactsRapide() {
  uint64_t maintenant = time_us_64();
  if ((maintenant - dernierSampleContactsUs) < CONTACT_SAMPLE_PERIOD_US) return;
  dernierSampleContactsUs = maintenant;

  uint8_t bits = composerBitsContactsDepuisGpio();
  if (bits != contactsCachedBits) {
    appliquerBitsContacts(bits);
    contactsChangedPending = true;
  }
}

void envoyerContacts(const char *raison) {
  Serial.print("CONTACT;");
  Serial.print(raison);
  Serial.print(";IN_RESET1="); Serial.print(contactReset1Cached);
  Serial.print(";IN_RESET2="); Serial.print(contactReset2Cached);
  Serial.print(";IN_RESET3="); Serial.print(contactReset3Cached);
  Serial.print(";IN_RESET4="); Serial.print(contactReset4Cached);
  Serial.print(";IN_LATCH1="); Serial.print(contactLatch1Cached);
  Serial.print(";IN_LATCH2="); Serial.print(contactLatch2Cached);
  Serial.print(";IN_LATCH3="); Serial.print(contactLatch3Cached);
  Serial.print(";IN_LATCH4="); Serial.print(contactLatch4Cached);
  Serial.println();
  contactsLastSentBits = contactsCachedBits;
  contactsChangedPending = false;
  dernierEnvoiContactsUs = time_us_64();
}

void gererEnvoiContacts() {
  uint64_t maintenant = time_us_64();
  bool delaiChangementOk = (maintenant - dernierEnvoiContactsUs) >= CONTACT_CHANGE_MIN_SEND_US;
  bool delaiHeartbeatOk = (maintenant - dernierEnvoiContactsUs) >= CONTACT_HEARTBEAT_PERIOD_US;

  if (contactsChangedPending && delaiChangementOk) { envoyerContacts("CHANGE"); return; }
  if (delaiHeartbeatOk) envoyerContacts("AUTO");
}

const char *pulseCodeTexte(uint8_t codePulse) {
  switch (codePulse) {
    case 1u: return "SET";
    case 2u: return "RESET";
    case 3u: return "BE";
    case 4u: return "BR";
    case 5u: return "BEBR";
    default: return "?";
  }
}

void envoyerSorties(const char *raison, uint8_t patternSorties) {
  Serial.print("OUT;");
  Serial.print(raison);
  Serial.print(";OUT1="); Serial.print((patternSorties & 0x01u) ? 1 : 0);
  Serial.print(";OUT2="); Serial.print((patternSorties & 0x02u) ? 1 : 0);
  Serial.println();
  sortiesLastSentPattern = patternSorties;
  sortiesChangedPending = false;
  dernierEnvoiSortiesUs = time_us_64();
}

void envoyerEvenementPulse(uint8_t patternSorties, uint8_t codePulse, uint64_t dureeUs) {
  Serial.print("OUT;PULSE;PULSE=");
  Serial.print(pulseCodeTexte(codePulse));
  Serial.print(";OUT1="); Serial.print((patternSorties & 0x01u) ? 1 : 0);
  Serial.print(";OUT2="); Serial.print((patternSorties & 0x02u) ? 1 : 0);
  Serial.print(";DUREE_US="); printUint64(dureeUs);
  Serial.println();
}

void gererEnvoiSortiesRapide() {
  bool pulsePendingLocal = false;
  uint8_t pulsePatternLocal = 0u, pulseCodeLocal = 0u;
  uint64_t pulseDureeLocal = 0ULL;

  // Snapshot atomique de l'evenement pulse.
  CRIT_ENTER();
  if (pulseEventPending) {
    pulsePendingLocal = true;
    pulsePatternLocal = pulseEventPattern;
    pulseCodeLocal = pulseEventCode;
    pulseDureeLocal = pulseEventDurationUs;
    pulseEventPending = false;
  }
  CRIT_EXIT();

  if (pulsePendingLocal) {
    envoyerEvenementPulse(pulsePatternLocal, pulseCodeLocal, pulseDureeLocal);
  }

  uint64_t maintenant = time_us_64();
  uint8_t sortiesActuelles = sortiesCachedPattern;

  if (sortiesChangedPending && sortiesActuelles != sortiesLastSentPattern &&
      (maintenant - dernierEnvoiSortiesUs) >= SORTIE_CHANGE_MIN_SEND_US) {
    envoyerSorties("CHANGE", sortiesActuelles);
  }
}

const char *tensionSelectionTexte() {
  return selection32Active ? "HIGH" : "LOW";
}

void envoyerSelectionTension(const char *raison) {
  Serial.print("VSEL;");
  Serial.print(raison);
  Serial.print(";SEL32=");
  Serial.print(selection32Active ? 1 : 0);
  Serial.print(";VSEL=");
  Serial.print(tensionSelectionTexte());
  Serial.println();

  selectionChangedPending = false;
  dernierEnvoiSelectionUs = time_us_64();
}

void gererEnvoiSelectionTension() {
  if (selectionChangedPending) {
    envoyerSelectionTension("CHANGE");
  }
}

void envoyerStatus(const char *raison) {
  // Image coherente unique : on lit le pattern cache (reflet de la derniere
  // ecriture GPIO) plutot que de melanger gpio_get direct et cache.
  uint8_t pat = sortiesCachedPattern & 0x03u;
  uint64_t lOn = atomicLoad64(&onUs);
  uint64_t lOff = atomicLoad64(&offUs);
  uint64_t lSet = atomicLoad64(&pulseSetUs);
  uint64_t lReset = atomicLoad64(&pulseResetUs);
  uint64_t lEff = atomicLoad64(&cyclesEffectues);
  uint64_t lDem = atomicLoad64(&cyclesDemandes);

  Serial.print("STATUS;");
  Serial.print(raison);
  Serial.print(";MODE="); Serial.print(modeTexte());
  Serial.print(";ETAT="); Serial.print(etatTexte());
  Serial.print(";CYCLE="); printUint64(lEff);
  Serial.print("/");
  if (lDem == 0ULL) Serial.print("INF"); else printUint64(lDem);
  Serial.print(";OUT1="); Serial.print((pat & 0x01u) ? 1 : 0);
  Serial.print(";OUT2="); Serial.print((pat & 0x02u) ? 1 : 0);
  Serial.print(";SEL32="); Serial.print(selection32Active ? 1 : 0);
  Serial.print(";VSEL="); Serial.print(tensionSelectionTexte());
  Serial.print(";IN_RESET1="); Serial.print(contactReset1Cached);
  Serial.print(";IN_RESET2="); Serial.print(contactReset2Cached);
  Serial.print(";IN_RESET3="); Serial.print(contactReset3Cached);
  Serial.print(";IN_RESET4="); Serial.print(contactReset4Cached);
  Serial.print(";IN_LATCH1="); Serial.print(contactLatch1Cached);
  Serial.print(";IN_LATCH2="); Serial.print(contactLatch2Cached);
  Serial.print(";IN_LATCH3="); Serial.print(contactLatch3Cached);
  Serial.print(";IN_LATCH4="); Serial.print(contactLatch4Cached);
  Serial.print(";ON_US="); printUint64(lOn);
  Serial.print(";OFF_US="); printUint64(lOff);
  Serial.print(";SET_US="); printUint64(lSet);
  Serial.print(";RESET_US="); printUint64(lReset);
  if (neutralLastType.length() > 0) {
    Serial.print(";NEUTRAL="); Serial.print(neutralLastType);
  }
  Serial.println();
}

String getToken(const String &data, char separator, int index) {
  int found = 0, start = 0, longueur = (int)data.length();
  for (int i = 0; i <= longueur; i++) {
    if (i == longueur || data.charAt(i) == separator) {
      if (found == index) return data.substring(start, i);
      found++;
      start = i + 1;
    }
  }
  return "";
}

bool parseUint64(const String &texteOriginal, uint64_t &valeur) {
  String texte = texteOriginal;
  texte.trim();
  if (texte.length() == 0) return false;

  uint64_t resultat = 0ULL;
  for (uint16_t i = 0; i < texte.length(); i++) {
    char c = texte.charAt(i);
    if (!isDigit(c)) return false;
    uint8_t digit = (uint8_t)(c - '0');
    if (resultat > (0xFFFFFFFFFFFFFFFFULL - digit) / 10ULL) return false;
    resultat = (resultat * 10ULL) + digit;
  }
  valeur = resultat;
  return true;
}

bool validerDureeUs(uint64_t valeur) {
  return valeur >= MIN_US && valeur <= MAX_US;
}

void traiterStartUs(const String &cmd) {
  String modeTxt = getToken(cmd, ';', 1);
  String onTxt = getToken(cmd, ';', 2);
  String offTxt = getToken(cmd, ';', 3);
  String setTxt = getToken(cmd, ';', 4);
  String resetTxt = getToken(cmd, ';', 5);
  String cyclesTxt = getToken(cmd, ';', 6);

  modeTxt.trim(); modeTxt.toUpperCase();

  uint64_t tmpOnUs=0, tmpOffUs=0, tmpSetUs=0, tmpResetUs=0, tmpCycles=0;
  ModeRelais tmpMode;

  if (modeTxt == "MONO" || modeTxt == "MONOSTABLE") tmpMode = MODE_MONO;
  else if (modeTxt == "BISTABLE") tmpMode = MODE_BISTABLE;
  else { Serial.println("ERREUR;MODE_INVALIDE"); return; }

  if (!parseUint64(onTxt, tmpOnUs))       { Serial.println("ERREUR;ON_US_INVALIDE"); return; }
  if (!parseUint64(offTxt, tmpOffUs))     { Serial.println("ERREUR;OFF_US_INVALIDE"); return; }
  if (!parseUint64(setTxt, tmpSetUs))     { Serial.println("ERREUR;SET_US_INVALIDE"); return; }
  if (!parseUint64(resetTxt, tmpResetUs)) { Serial.println("ERREUR;RESET_US_INVALIDE"); return; }
  if (!parseUint64(cyclesTxt, tmpCycles)) { Serial.println("ERREUR;CYCLES_INVALIDE"); return; }

  if (!validerDureeUs(tmpOnUs))    { Serial.println("ERREUR;ON_US_HORS_LIMITE"); return; }
  if (!validerDureeUs(tmpOffUs))   { Serial.println("ERREUR;OFF_US_HORS_LIMITE"); return; }
  if (!validerDureeUs(tmpSetUs))   { Serial.println("ERREUR;SET_US_HORS_LIMITE"); return; }
  if (!validerDureeUs(tmpResetUs)) { Serial.println("ERREUR;RESET_US_HORS_LIMITE"); return; }

  stopEssai();

  CRIT_ENTER();
  modeRelais = tmpMode;
  onUs = tmpOnUs;
  offUs = tmpOffUs;
  pulseSetUs = tmpSetUs;
  pulseResetUs = tmpResetUs;
  cyclesDemandes = tmpCycles;
  CRIT_EXIT();

  demarrerEssai();
  envoyerStatus("START");
}

const char *measureContactName(uint8_t index) {
  switch (index) {
    case 0: return "R1";
    case 1: return "R2";
    case 2: return "R3";
    case 3: return "R4";
    case 4: return "T1";
    case 5: return "T2";
    case 6: return "T3";
    case 7: return "T4";
    default: return "?";
  }
}

void envoyerMeasureBegin(const String &action, uint64_t captureUs, uint64_t pulseUs, uint8_t nbInv, uint8_t startBits) {
  Serial.print("MEASURE;BEGIN;ACTION=");
  Serial.print(action);
  Serial.print(";CAPTURE_US="); printUint64(captureUs);
  Serial.print(";PULSE_US="); printUint64(pulseUs);
  Serial.print(";NB_INV="); Serial.print(nbInv);
  Serial.print(";START_BITS="); Serial.print(startBits);
  Serial.println();
}

void envoyerMeasureEnd(const String &action, uint64_t captureUs, uint64_t pulseUs, uint8_t nbInv, uint8_t startBits, uint8_t endBits, uint16_t eventCount, bool overflow, uint32_t loopMaxUs, uint32_t droppedEvents) {
  Serial.print("MEASURE;END;ACTION=");
  Serial.print(action);
  Serial.print(";CAPTURE_US="); printUint64(captureUs);
  Serial.print(";PULSE_US="); printUint64(pulseUs);
  Serial.print(";NB_INV="); Serial.print(nbInv);
  Serial.print(";START_BITS="); Serial.print(startBits);
  Serial.print(";END_BITS="); Serial.print(endBits);
  Serial.print(";EVENTS="); Serial.print(eventCount);
  Serial.print(";EVENT_CAPACITY="); Serial.print(MEASURE_MAX_EVENTS);
  Serial.print(";OVERFLOW="); Serial.print(overflow ? 1 : 0);
  Serial.print(";DROPPED_EVENTS="); Serial.print(droppedEvents);
  Serial.print(";LOOP_MAX_US="); Serial.print(loopMaxUs);
  Serial.println();
}

void envoyerMeasureEvents(uint16_t eventCount) {
  for (uint16_t i = 0; i < eventCount; i++) {
    Serial.print("MEASURE_EVT;I=");
    Serial.print(i);
    Serial.print(";T_US=");
    Serial.print(measureEvents[i].tUs);
    Serial.print(";CONTACT=");
    Serial.print(measureContactName(measureEvents[i].contactIndex));
    Serial.print(";STATE=");
    Serial.print(measureEvents[i].state);
    Serial.println();
  }
}

void traiterMeasureContacts(const String &cmd) {
  String actionTxt = getToken(cmd, ';', 1);
  String captureTxt = getToken(cmd, ';', 2);
  String pulseTxt = getToken(cmd, ';', 3);
  String nbInvTxt = getToken(cmd, ';', 4);
  String sourceTxt = getToken(cmd, ';', 5);
  actionTxt.trim(); actionTxt.toUpperCase();
  sourceTxt.trim(); sourceTxt.toUpperCase();
  bool sourceEA = (sourceTxt == "EA");

  uint64_t captureUs = 0ULL;
  uint64_t pulseUs = 0ULL;
  uint64_t nbInv64 = 0ULL;

  if (actionTxt != "BE" && actionTxt != "BR") {
    Serial.println("MEASURE;ERROR;REASON=ACTION_INVALIDE");
    return;
  }
  if (!parseUint64(captureTxt, captureUs) ||
      captureUs < MEASURE_CAPTURE_MIN_US ||
      captureUs > MEASURE_CAPTURE_MAX_US) {
    Serial.println("MEASURE;ERROR;REASON=CAPTURE_US_INVALIDE");
    return;
  }
  if (!parseUint64(pulseTxt, pulseUs) || !validerDureeUs(pulseUs) || pulseUs > captureUs) {
    Serial.println("MEASURE;ERROR;REASON=PULSE_US_INVALIDE");
    return;
  }
  if (!parseUint64(nbInvTxt, nbInv64) || nbInv64 < 1ULL || nbInv64 > 4ULL) {
    Serial.println("MEASURE;ERROR;REASON=NB_INV_INVALIDE");
    return;
  }
  if (running || neutralPulseActive || etat != ETAT_ARRET) {
    Serial.println("MEASURE;ERROR;REASON=RP2040_OCCUPE");
    return;
  }

  uint8_t nbInv = (uint8_t)nbInv64;
  uint8_t pattern = (actionTxt == "BE") ? 0x01u : 0x02u;
  uint8_t startBits = composerBitsContactsDepuisGpio();
  uint8_t previousBits = startBits;
  uint16_t eventCount = 0;
  bool overflow = false;
  bool pulseOffDone = false;
  uint32_t loopMaxUs = 0u;
  uint32_t droppedEvents = 0u;

  envoyerMeasureBegin(actionTxt, captureUs, pulseUs, nbInv, startBits);
  Serial.flush();

  // En mode historique, GP26 selectionne la voie fixe haute avant t0.
  // En mode EA, la tension est fournie par l'alimentation pilotee par le PC :
  // GP26 reste inactif et aucun temps de collage du relais 28/32 V n'est ajoute.
  if (sourceEA) {
    appliquerSelection32(false);
  } else {
    appliquerSelection32(true);
    delayMicroseconds((uint32_t)NEUTRAL_SELECTION_SETTLE_US);
  }

  noInterrupts();
  appliquerSorties(pattern | 0x04u);
  uint64_t t0 = time_us_64();
  uint64_t endAt = t0 + captureUs;
  uint64_t pulseOffAt = t0 + pulseUs;
  uint64_t lastSampleUs = t0;

  while (time_us_64() < endAt) {
    uint64_t checkNow = time_us_64();
    if (!pulseOffDone && checkNow >= pulseOffAt) {
      appliquerSorties(0x00u);
      pulseOffDone = true;
    }

    uint8_t bits = composerBitsContactsDepuisGpio();
    uint64_t now = time_us_64();
    uint32_t loopDeltaUs = (uint32_t)(now - lastSampleUs);
    if (loopDeltaUs > loopMaxUs) loopMaxUs = loopDeltaUs;
    lastSampleUs = now;
    uint8_t changed = bits ^ previousBits;
    if (changed != 0u) {
      uint32_t tRel = (uint32_t)(now - t0);
      for (uint8_t i = 0; i < 8; i++) {
        if (changed & (1u << i)) {
          if (eventCount < MEASURE_MAX_EVENTS) {
            measureEvents[eventCount].tUs = tRel;
            measureEvents[eventCount].contactIndex = i;
            measureEvents[eventCount].state = (bits >> i) & 0x01u;
            eventCount++;
          } else {
            overflow = true;
            droppedEvents++;
          }
        }
      }
      previousBits = bits;
    }
  }
  appliquerSorties(0x00u);
  interrupts();

  if (!sourceEA) appliquerSelection32(false);
  appliquerBitsContacts(composerBitsContactsDepuisGpio());
  contactsChangedPending = true;
  sortiesChangedPending = true;
  selectionChangedPending = true;

  envoyerMeasureEvents(eventCount);
  envoyerMeasureEnd(actionTxt, captureUs, pulseUs, nbInv, startBits, contactsCachedBits, eventCount, overflow, loopMaxUs, droppedEvents);
  envoyerStatus("MEASURE_DONE");
}

void traiterMeasureMono(const String &cmd) {
  String actionTxt = getToken(cmd, ';', 1);
  String captureTxt = getToken(cmd, ';', 2);
  String holdTxt = getToken(cmd, ';', 3);
  String nbInvTxt = getToken(cmd, ';', 4);
  String sourceTxt = getToken(cmd, ';', 5);
  actionTxt.trim(); actionTxt.toUpperCase();
  sourceTxt.trim(); sourceTxt.toUpperCase();
  bool sourceEA = (sourceTxt == "EA");

  uint64_t captureUs = 0ULL;
  uint64_t holdUs = 0ULL;
  uint64_t nbInv64 = 0ULL;

  if (actionTxt != "ON" && actionTxt != "OFF") {
    Serial.println("MEASURE;ERROR;REASON=MONO_ACTION_INVALIDE");
    return;
  }
  if (!parseUint64(captureTxt, captureUs) ||
      captureUs < MEASURE_CAPTURE_MIN_US ||
      captureUs > MEASURE_CAPTURE_MAX_US) {
    Serial.println("MEASURE;ERROR;REASON=CAPTURE_US_INVALIDE");
    return;
  }
  if (!parseUint64(holdTxt, holdUs) || holdUs < 1000ULL || holdUs > 5000000ULL) {
    Serial.println("MEASURE;ERROR;REASON=HOLD_US_INVALIDE");
    return;
  }
  if (!parseUint64(nbInvTxt, nbInv64) || nbInv64 < 1ULL || nbInv64 > 4ULL) {
    Serial.println("MEASURE;ERROR;REASON=NB_INV_INVALIDE");
    return;
  }
  if (running || neutralPulseActive || etat != ETAT_ARRET) {
    Serial.println("MEASURE;ERROR;REASON=RP2040_OCCUPE");
    return;
  }

  uint8_t nbInv = (uint8_t)nbInv64;
  uint8_t startBits = 0u;
  uint8_t previousBits = 0u;
  uint16_t eventCount = 0;
  bool overflow = false;
  uint32_t loopMaxUs = 0u;
  uint32_t droppedEvents = 0u;

  Serial.print("MEASURE;BEGIN;ACTION=MONO_");
  Serial.print(actionTxt);
  Serial.print(";CAPTURE_US="); printUint64(captureUs);
  Serial.print(";PULSE_US=0");
  Serial.print(";HOLD_US="); printUint64(holdUs);
  Serial.print(";NB_INV="); Serial.print(nbInv);
  Serial.print(";START_BITS=");

  appliquerSelection32(sourceEA ? false : true);
  if (actionTxt == "ON") {
    appliquerSorties(0x00u);
    delayMicroseconds((uint32_t)holdUs);
  } else {
    appliquerSorties(0x01u | 0x04u);
    delayMicroseconds((uint32_t)holdUs);
  }

  startBits = composerBitsContactsDepuisGpio();
  previousBits = startBits;
  Serial.print(startBits);
  Serial.println();
  Serial.flush();

  noInterrupts();
  if (actionTxt == "ON") {
    appliquerSorties(0x01u | 0x04u);  // GP14 uniquement
  } else {
    appliquerSorties(0x00u);          // coupure GP14, GP15 reste OFF
  }
  uint64_t t0 = time_us_64();
  uint64_t endAt = t0 + captureUs;
  uint64_t lastSampleUs = t0;

  while (time_us_64() < endAt) {
    uint8_t bits = composerBitsContactsDepuisGpio();
    uint64_t now = time_us_64();
    uint32_t loopDeltaUs = (uint32_t)(now - lastSampleUs);
    if (loopDeltaUs > loopMaxUs) loopMaxUs = loopDeltaUs;
    lastSampleUs = now;
    uint8_t changed = bits ^ previousBits;
    if (changed != 0u) {
      uint32_t tRel = (uint32_t)(now - t0);
      for (uint8_t i = 0; i < 8; i++) {
        if (changed & (1u << i)) {
          if (eventCount < MEASURE_MAX_EVENTS) {
            measureEvents[eventCount].tUs = tRel;
            measureEvents[eventCount].contactIndex = i;
            measureEvents[eventCount].state = (bits >> i) & 0x01u;
            eventCount++;
          } else {
            overflow = true;
            droppedEvents++;
          }
        }
      }
      previousBits = bits;
    }
  }
  if (actionTxt == "OFF") {
    appliquerSorties(0x00u);
  } else {
    appliquerSorties(0x01u | 0x04u);  // reste colle pour permettre la mesure OFF ensuite
  }
  interrupts();

  if (actionTxt == "OFF" && !sourceEA) {
    appliquerSelection32(false);
  }
  appliquerBitsContacts(composerBitsContactsDepuisGpio());
  contactsChangedPending = true;
  sortiesChangedPending = true;
  selectionChangedPending = true;

  envoyerMeasureEvents(eventCount);
  envoyerMeasureEnd(String("MONO_") + actionTxt, captureUs, 0ULL, nbInv, startBits, contactsCachedBits, eventCount, overflow, loopMaxUs, droppedEvents);
  envoyerStatus("MEASURE_DONE");
}


static bool adsWriteRegister(uint8_t reg, uint16_t value) {
  Wire.beginTransmission(ADS1115_ADDR);
  Wire.write(reg);
  Wire.write((uint8_t)(value >> 8));
  Wire.write((uint8_t)(value & 0xFF));
  return Wire.endTransmission() == 0;
}

static bool adsReadRegister(uint8_t reg, uint16_t &value) {
  Wire.beginTransmission(ADS1115_ADDR);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((int)ADS1115_ADDR, 2) != 2) return false;
  value = ((uint16_t)Wire.read() << 8) | (uint16_t)Wire.read();
  return true;
}

void initialiserAds1115() {
  Wire.setSDA(PIN_ADS_SDA);
  Wire.setSCL(PIN_ADS_SCL);
  Wire.begin();
  Wire.setClock(400000);
  delay(5);
  ads1115Ok = adsWriteRegister(0x01, ADS1115_CONFIG_CONT_A0_4096_860SPS);
  delay(3);
  uint16_t raw = 0;
  if (ads1115Ok) ads1115Ok = adsReadRegister(0x00, raw);
  ads1115Raw = (int16_t)raw;
  adsDernierSampleUs = time_us_64();
}

void mettreAJourAds1115() {
  uint64_t now = time_us_64();
  if ((now - adsDernierSampleUs) < ADS_SAMPLE_PERIOD_US) return;
  adsDernierSampleUs = now;
  uint16_t rawUnsigned = 0;
  if (!adsReadRegister(0x00, rawUnsigned)) {
    ads1115Ok = false;
    if (adsFailureCount < 255u) adsFailureCount++;
    if (voltageScanActive && adsFailureCount >= 3u) {
      voltageScanActive = false;
      Serial.println("VSCAN;ERROR;REASON=ADS1115_COMMUNICATION");
    }
    return;
  }
  adsFailureCount = 0u;
  ads1115Ok = true;
  ads1115Raw = (int16_t)rawUnsigned;
  int32_t rawPositive = ads1115Raw < 0 ? 0 : (int32_t)ads1115Raw;
  // PGA ±4,096 V : 125 µV par bit. Rapport stocké en millionièmes.
  int64_t coilUv = ((int64_t)rawPositive * 125LL * (int64_t)voltageRatioU6) / 1000000LL;
  int64_t mv = coilUv / 1000LL + (int64_t)voltageOffsetMv;
  if (mv < 0) mv = 0;
  if (mv > 1000000LL) mv = 1000000LL;
  adsCoilMv = (int32_t)mv;
}

const char *voltageScanModeText(VoltageScanMode mode) {
  if (mode == VSCAN_PICKUP) return "PICKUP";
  if (mode == VSCAN_DROPOUT) return "DROPOUT";
  return "NONE";
}

void envoyerAdsStatus() {
  Serial.print("ADS;STATUS="); Serial.print(ads1115Ok ? "OK" : "ERROR");
  Serial.print(";ADDR=0x48;RAW="); Serial.print(ads1115Raw);
  Serial.print(";COIL_MV="); Serial.print(adsCoilMv);
  Serial.print(";RATIO_U6="); Serial.print(voltageRatioU6);
  Serial.print(";OFFSET_MV="); Serial.print(voltageOffsetMv);
  Serial.print(";MODE="); Serial.print(voltageScanModeText(voltageScanMode));
  Serial.println();
}

bool voltageExpectedForInv(uint8_t bits, uint8_t invIndex, VoltageScanMode mode) {
  bool rClosed = ((bits >> invIndex) & 0x01u) != 0u;
  bool tClosed = ((bits >> (invIndex + 4u)) & 0x01u) != 0u;
  if (mode == VSCAN_PICKUP) return (!rClosed && tClosed);
  if (mode == VSCAN_DROPOUT) return (rClosed && !tClosed);
  return false;
}

bool voltageExpectedGlobal(uint8_t bits, VoltageScanMode mode) {
  for (uint8_t i = 0; i < voltageScanNbInv; i++) {
    if (!voltageExpectedForInv(bits, i, mode)) return false;
  }
  return voltageScanNbInv > 0;
}

void resetVoltageScanCandidates() {
  for (uint8_t i = 0; i < 5; i++) {
    voltageCandidateStartUs[i] = 0ULL;
    voltageStableStartUs[i] = 0ULL;
    voltageCandidateMv[i] = -1;
    voltageCandidateRaw[i] = -1;
    voltageCandidateActive[i] = false;
    voltageResultMv[i] = -1;
    voltageResultRaw[i] = -1;
    voltageResultTimeUs[i] = 0ULL;
    voltageResultDone[i] = false;
  }
}

void envoyerVoltageResult() {
  Serial.print("VSCAN;RESULT;MODE="); Serial.print(voltageScanModeText(voltageScanMode));
  Serial.print(";CAPTURE=FIRST_PASSAGE");
  Serial.print(";VALIDATION=STABLE_AFTER_CAPTURE");
  Serial.print(";GLOBAL_MV="); Serial.print(voltageResultMv[4]);
  Serial.print(";GLOBAL_RAW="); Serial.print(voltageResultRaw[4]);
  Serial.print(";GLOBAL_T_US="); printUint64(voltageResultTimeUs[4]);
  for (uint8_t i = 0; i < 4; i++) {
    Serial.print(";I"); Serial.print(i + 1); Serial.print("_MV="); Serial.print(voltageResultMv[i]);
    Serial.print(";I"); Serial.print(i + 1); Serial.print("_RAW="); Serial.print(voltageResultRaw[i]);
    Serial.print(";I"); Serial.print(i + 1); Serial.print("_T_US="); printUint64(voltageResultTimeUs[i]);
  }
  Serial.print(";LAST_MV="); Serial.print(adsCoilMv);
  Serial.print(";ELAPSED_US="); printUint64(time_us_64() - voltageScanStartUs);
  Serial.println();
}

void gererVoltageScan() {
  if (!voltageScanActive || voltageScanMode == VSCAN_NONE || !ads1115Ok) return;
  uint64_t now = time_us_64();
  if ((now - adsDernierEnvoiUs) >= 100000ULL) {
    adsDernierEnvoiUs = now;
    envoyerAdsStatus();
  }

  uint8_t bits = composerBitsContactsDepuisGpio();

  for (uint8_t slot = 0; slot < 5; slot++) {
    if (voltageResultDone[slot]) continue;

    bool expected = false;
    if (slot < voltageScanNbInv) expected = voltageExpectedForInv(bits, slot, voltageScanMode);
    else if (slot == 4) expected = voltageExpectedGlobal(bits, voltageScanMode);
    else continue;

    if (!expected) {
      // Un rebond annule uniquement la période de stabilité en cours.
      // La tension et l'instant du premier passage restent définitivement mémorisés.
      voltageStableStartUs[slot] = 0ULL;
      continue;
    }

    if (!voltageCandidateActive[slot]) {
      // Premier passage dans l'état cible : capture immédiate AVANT les rebonds.
      voltageCandidateActive[slot] = true;
      voltageCandidateStartUs[slot] = now;
      voltageCandidateMv[slot] = adsCoilMv;
      voltageCandidateRaw[slot] = ads1115Raw;
      voltageStableStartUs[slot] = now;

      if (slot < 4) {
        Serial.print("VSCAN;FIRST;MODE="); Serial.print(voltageScanModeText(voltageScanMode));
        Serial.print(";INV="); Serial.print(slot + 1);
        Serial.print(";MV="); Serial.print(voltageCandidateMv[slot]);
        Serial.print(";RAW="); Serial.print(voltageCandidateRaw[slot]);
        Serial.print(";T_US="); printUint64(voltageCandidateStartUs[slot] - voltageScanStartUs);
        Serial.println();
      } else {
        Serial.print("VSCAN;FIRST;MODE="); Serial.print(voltageScanModeText(voltageScanMode));
        Serial.print(";INV=GLOBAL;MV="); Serial.print(voltageCandidateMv[slot]);
        Serial.print(";RAW="); Serial.print(voltageCandidateRaw[slot]);
        Serial.print(";T_US="); printUint64(voltageCandidateStartUs[slot] - voltageScanStartUs);
        Serial.println();
      }
    } else if (voltageStableStartUs[slot] == 0ULL) {
      // Retour dans l'état cible après un rebond : on recommence seulement
      // la validation stable, sans reprendre la tension.
      voltageStableStartUs[slot] = now;
    }

    if (voltageStableStartUs[slot] != 0ULL &&
        (now - voltageStableStartUs[slot]) >= voltageStableUs) {
      voltageResultDone[slot] = true;
      voltageResultMv[slot] = voltageCandidateMv[slot];
      voltageResultRaw[slot] = voltageCandidateRaw[slot];
      voltageResultTimeUs[slot] = voltageCandidateStartUs[slot] - voltageScanStartUs;

      if (slot < 4) {
        Serial.print("VSCAN;INV;MODE="); Serial.print(voltageScanModeText(voltageScanMode));
        Serial.print(";INV="); Serial.print(slot + 1);
        Serial.print(";MV="); Serial.print(voltageResultMv[slot]);
        Serial.print(";RAW="); Serial.print(voltageResultRaw[slot]);
        Serial.print(";T_US="); printUint64(voltageResultTimeUs[slot]);
        Serial.print(";CAPTURE=FIRST_PASSAGE;VALIDATED_AFTER_US=");
        printUint64(now - voltageCandidateStartUs[slot]);
        Serial.println();
      }

      if (slot == 4) {
        envoyerVoltageResult();
        voltageScanActive = false;
      }
    }
  }
}

void traiterVoltageCfg(const String &cmd) {
  uint64_t ratio = 0ULL, stable = 0ULL;
  String ratioTxt = getToken(cmd, ';', 1);
  String offsetTxt = getToken(cmd, ';', 2);
  String stableTxt = getToken(cmd, ';', 3);
  if (!parseUint64(ratioTxt, ratio) || ratio < 1000000ULL || ratio > 100000000ULL) {
    Serial.println("VSCAN;ERROR;REASON=RATIO_INVALIDE"); return;
  }
  long offset = offsetTxt.toInt();
  if (offset < -500 || offset > 500) { Serial.println("VSCAN;ERROR;REASON=OFFSET_INVALIDE"); return; }
  if (!parseUint64(stableTxt, stable) || stable < 500ULL || stable > 50000ULL) {
    Serial.println("VSCAN;ERROR;REASON=STABLE_US_INVALIDE"); return;
  }
  voltageRatioU6 = (uint32_t)ratio;
  voltageOffsetMv = (int32_t)offset;
  voltageStableUs = (uint32_t)stable;
  Serial.print("VSCAN;CFG;RATIO_U6="); Serial.print(voltageRatioU6);
  Serial.print(";OFFSET_MV="); Serial.print(voltageOffsetMv);
  Serial.print(";STABLE_US="); Serial.print(voltageStableUs);
  Serial.println();
}

void traiterVoltageScan(const String &cmd) {
  String action = getToken(cmd, ';', 1); action.trim(); action.toUpperCase();
  if (action == "CANCEL") {
    voltageScanActive = false; voltageScanMode = VSCAN_NONE;
    Serial.println("VSCAN;CANCELLED"); return;
  }
  if (action != "ARM") { Serial.println("VSCAN;ERROR;REASON=COMMANDE_INVALIDE"); return; }
  String modeTxt = getToken(cmd, ';', 2); modeTxt.trim(); modeTxt.toUpperCase();
  String nbTxt = getToken(cmd, ';', 3);
  uint64_t nb = 0ULL;
  if (!ads1115Ok) { Serial.println("VSCAN;ERROR;REASON=ADS1115_ABSENT"); return; }
  if (!parseUint64(nbTxt, nb) || nb < 1ULL || nb > 4ULL) { Serial.println("VSCAN;ERROR;REASON=NB_INV_INVALIDE"); return; }
  VoltageScanMode mode = VSCAN_NONE;
  if (modeTxt == "PICKUP") mode = VSCAN_PICKUP;
  else if (modeTxt == "DROPOUT") mode = VSCAN_DROPOUT;
  else { Serial.println("VSCAN;ERROR;REASON=MODE_INVALIDE"); return; }
  voltageScanNbInv = (uint8_t)nb;
  voltageScanMode = mode;
  voltageScanStartUs = time_us_64();
  resetVoltageScanCandidates();
  voltageScanActive = true;
  Serial.print("VSCAN;BEGIN;MODE="); Serial.print(voltageScanModeText(mode));
  Serial.print(";CAPTURE=FIRST_PASSAGE");
  Serial.print(";VALIDATION=STABLE_AFTER_CAPTURE");
  Serial.print(";NB_INV="); Serial.print(voltageScanNbInv);
  Serial.print(";START_BITS="); Serial.print(composerBitsContactsDepuisGpio());
  Serial.print(";STABLE_US="); Serial.print(voltageStableUs);
  Serial.println();
}

void traiterCoilHold(const String &cmd) {
  String state = getToken(cmd, ';', 1); state.trim(); state.toUpperCase();
  if (running || neutralPulseActive || etat != ETAT_ARRET) {
    Serial.println("VSCAN;ERROR;REASON=RP2040_OCCUPE"); return;
  }
  uint8_t pattern = 0u;
  if (state == "ON" || state == "BE") pattern = 0x01u; // ON conservé pour compatibilité V2.11.x
  else if (state == "BR") pattern = 0x02u;
  else if (state == "OFF") pattern = 0x00u;
  else { Serial.println("VSCAN;ERROR;REASON=COIL_HOLD_INVALIDE"); return; }
  coilHoldPattern = pattern;
  coilHoldActive = pattern != 0u;
  appliquerSelection32(false); // La source bobine est l'EA via le sélecteur physique.
  appliquerSorties(pattern);
  Serial.print("COIL;HOLD="); Serial.print(coilHoldActive ? 1 : 0);
  Serial.print(";COIL="); Serial.print(pattern == 0x01u ? "BE" : pattern == 0x02u ? "BR" : "OFF");
  Serial.print(";COIL_MV="); Serial.print(adsCoilMv);
  Serial.println();
}

void traiterPulseUs(const String &cmd) {
  String typeTxt = getToken(cmd, ';', 1);
  String dureeTxt = getToken(cmd, ';', 2);
  String sourceTxt = getToken(cmd, ';', 3);
  typeTxt.trim(); typeTxt.toUpperCase();
  sourceTxt.trim(); sourceTxt.toUpperCase();
  bool sourceEA = (sourceTxt == "EA");

  uint64_t dureeUs = 0ULL;
  if (!parseUint64(dureeTxt, dureeUs)) { Serial.println("ERREUR;PULSE_US_INVALIDE"); return; }
  if (!validerDureeUs(dureeUs))        { Serial.println("ERREUR;PULSE_US_HORS_LIMITE"); return; }

  if (typeTxt == "BE") {
    ledRgbSetMode(LED_MODE_PULSE_BE);
    demarrerPulseNeutral(0x01, dureeUs, "BE", sourceEA ? false : true);
  } else if (typeTxt == "BR") {
    ledRgbSetMode(LED_MODE_PULSE_BR);
    demarrerPulseNeutral(0x02, dureeUs, "BR", sourceEA ? false : true);
  } else if (typeTxt == "BEBR" || typeTxt == "BE/BR") {
    ledRgbSetMode(LED_MODE_PULSE_BEBR);
    demarrerPulseNeutral(0x01 | 0x02, dureeUs, "BEBR", false);
  } else {
    Serial.println("ERREUR;PULSE_TYPE_INVALIDE");
    return;
  }

  // La sequence est asynchrone (settle -> pulse -> retombee). Au retour
  // ici, la pulse n'est pas terminee : on annonce le demarrage. La fin reelle
  // emettra STATUS;PULSE_DONE depuis la loop.
  const char *r;
  if (typeTxt == "BE") r = "PULSE_BE_START";
  else if (typeTxt == "BR") r = "PULSE_BR_START";
  else r = "PULSE_BEBR_START";
  envoyerStatus(r);
}

void traiterLed(const String &cmd);

void traiterCommande(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;

  if (cmd == "STOP")    { stopEssai(); envoyerStatus("STOP"); return; }
  if (cmd == "PAUSE")   { pauseEssai(); envoyerStatus("PAUSE"); return; }
  if (cmd == "RESUME")  { reprendreEssai(); envoyerStatus("RESUME"); return; }
  if (cmd == "STATUS?") { envoyerStatus("QUERY"); return; }

  if (cmd.startsWith("LED;"))      { traiterLed(cmd); return; }

  if ((voltageScanActive || coilHoldActive) &&
      (cmd.startsWith("START_US;") || cmd.startsWith("PULSE_US;") ||
       cmd.startsWith("MEASURE_CONTACTS;") || cmd.startsWith("MEASURE_MONO;"))) {
    Serial.println("VSCAN;ERROR;REASON=MODE_TENSION_OCCUPE");
    return;
  }

  if (cmd.startsWith("START_US;")) { traiterStartUs(cmd); return; }
  if (cmd.startsWith("PULSE_US;")) { traiterPulseUs(cmd); return; }
  if (cmd.startsWith("MEASURE_CONTACTS;")) { traiterMeasureContacts(cmd); return; }
  if (cmd.startsWith("MEASURE_MONO;")) { traiterMeasureMono(cmd); return; }
  if (cmd.startsWith("VOLTAGE_CFG;")) { traiterVoltageCfg(cmd); return; }
  if (cmd.startsWith("VOLTAGE_SCAN;")) { traiterVoltageScan(cmd); return; }
  if (cmd.startsWith("COIL_HOLD;")) { traiterCoilHold(cmd); return; }
  if (cmd == "ADS?") { envoyerAdsStatus(); return; }

  Serial.print("ERREUR;COMMANDE_INCONNUE;");
  Serial.println(cmd);
}

void lireSerie() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (ligneSerie.length() > 0) {
        traiterCommande(ligneSerie);
        ligneSerie = "";
      }
    } else {
      ligneSerie += c;
      if (ligneSerie.length() > 220) {
        ligneSerie = "";
        Serial.println("ERREUR;LIGNE_TROP_LONGUE");
      }
    }
  }
}

void ledRgbSet(uint8_t r, uint8_t g, uint8_t b) {
  uint32_t couleur = ledRgb.Color(r, g, b);
  if (couleur == ledRgbDerniereCouleur) {
    return;
  }
  ledRgb.setPixelColor(0, couleur);
  ledRgb.show();
  ledRgbDerniereCouleur = couleur;
}

void ledRgbSetMode(LedRgbMode mode) {
  ledRgbMode = mode;
  ledRgbModeStartMs = millis();
  ledRgbDernierUpdateMs = 0UL;

  switch (mode) {
    case LED_MODE_CONNECTED: ledRgbSet(18, 14, 0); break;      // jaune tres pale fixe
    case LED_MODE_PULSE_BE:  ledRgbSet(120, 0, 0); break;      // rouge
    case LED_MODE_PULSE_BR:  ledRgbSet(0, 0, 140); break;      // bleu
    case LED_MODE_PULSE_BEBR:ledRgbSet(90, 0, 120); break;     // violet
    case LED_MODE_SELECT32:  ledRgbSet(0, 120, 120); break;    // cyan
    case LED_MODE_ACCEPT:    ledRgbSet(0, 120, 0); break;      // vert fixe
    case LED_MODE_REJECT:    ledRgbSet(140, 0, 0); break;      // rouge fixe
    default: break; // modes animes geres par mettreAJourLedRgb()
  }
}

void ledRgbAppliquerModeMachinePending() {
  uint8_t pending = 255u;
  CRIT_ENTER();
  pending = ledRgbModeMachinePending;
  ledRgbModeMachinePending = 255u;
  CRIT_EXIT();

  if (pending != 255u) {
    ledRgbSetMode((LedRgbMode)pending);
  }
}

uint8_t ledTriangle(uint32_t elapsedMs, uint32_t periodeMs, uint8_t maxValue) {
  uint32_t phase = elapsedMs % periodeMs;
  uint32_t demi = periodeMs / 2UL;
  if (phase <= demi) {
    return (uint8_t)((phase * maxValue) / demi);
  }
  return (uint8_t)(((periodeMs - phase) * maxValue) / demi);
}

void mettreAJourLedRgb() {
  ledRgbAppliquerModeMachinePending();

  uint32_t maintenantMs = millis();
  if ((uint32_t)(maintenantMs - ledRgbDernierUpdateMs) < 80UL) {
    return;
  }
  ledRgbDernierUpdateMs = maintenantMs;

  uint32_t elapsed = maintenantMs - ledRgbModeStartMs;

  switch (ledRgbMode) {
    case LED_MODE_BOOT:
      // Non connecte : jaune pale clignotant.
      if ((elapsed % 900UL) < 450UL) ledRgbSet(55, 38, 0);
      else ledRgbSet(0, 0, 0);
      break;

    case LED_MODE_CYCLE_DONE: {
      // Cyclage fini : rouge doux progressif.
      uint8_t r = ledTriangle(elapsed, 2200UL, 120);
      ledRgbSet(r, 0, 0);
      break;
    }

    case LED_MODE_ERROR:
      // Erreur : orange clignotant.
      if ((elapsed % 500UL) < 250UL) ledRgbSet(180, 55, 0);
      else ledRgbSet(0, 0, 0);
      break;

    case LED_MODE_CONNECTED:
      ledRgbSet(18, 14, 0);
      break;

    case LED_MODE_SELECT32:
      ledRgbSet(0, 120, 120);
      break;

    case LED_MODE_ACCEPT:
      ledRgbSet(0, 120, 0);
      break;

    case LED_MODE_REJECT:
      ledRgbSet(140, 0, 0);
      break;

    case LED_MODE_PULSE_BE:
      ledRgbSet(120, 0, 0);
      break;

    case LED_MODE_PULSE_BR:
      ledRgbSet(0, 0, 140);
      break;

    case LED_MODE_PULSE_BEBR:
      ledRgbSet(90, 0, 120);
      break;
  }
}

void traiterLed(const String &cmd) {
  String modeTxt = getToken(cmd, ';', 1);
  modeTxt.trim();
  modeTxt.toUpperCase();

  if (modeTxt == "BOOT" || modeTxt == "DISCONNECTED") ledRgbSetMode(LED_MODE_BOOT);
  else if (modeTxt == "CONNECTED" || modeTxt == "IDLE" || modeTxt == "ARRET") ledRgbSetMode(LED_MODE_CONNECTED);
  else if (modeTxt == "CYCLE_DONE" || modeTxt == "CYCLAGE_FINI") ledRgbSetMode(LED_MODE_CYCLE_DONE);
  else if (modeTxt == "BE") ledRgbSetMode(LED_MODE_PULSE_BE);
  else if (modeTxt == "BR") ledRgbSetMode(LED_MODE_PULSE_BR);
  else if (modeTxt == "BEBR" || modeTxt == "BE/BR") ledRgbSetMode(LED_MODE_PULSE_BEBR);
  else if (modeTxt == "SELECT32" || modeTxt == "SEL32" || modeTxt == "CYAN") ledRgbSetMode(LED_MODE_SELECT32);
  else if (modeTxt == "ACCEPT" || modeTxt == "ACCEPTE") ledRgbSetMode(LED_MODE_ACCEPT);
  else if (modeTxt == "REJECT" || modeTxt == "REJETE") ledRgbSetMode(LED_MODE_REJECT);
  else if (modeTxt == "ERROR" || modeTxt == "ERREUR") ledRgbSetMode(LED_MODE_ERROR);
  else {
    Serial.print("ERREUR;LED_MODE_INVALIDE;");
    Serial.println(modeTxt);
    return;
  }

  Serial.print("LED;OK;");
  Serial.println(modeTxt);
}

void setup() {
  gpio_init(PIN_SORTIE_1);
  gpio_init(PIN_SORTIE_2);
  gpio_init(PIN_SELECT_32V);
  gpio_init(PIN_LED_INTERNE);
  gpio_init(PIN_CONTACT_RESET_1);
  gpio_init(PIN_CONTACT_RESET_2);
  gpio_init(PIN_CONTACT_RESET_3);
  gpio_init(PIN_CONTACT_RESET_4);
  gpio_init(PIN_CONTACT_LATCH_1);
  gpio_init(PIN_CONTACT_LATCH_2);
  gpio_init(PIN_CONTACT_LATCH_3);
  gpio_init(PIN_CONTACT_LATCH_4);

  gpio_set_dir(PIN_SORTIE_1, GPIO_OUT);
  gpio_set_dir(PIN_SORTIE_2, GPIO_OUT);
  gpio_set_dir(PIN_SELECT_32V, GPIO_OUT);
  gpio_set_dir(PIN_LED_INTERNE, GPIO_OUT);

  ledRgb.begin();
  ledRgb.setBrightness(LED_RGB_BRIGHTNESS);
  ledRgbSetMode(LED_MODE_BOOT);

  gpio_set_dir(PIN_CONTACT_RESET_1, GPIO_IN);
  gpio_set_dir(PIN_CONTACT_RESET_2, GPIO_IN);
  gpio_set_dir(PIN_CONTACT_RESET_3, GPIO_IN);
  gpio_set_dir(PIN_CONTACT_RESET_4, GPIO_IN);
  gpio_set_dir(PIN_CONTACT_LATCH_1, GPIO_IN);
  gpio_set_dir(PIN_CONTACT_LATCH_2, GPIO_IN);
  gpio_set_dir(PIN_CONTACT_LATCH_3, GPIO_IN);
  gpio_set_dir(PIN_CONTACT_LATCH_4, GPIO_IN);

  // Pull-up externes sur R1/R2/R3/R4/T1/T2/T3/T4.
  // On désactive les pulls internes pour que l'état soit imposé uniquement
  // par les résistances externes vers 3V3.
  gpio_disable_pulls(PIN_CONTACT_RESET_1);
  gpio_disable_pulls(PIN_CONTACT_RESET_2);
  gpio_disable_pulls(PIN_CONTACT_RESET_3);
  gpio_disable_pulls(PIN_CONTACT_RESET_4);
  gpio_disable_pulls(PIN_CONTACT_LATCH_1);
  gpio_disable_pulls(PIN_CONTACT_LATCH_2);
  gpio_disable_pulls(PIN_CONTACT_LATCH_3);
  gpio_disable_pulls(PIN_CONTACT_LATCH_4);

  appliquerBitsContacts(composerBitsContactsDepuisGpio());
  contactsChangedPending = true;
  dernierSampleContactsUs = time_us_64();
  dernierEnvoiContactsUs = 0ULL;

  appliquerSorties(0x00);
  appliquerSelection32(false);  // tension basse par defaut au boot
  selectionChangedPending = true;
  dernierEnvoiSelectionUs = 0ULL;
  sortiesLastSentPattern = 255u;
  sortiesChangedPending = true;
  dernierEnvoiSortiesUs = 0ULL;

  initialiserAds1115();

  Serial.begin(921600);
  delay(500);

  Serial.println("RP2040_RELAIS_28VDC_PRET;V2_12_3_R8;EA_CHRONO_NO_GP26;SELECTION_TENSION_BASSE_HAUTE_INFO_GP26;LED_RGB_GP16;LED_COMMANDS;MEASURE_CONTACTS;MEASURE_MONO;ADS1115_GP0_GP1;VOLTAGE_MONO_BISTABLE;CALIBRATION_RAW;VOLTAGE_FIRST_PASSAGE;STABLE_CONFIRMATION;CAPTURE_QUALITY_50US");
  envoyerStatus("BOOT");
}

void loop() {
  lireSerie();
  mettreAJourContactsRapide();
  mettreAJourAds1115();
  gererVoltageScan();

  // Pulse courte Neutral : le settle (alarme) est termine, on execute la largeur
  // de pulse en section critique cote loop pour un jitter minimal.
  if (neutralPulseCourtePending) {
    neutralPulseCourtePending = false;
    if (neutralPhase == NEUTRAL_PULSE_ON) {
      executerPulseCourteEnSectionCritique();
    }
  }

  if (neutralPulseDone) {
    neutralPulseDone = false;
    envoyerStatus("PULSE_DONE");
    if (ledRgbMode == LED_MODE_PULSE_BE || ledRgbMode == LED_MODE_PULSE_BR || ledRgbMode == LED_MODE_PULSE_BEBR) {
      ledRgbSetMode(selection32Active ? LED_MODE_SELECT32 : LED_MODE_CONNECTED);
    }
  }

  gererEnvoiSortiesRapide();
  gererEnvoiSelectionTension();
  gererEnvoiContacts();
  mettreAJourLedRgb();

  uint32_t maintenantMs = millis();
  if ((uint32_t)(maintenantMs - dernierStatusMs) >= STATUS_PERIOD_MS) {
    dernierStatusMs = maintenantMs;
    envoyerStatus("AUTO");
  }
}

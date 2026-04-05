#include <Arduino.h>
#include <Arduino_GFX_Library.h>

#include <cctype>
#include <cstdio>
#include <cstring>

#if __has_include(<esp_lcd_touch_axs5106l.h>)
#include <Wire.h>
#include <esp_lcd_touch_axs5106l.h>
#define METERSIM_HAS_TOUCH_LIB 1
#else
#define METERSIM_HAS_TOUCH_LIB 0
#endif

/*
  MeterSIM short-term scope firmware:
  - BASIC serial mode
  - DLMS placeholder mode
  - RGB mode indication
  - On-screen start/stop + mode buttons
  - Touch interaction (when touch profile + touch library are available)

  IMPORTANT:
  Keep your known-good Arduino IDE flash and PSRAM settings for your board.
  This sketch intentionally does not force toolchain-specific values.
*/

#define METERSIM_BOARD_LCD_147 1
#define METERSIM_BOARD_TOUCH_LCD_147 2

#ifndef METERSIM_BOARD_PROFILE
// Default profile matches DeviceDetails.md (ESP32-S3-LCD-1.47, ST7789, RGB bead).
#define METERSIM_BOARD_PROFILE METERSIM_BOARD_LCD_147
#endif

#if METERSIM_BOARD_PROFILE == METERSIM_BOARD_LCD_147
constexpr int PIN_LCD_MOSI = 45;
constexpr int PIN_LCD_SCK = 40;
constexpr int PIN_LCD_CS = 42;
constexpr int PIN_LCD_DC = 41;
constexpr int PIN_LCD_RST = 39;
constexpr int PIN_LCD_BL = 48;
constexpr int PIN_RGB = 38;
#define METERSIM_HAS_RGB_BEAD 1
#elif METERSIM_BOARD_PROFILE == METERSIM_BOARD_TOUCH_LCD_147
constexpr int PIN_LCD_DC = 45;
constexpr int PIN_LCD_CS = 21;
constexpr int PIN_LCD_SCK = 38;
constexpr int PIN_LCD_MOSI = 39;
constexpr int PIN_LCD_RST = 40;
constexpr int PIN_LCD_BL = 46;

constexpr int PIN_TOUCH_SDA = 42;
constexpr int PIN_TOUCH_SCL = 41;
constexpr int PIN_TOUCH_RST = 47;
constexpr int PIN_TOUCH_INT = 48;

// Touch board does not document an onboard RGB bead in the official spec.
constexpr int PIN_RGB = -1;
#define METERSIM_HAS_RGB_BEAD 0
#else
#error "Invalid METERSIM_BOARD_PROFILE value."
#endif

#if METERSIM_BOARD_PROFILE == METERSIM_BOARD_TOUCH_LCD_147 && METERSIM_HAS_TOUCH_LIB
#define METERSIM_TOUCH_ENABLED 1
#else
#define METERSIM_TOUCH_ENABLED 0
#endif

constexpr uint16_t LCD_WIDTH = 172;
constexpr uint16_t LCD_HEIGHT = 320;
constexpr uint16_t LCD_X_OFFSET = 34;
constexpr uint16_t LCD_Y_OFFSET = 0;

constexpr uint32_t BASIC_STREAM_INTERVAL_MS = 1000;
constexpr uint32_t DLMS_STREAM_INTERVAL_MS = 1400;
constexpr uint32_t TOUCH_DEBOUNCE_MS = 220;

constexpr uint16_t COLOR_DARK_GREEN = 0x0320;
constexpr uint16_t COLOR_DARK_CYAN = 0x0410;
constexpr uint16_t COLOR_NAVY = 0x000F;
constexpr uint16_t COLOR_MAROON = 0x7800;

constexpr uint8_t UI_TEXT_SIZE = 2;
constexpr int16_t UI_CHAR_W = 6 * UI_TEXT_SIZE;
constexpr int16_t UI_CHAR_H = 8 * UI_TEXT_SIZE;

const uint8_t DLMS_PLACEHOLDER_FRAME[] = {
    0x7E, 0xA0, 0x07, 0x03, 0x21, 0x93, 0x0F, 0x01, 0x7E,
};

Arduino_DataBus *bus =
    new Arduino_ESP32SPI(PIN_LCD_DC, PIN_LCD_CS, PIN_LCD_SCK, PIN_LCD_MOSI);
Arduino_GFX *gfx = new Arduino_ST7789(
    bus,
    PIN_LCD_RST,
    0 /* rotation */,
    false /* IPS */,
    LCD_WIDTH,
    LCD_HEIGHT,
    LCD_X_OFFSET,
    LCD_Y_OFFSET,
    LCD_X_OFFSET,
    LCD_Y_OFFSET);

enum class DeviceMode : uint8_t {
  BASIC_SERIAL = 0,
  DLMS_PLACEHOLDER = 1,
};

struct UiButton {
  int16_t x;
  int16_t y;
  int16_t w;
  int16_t h;
};

struct CommsIndicators {
  bool rxActive;
  bool txActive;
  uint32_t rxTimeout;
  uint32_t txTimeout;
};

DeviceMode currentMode = DeviceMode::BASIC_SERIAL;
bool streamEnabled = true;
bool uiDirty = true;
bool touchRuntimeReady = false;

uint32_t lastStreamAt = 0;
uint32_t lastTouchAt = 0;
uint32_t bootTime = 0;

int16_t screenW = LCD_WIDTH;
int16_t screenH = LCD_HEIGHT;
UiButton streamButton{0, 0, 0, 0};
UiButton modeButton{0, 0, 0, 0};

CommsIndicators commsIndicators{false, false, 0, 0};

char lastEvent[64] = "boot";
String commandBuffer;

const char *modeName(DeviceMode mode) {
  switch (mode) {
    case DeviceMode::BASIC_SERIAL:
      return "BASIC_SERIAL";
    case DeviceMode::DLMS_PLACEHOLDER:
      return "DLMS_PLACEHOLDER";
    default:
      return "UNKNOWN";
  }
}

const char *modeHeading(DeviceMode mode) {
  switch (mode) {
    case DeviceMode::BASIC_SERIAL:
      return "BASIC SERIAL";
    case DeviceMode::DLMS_PLACEHOLDER:
      return "DLMS PLACEHOLDER";
    default:
      return "UNKNOWN MODE";
  }
}

const char *boardProfileName() {
#if METERSIM_BOARD_PROFILE == METERSIM_BOARD_LCD_147
  return "ESP32-S3-LCD-1.47";
#elif METERSIM_BOARD_PROFILE == METERSIM_BOARD_TOUCH_LCD_147
  return "ESP32-S3-Touch-LCD-1.47";
#else
  return "Unknown profile";
#endif
}

uint16_t modeAccentColor(DeviceMode mode) {
  switch (mode) {
    case DeviceMode::BASIC_SERIAL:
      return COLOR_DARK_GREEN;
    case DeviceMode::DLMS_PLACEHOLDER:
      return COLOR_DARK_CYAN;
    default:
      return COLOR_NAVY;
  }
}

void setLastEvent(const char *text) {
  std::strncpy(lastEvent, text, sizeof(lastEvent) - 1);
  lastEvent[sizeof(lastEvent) - 1] = '\0';
}

void flagTxActivity() {
  commsIndicators.txActive = true;
  commsIndicators.txTimeout = millis() + 200;
}

void flagRxActivity() {
  commsIndicators.rxActive = true;
  commsIndicators.rxTimeout = millis() + 200;
}

void updateCommsIndicators() {
  const uint32_t now = millis();
  if (commsIndicators.txActive && now > commsIndicators.txTimeout) {
    commsIndicators.txActive = false;
  }
  if (commsIndicators.rxActive && now > commsIndicators.rxTimeout) {
    commsIndicators.rxActive = false;
  }
}

void setRgbColor(uint8_t red, uint8_t green, uint8_t blue) {
#if METERSIM_HAS_RGB_BEAD
  neopixelWrite(PIN_RGB, red, green, blue);
#else
  (void)red;
  (void)green;
  (void)blue;
#endif
}

void applyModeRgbColor() {
  if (currentMode == DeviceMode::BASIC_SERIAL) {
    setRgbColor(0, 180, 30);
  } else {
    setRgbColor(20, 90, 220);
  }
}

void computeUiLayout() {
  screenW = gfx->width();
  screenH = gfx->height();
}

void drawLedIndicator(int16_t x, int16_t y, bool isActive, const char *label) {
  const int16_t ledRadius = 8;
  const uint16_t ledColor = isActive ? RGB565_GREEN : RGB565_DARKGREY;

  // Draw LED circle
  gfx->fillCircle(x, y, ledRadius, ledColor);
  gfx->drawCircle(x, y, ledRadius, RGB565_WHITE);

  // Draw label below LED
  gfx->setTextSize(1);
  gfx->setTextColor(RGB565_WHITE);
  const int16_t labelWidth = static_cast<int16_t>(std::strlen(label) * 6);
  gfx->setCursor(x - labelWidth / 2, y + ledRadius + 6);
  gfx->print(label);
}

void formatUptime(uint32_t millis, char *buffer, size_t size) {
  uint32_t seconds = millis / 1000;
  uint32_t minutes = seconds / 60;
  uint32_t hours = minutes / 60;

  seconds = seconds % 60;
  minutes = minutes % 60;

  std::snprintf(buffer, size, "%02lu:%02lu:%02lu", hours, minutes, seconds);
}

void renderUi() {
  gfx->fillScreen(RGB565_BLACK);

  const int16_t margin = 8;
  const int16_t gap = 8;
  const uint16_t accent = modeAccentColor(currentMode);

  int16_t yPos = margin;
  const int16_t sectionHeight = 50;

  // Section 1: Device Mode Header
  gfx->fillRect(0, yPos, screenW, sectionHeight, accent);
  gfx->setTextColor(RGB565_WHITE);
  gfx->setTextSize(UI_TEXT_SIZE);

  const char *heading = modeHeading(currentMode);
  const int16_t headingWidth = static_cast<int16_t>(std::strlen(heading) * UI_CHAR_W);
  int16_t headingX = (screenW - headingWidth) / 2;
  if (headingX < margin) {
    headingX = margin;
  }
  gfx->setCursor(headingX, static_cast<int16_t>(yPos + sectionHeight / 2 - UI_CHAR_H / 2));
  gfx->print(heading);
  yPos += sectionHeight + gap;

  // Section 2: TX/RX Indicators
  updateCommsIndicators();
  const int16_t ledSectionHeight = 50;
  const int16_t ledY = yPos + ledSectionHeight / 2;
  const int16_t ledSpacing = screenW / 2;

  drawLedIndicator(ledSpacing / 2, ledY, commsIndicators.rxActive, "RX");
  drawLedIndicator(screenW - ledSpacing / 2, ledY, commsIndicators.txActive, "TX");
  yPos += ledSectionHeight + gap;

  // Section 3: Uptime Display
  char uptimeStr[16];
  uint32_t currentTime = bootTime > 0 ? (millis() - bootTime) : 0;
  formatUptime(currentTime, uptimeStr, sizeof(uptimeStr));

  gfx->setTextSize(UI_TEXT_SIZE);
  gfx->setTextColor(RGB565_WHITE);
  gfx->setCursor(margin, yPos + UI_CHAR_H);
  gfx->print("Uptime:");

  gfx->setCursor(margin, static_cast<int16_t>(yPos + UI_CHAR_H * 2 + 6));
  gfx->setTextSize(UI_TEXT_SIZE);
  gfx->print(uptimeStr);
  yPos += 60 + gap;

  // Section 4: Stream Status
  gfx->setTextSize(1);
  gfx->setTextColor(RGB565_WHITE);
  gfx->setCursor(margin, yPos + 8);
  const char *streamStatus = streamEnabled ? "STREAM: ON" : "STREAM: OFF";
  gfx->print(streamStatus);
  yPos += 18 + gap;

  // Section 5: Last Event
  gfx->setTextSize(1);
  gfx->setTextColor(RGB565_DARKGREY);
  gfx->setCursor(margin, yPos + 8);
  gfx->print(lastEvent);
}

void printHelp() {
  Serial.println("[HELP] Commands:");
  Serial.println("  HELP");
  Serial.println("  STATUS");
  Serial.println("  MODE:BASIC");
  Serial.println("  MODE:DLMS");
  Serial.println("  MODE:NEXT");
  Serial.println("  MODE?");
  Serial.println("  STREAM:ON");
  Serial.println("  STREAM:OFF");
  Serial.println("  STREAM:TOGGLE");
  Serial.println("  DLMS:ONCE");
  Serial.println("  PING");
}

void printStatus() {
  Serial.printf("[STATUS] profile=%s mode=%s stream=%s touch=%s uptime=%lu\n",
                boardProfileName(),
                modeName(currentMode),
                streamEnabled ? "ON" : "OFF",
                touchRuntimeReady ? "READY" : "UNAVAILABLE",
                static_cast<unsigned long>(millis()));
}

void setMode(DeviceMode newMode, const char *source) {
  if (currentMode == newMode) {
    return;
  }

  currentMode = newMode;
  applyModeRgbColor();
  uiDirty = true;

  char eventBuffer[64];
  std::snprintf(eventBuffer,
                sizeof(eventBuffer),
                "mode=%s via %s",
                modeName(currentMode),
                source);
  setLastEvent(eventBuffer);

  Serial.printf("[SYS] Mode changed -> %s (%s)\n", modeName(currentMode), source);
}

void cycleMode(const char *source) {
  if (currentMode == DeviceMode::BASIC_SERIAL) {
    setMode(DeviceMode::DLMS_PLACEHOLDER, source);
  } else {
    setMode(DeviceMode::BASIC_SERIAL, source);
  }
}

void setStreamState(bool enabled, const char *source) {
  if (streamEnabled == enabled) {
    return;
  }

  streamEnabled = enabled;
  uiDirty = true;

  char eventBuffer[64];
  std::snprintf(eventBuffer,
                sizeof(eventBuffer),
                "stream=%s via %s",
                streamEnabled ? "on" : "off",
                source);
  setLastEvent(eventBuffer);

  Serial.printf("[SYS] Stream %s (%s)\n", streamEnabled ? "ON" : "OFF", source);
}

void emitBasicSerialSample() {
  const float voltage = 220.0f + static_cast<float>(random(-60, 61)) / 10.0f;
  const float current = 0.5f + static_cast<float>(random(0, 400)) / 100.0f;
  const float pf = 0.85f + static_cast<float>(random(0, 16)) / 100.0f;
  const float watts = voltage * current * pf;

  Serial.printf("METER|mode=BASIC|ms=%lu|V=%.1f|I=%.2f|PF=%.2f|P=%.1f\n",
                static_cast<unsigned long>(millis()),
                voltage,
                current,
                pf,
                watts);
  flagTxActivity();
}

void emitDlmsPlaceholderFrame() {
  Serial.write(DLMS_PLACEHOLDER_FRAME, sizeof(DLMS_PLACEHOLDER_FRAME));
  Serial.write('\n');
  flagTxActivity();
}

void serviceStream() {
  if (!streamEnabled) {
    return;
  }

  const uint32_t now = millis();
  const uint32_t interval = (currentMode == DeviceMode::BASIC_SERIAL)
                                ? BASIC_STREAM_INTERVAL_MS
                                : DLMS_STREAM_INTERVAL_MS;
  if (now - lastStreamAt < interval) {
    return;
  }

  lastStreamAt = now;
  if (currentMode == DeviceMode::BASIC_SERIAL) {
    emitBasicSerialSample();
  } else {
    emitDlmsPlaceholderFrame();
  }
}

void processCommand(const String &rawCommand) {
  String command = rawCommand;
  command.trim();
  if (command.length() == 0) {
    return;
  }

  setLastEvent(command.c_str());
  uiDirty = true;

  String upper = command;
  upper.toUpperCase();

  if (upper == "HELP") {
    printHelp();
    return;
  }
  if (upper == "PING") {
    Serial.println("PONG");
    return;
  }
  if (upper == "STATUS") {
    printStatus();
    return;
  }
  if (upper == "MODE?") {
    Serial.printf("MODE:%s\n", modeName(currentMode));
    return;
  }
  if (upper == "MODE:NEXT") {
    cycleMode("serial");
    return;
  }
  if (upper == "MODE:BASIC") {
    setMode(DeviceMode::BASIC_SERIAL, "serial");
    return;
  }
  if (upper == "MODE:DLMS") {
    setMode(DeviceMode::DLMS_PLACEHOLDER, "serial");
    return;
  }
  if (upper == "STREAM:ON") {
    setStreamState(true, "serial");
    return;
  }
  if (upper == "STREAM:OFF") {
    setStreamState(false, "serial");
    return;
  }
  if (upper == "STREAM:TOGGLE") {
    setStreamState(!streamEnabled, "serial");
    return;
  }
  if (upper == "DLMS:ONCE") {
    emitDlmsPlaceholderFrame();
    return;
  }

  if (currentMode == DeviceMode::BASIC_SERIAL) {
    Serial.print("ECHO:");
    Serial.println(command);
    return;
  }

  Serial.print("[WARN] Unknown command: ");
  Serial.println(command);
}

void readSerialCommands() {
  while (Serial.available() > 0) {
    flagRxActivity();
    const char c = static_cast<char>(Serial.read());
    if ((c == '\n') || (c == '\r')) {
      if (commandBuffer.length() > 0) {
        processCommand(commandBuffer);
        commandBuffer = "";
      }
      continue;
    }

    if (std::isprint(static_cast<unsigned char>(c)) != 0) {
      if (commandBuffer.length() < 120) {
        commandBuffer += c;
      }
    }
  }
}

#if METERSIM_BOARD_PROFILE == METERSIM_BOARD_TOUCH_LCD_147
void lcdRegInitTouchProfile() {
  static const uint8_t initOperations[] = {
      BEGIN_WRITE,
      WRITE_COMMAND_8, 0x11,
      END_WRITE,
      DELAY, 120,

      BEGIN_WRITE,
      WRITE_C8_D16, 0xDF, 0x98, 0x53,
      WRITE_C8_D8, 0xB2, 0x23,

      WRITE_COMMAND_8, 0xB7,
      WRITE_BYTES, 4,
      0x00, 0x47, 0x00, 0x6F,

      WRITE_COMMAND_8, 0xBB,
      WRITE_BYTES, 6,
      0x1C, 0x1A, 0x55, 0x73, 0x63, 0xF0,

      WRITE_C8_D16, 0xC0, 0x44, 0xA4,
      WRITE_C8_D8, 0xC1, 0x16,

      WRITE_COMMAND_8, 0xC3,
      WRITE_BYTES, 8,
      0x7D, 0x07, 0x14, 0x06, 0xCF, 0x71, 0x72, 0x77,

      WRITE_COMMAND_8, 0xC4,
      WRITE_BYTES, 12,
      0x00, 0x00, 0xA0, 0x79, 0x0B, 0x0A, 0x16, 0x79, 0x0B, 0x0A, 0x16, 0x82,

      WRITE_COMMAND_8, 0xC8,
      WRITE_BYTES, 32,
      0x3F, 0x32, 0x29, 0x29, 0x27, 0x2B, 0x27, 0x28, 0x28, 0x26, 0x25, 0x17, 0x12, 0x0D, 0x04, 0x00,
      0x3F, 0x32, 0x29, 0x29, 0x27, 0x2B, 0x27, 0x28, 0x28, 0x26, 0x25, 0x17, 0x12, 0x0D, 0x04, 0x00,

      WRITE_COMMAND_8, 0xD0,
      WRITE_BYTES, 5,
      0x04, 0x06, 0x6B, 0x0F, 0x00,

      WRITE_C8_D16, 0xD7, 0x00, 0x30,
      WRITE_C8_D8, 0xE6, 0x14,
      WRITE_C8_D8, 0xDE, 0x01,

      WRITE_COMMAND_8, 0xB7,
      WRITE_BYTES, 5,
      0x03, 0x13, 0xEF, 0x35, 0x35,

      WRITE_COMMAND_8, 0xC1,
      WRITE_BYTES, 3,
      0x14, 0x15, 0xC0,

      WRITE_C8_D16, 0xC2, 0x06, 0x3A,
      WRITE_C8_D16, 0xC4, 0x72, 0x12,
      WRITE_C8_D8, 0xBE, 0x00,
      WRITE_C8_D8, 0xDE, 0x02,

      WRITE_COMMAND_8, 0xE5,
      WRITE_BYTES, 3,
      0x00, 0x02, 0x00,

      WRITE_COMMAND_8, 0xE5,
      WRITE_BYTES, 3,
      0x01, 0x02, 0x00,

      WRITE_C8_D8, 0xDE, 0x00,
      WRITE_C8_D8, 0x35, 0x00,
      WRITE_C8_D8, 0x3A, 0x05,

      WRITE_COMMAND_8, 0x2A,
      WRITE_BYTES, 4,
      0x00, 0x22, 0x00, 0xCD,

      WRITE_COMMAND_8, 0x2B,
      WRITE_BYTES, 4,
      0x00, 0x00, 0x01, 0x3F,

      WRITE_C8_D8, 0xDE, 0x02,

      WRITE_COMMAND_8, 0xE5,
      WRITE_BYTES, 3,
      0x00, 0x02, 0x00,

      WRITE_C8_D8, 0xDE, 0x00,
      WRITE_C8_D8, 0x36, 0x00,
      WRITE_COMMAND_8, 0x21,
      END_WRITE,

      DELAY, 10,

      BEGIN_WRITE,
      WRITE_COMMAND_8, 0x29,
      END_WRITE};

  bus->batchOperation(initOperations, sizeof(initOperations));
}
#endif

void initTouchIfAvailable() {
#if METERSIM_TOUCH_ENABLED
  Wire.begin(PIN_TOUCH_SDA, PIN_TOUCH_SCL);
  bsp_touch_init(
      &Wire, PIN_TOUCH_RST, PIN_TOUCH_INT, gfx->getRotation(), gfx->width(), gfx->height());
  touchRuntimeReady = true;
#else
  touchRuntimeReady = false;
#endif
}

void readTouchButtons() {
#if METERSIM_TOUCH_ENABLED
  bsp_touch_read();

  touch_data_t touchData{};
  if (!bsp_touch_get_coordinates(&touchData)) {
    return;
  }

  const uint32_t now = millis();
  if (now - lastTouchAt < TOUCH_DEBOUNCE_MS) {
    return;
  }
  lastTouchAt = now;

  const int16_t x = static_cast<int16_t>(touchData.coords[0].x);
  const int16_t y = static_cast<int16_t>(touchData.coords[0].y);

  if (pointInButton(streamButton, x, y)) {
    setStreamState(!streamEnabled, "touch");
  } else if (pointInButton(modeButton, x, y)) {
    cycleMode("touch");
  }
#endif
}

void setup() {
  Serial.begin(115200);
  delay(1200);

  randomSeed(static_cast<uint32_t>(micros()));

  Serial.println("[BOOT] MeterSIM short-term scope firmware");
  Serial.printf("[BOOT] Profile: %s\n", boardProfileName());

#if METERSIM_BOARD_PROFILE == METERSIM_BOARD_TOUCH_LCD_147 && !METERSIM_HAS_TOUCH_LIB
  Serial.println("[WARN] Touch profile selected but esp_lcd_touch_axs5106l is not installed.");
#endif

  if (!gfx->begin()) {
    Serial.println("[ERR] gfx->begin() failed.");
  }

#if METERSIM_BOARD_PROFILE == METERSIM_BOARD_TOUCH_LCD_147
  lcdRegInitTouchProfile();
#endif

  gfx->setRotation(0);
  gfx->setTextWrap(false);
  gfx->fillScreen(RGB565_BLACK);

  pinMode(PIN_LCD_BL, OUTPUT);
  digitalWrite(PIN_LCD_BL, HIGH);

  bootTime = millis();
  computeUiLayout();
  initTouchIfAvailable();
  applyModeRgbColor();
  printHelp();
  printStatus();
  uiDirty = true;
  renderUi();
}

void loop() {
  readSerialCommands();
  readTouchButtons();
  serviceStream();

  // Mark UI dirty when comms activity changes
  static bool lastRxState = false;
  static bool lastTxState = false;
  if (commsIndicators.rxActive != lastRxState ||
      commsIndicators.txActive != lastTxState) {
    uiDirty = true;
    lastRxState = commsIndicators.rxActive;
    lastTxState = commsIndicators.txActive;
  }

  if (uiDirty) {
    renderUi();
    uiDirty = false;
  }

  delay(5);
}

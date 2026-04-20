#include <Arduino.h>
#include <Arduino_GFX_Library.h>
#include <WiFi.h>

#if __has_include("C:/Users/dirku/Documents/Arduino/libraries/GFX_Library_for_Arduino/examples/HelloWorldGfxfont/FreeMono8pt7b.h")
#include "C:/Users/dirku/Documents/Arduino/libraries/GFX_Library_for_Arduino/examples/HelloWorldGfxfont/FreeMono8pt7b.h"
#define METERSIM_HAS_TCP_WIDGET_FONT 1
#else
#define METERSIM_HAS_TCP_WIDGET_FONT 0
#endif

/*
  Simple ESP32-S3 serial test device for the Waveshare ESP32-S3-LCD-1.47 board.

  Notes:
  - Touch support has been removed on purpose.
  - The serial side is intentionally simple for testing tools and parsers.
  - The display code is split into small helpers so future UI changes stay easy.
*/

// DISPLAY: pin mapping from the Waveshare ESP32-S3-LCD-1.47 wiki.
constexpr int PIN_LCD_MOSI = 45;
constexpr int PIN_LCD_SCK = 40;
constexpr int PIN_LCD_CS = 42;
constexpr int PIN_LCD_DC = 41;
constexpr int PIN_LCD_RST = 39;
constexpr int PIN_LCD_BL = 48;

// RGB: onboard RGB LED control pin from the Waveshare board wiki.
constexpr int PIN_RGB = 38;

constexpr uint16_t LCD_WIDTH = 172;
constexpr uint16_t LCD_HEIGHT = 320;
constexpr uint16_t LCD_X_OFFSET = 34;
constexpr uint16_t LCD_Y_OFFSET = 0;

// SERIAL: serial and UI timing values.
constexpr uint32_t SERIAL_BAUD = 9600;
constexpr uint32_t SERIAL_WAIT_MS = 2500;
constexpr uint32_t STREAM_INTERVAL_MS = 750;
constexpr uint32_t ACTIVITY_FLASH_MS = 180;

// TCP/WIFI: hardcoded station credentials for local network testing.
// Replace these with the SSID and password of the Wi-Fi network both ESP32 boards should join.
constexpr char WIFI_STA_SSID[] = "WIFI_STA_SSID";
constexpr char WIFI_STA_PASSWORD[] = "WIFI_STA_PASSWORD";
constexpr uint16_t TCP_PORT = 5000;
constexpr uint32_t WIFI_RECONNECT_INTERVAL_MS = 5000;
constexpr uint32_t TCP_CONNECTED_FLASH_ON_MS = 90;
constexpr uint32_t TCP_CONNECTED_FLASH_GAP_MS = 120;
constexpr uint32_t TCP_CONNECTED_FLASH_PAUSE_MS = 800;
constexpr uint32_t TCP_RED_FLASH_STEP_MS = 130;

enum class OutputTarget : uint8_t {
  SERIAL_ONLY,
  TCP_ONLY,
  BOTH,
};

enum class TcpLedMode : uint8_t {
  BOOTING,
  OFFLINE,
  SERVER_READY,
  CLIENT_CONNECTED,
  DISCONNECT_FLASH,
};

struct ReplyCommand {
  const char *name;
  const char *response;
};

// SERIAL: three simple command/response pairs for testing.
const ReplyCommand kReplyCommands[] = {
    {"ALPHA", "GLIM"},
    {"BRAVO", "SNARP"},
    {"CHARLIE", "WOBBLE"},
};

struct DeviceState {
  bool streamEnabled = false;
  bool displayReady = false;
  bool displayDirty = true;
  bool displayLayoutDrawn = false;
  bool lastRxLampState = false;
  bool lastTxLampState = false;
  bool wifiConnected = false;
  bool tcpServerReady = false;
  bool tcpClientConnected = false;
  uint32_t lastStreamAt = 0;
  uint32_t lastWifiConnectAttemptAt = 0;
  uint32_t rxLedUntil = 0;
  uint32_t txLedUntil = 0;
  uint32_t tcpLedModeStartedAt = 0;
  uint32_t streamCount = 0;
  uint16_t widgetValue = 0;
  TcpLedMode tcpLedMode = TcpLedMode::BOOTING;
};

struct RgbColor {
  uint8_t red;
  uint8_t green;
  uint8_t blue;
};

// DISPLAY: this panel renders 16-bit colors with red/blue swapped, so encode
// display colors through this helper instead of using raw RGB565 constants.
constexpr uint16_t displayColor565(uint8_t red, uint8_t green, uint8_t blue) {
  return ((static_cast<uint16_t>(blue) & 0xF8) << 8) |
         ((static_cast<uint16_t>(green) & 0xFC) << 3) |
         (static_cast<uint16_t>(red) >> 3);
}

constexpr uint16_t COLOR_COBALT_BLUE = displayColor565(0x00, 0x47, 0xAB);
constexpr uint16_t COLOR_RX_GREEN = displayColor565(0x00, 0xD0, 0x32);
constexpr uint16_t COLOR_TX_YELLOW = displayColor565(0xFF, 0xD2, 0x00);

// RGB: this board's onboard LED appears to be wired with red/green swapped.
RgbColor toBoardLedColor(const RgbColor &logicalColor) {
  return {logicalColor.green, logicalColor.red, logicalColor.blue};
}

Arduino_DataBus *gBus =
    new Arduino_ESP32SPI(PIN_LCD_DC, PIN_LCD_CS, PIN_LCD_SCK, PIN_LCD_MOSI);
Arduino_GFX *gDisplay = new Arduino_ST7789(
    gBus,
    PIN_LCD_RST,
    0,
    false,
    LCD_WIDTH,
    LCD_HEIGHT,
    LCD_X_OFFSET,
    LCD_Y_OFFSET,
    LCD_X_OFFSET,
    LCD_Y_OFFSET);

DeviceState gState;
String gCommandBuffer;
String gTcpCommandBuffer;
WiFiServer gTcpServer(TCP_PORT);
WiFiClient gTcpClient;

bool rxLampActive() {
  return millis() < gState.rxLedUntil;
}

bool txLampActive() {
  return millis() < gState.txLedUntil;
}

void markRxActivity() {
  gState.rxLedUntil = millis() + ACTIVITY_FLASH_MS;
  gState.displayDirty = true;
}

void markTxActivity() {
  gState.txLedUntil = millis() + ACTIVITY_FLASH_MS;
  gState.displayDirty = true;
}

bool isTcpClientConnected() {
  return gState.tcpClientConnected && gTcpClient.connected();
}

bool isWifiConnected() {
  return WiFi.status() == WL_CONNECTED;
}

String ipToString(const IPAddress &ip) {
  return String(ip[0]) + "." + String(ip[1]) + "." + String(ip[2]) + "." + String(ip[3]);
}

void setRgbColor(const RgbColor &color) {
  const RgbColor boardColor = toBoardLedColor(color);
  neopixelWrite(PIN_RGB, boardColor.red, boardColor.green, boardColor.blue);
}

// RGB: TCP state LED rules.
void setTcpLedMode(TcpLedMode mode) {
  gState.tcpLedMode = mode;
  gState.tcpLedModeStartedAt = millis();
}

void sendLine(const String &message, OutputTarget target = OutputTarget::BOTH) {
  bool wroteOutput = false;

  if (target == OutputTarget::SERIAL_ONLY || target == OutputTarget::BOTH) {
    Serial.println(message);
    wroteOutput = true;
  }

  if ((target == OutputTarget::TCP_ONLY || target == OutputTarget::BOTH) && isTcpClientConnected()) {
    gTcpClient.println(message);
    wroteOutput = true;
  }

  if (wroteOutput) {
    markTxActivity();
  }
}

void updateTcpLed() {
  const uint32_t now = millis();

  switch (gState.tcpLedMode) {
    case TcpLedMode::BOOTING:
      setRgbColor({180, 90, 0});
      break;

    case TcpLedMode::OFFLINE:
      setRgbColor({80, 0, 0});
      break;

    case TcpLedMode::SERVER_READY:
      setRgbColor({0, 180, 0});
      break;

    case TcpLedMode::CLIENT_CONNECTED: {
      constexpr uint32_t cycleLength = TCP_CONNECTED_FLASH_ON_MS +
                                       TCP_CONNECTED_FLASH_GAP_MS +
                                       TCP_CONNECTED_FLASH_ON_MS +
                                       TCP_CONNECTED_FLASH_PAUSE_MS;
      const uint32_t phase =
          (now - gState.tcpLedModeStartedAt) % cycleLength;
      if (phase < TCP_CONNECTED_FLASH_ON_MS) {
        setRgbColor({0, 220, 0});
      } else if (phase < TCP_CONNECTED_FLASH_ON_MS + TCP_CONNECTED_FLASH_GAP_MS) {
        setRgbColor({0, 0, 0});
      } else if (phase < (TCP_CONNECTED_FLASH_ON_MS * 2) + TCP_CONNECTED_FLASH_GAP_MS) {
        setRgbColor({0, 220, 0});
      } else {
        setRgbColor({0, 0, 0});
      }
      break;
    }

    case TcpLedMode::DISCONNECT_FLASH: {
      const uint32_t elapsed = now - gState.tcpLedModeStartedAt;
      if (elapsed < TCP_RED_FLASH_STEP_MS) {
        setRgbColor({220, 0, 0});
      } else if (elapsed < TCP_RED_FLASH_STEP_MS * 2) {
        setRgbColor({0, 0, 0});
      } else if (elapsed < TCP_RED_FLASH_STEP_MS * 3) {
        setRgbColor({220, 0, 0});
      } else if (elapsed < TCP_RED_FLASH_STEP_MS * 4) {
        setRgbColor({0, 0, 0});
      } else {
        setTcpLedMode(TcpLedMode::SERVER_READY);
        setRgbColor({0, 180, 0});
      }
      break;
    }
  }
}

// SERIAL: help output stays small and predictable for testing.
void printHelp(OutputTarget target) {
  sendLine("help", target);
  sendLine("  ALPHA   -> GLIM", target);
  sendLine("  BRAVO   -> SNARP", target);
  sendLine("  CHARLIE -> WOBBLE", target);
  sendLine("  STREAM  -> toggle placeholder stream", target);
  sendLine("  HELP    -> show this list", target);
}

void printTcpConnectInfo() {
  if (!gState.tcpServerReady) {
    return;
  }

  sendLine("Wi-Fi SSID: " + String(WIFI_STA_SSID), OutputTarget::SERIAL_ONLY);
  sendLine("SerialHub TCP/IP target: " + ipToString(WiFi.localIP()) + ":" + String(TCP_PORT),
           OutputTarget::SERIAL_ONLY);
}

void sendStreamFrame() {
  gState.streamCount++;
  gState.widgetValue = static_cast<uint16_t>((gState.streamCount * 17) % 100);

  sendLine(
      String("--- STREAM | count=") + String(gState.streamCount) +
          " | value=" + String(gState.widgetValue) +
          " | tick=" + String(static_cast<unsigned long>(millis())) + " ---",
      OutputTarget::BOTH);
  gState.displayDirty = true;
}

void handleCommand(const String &rawCommand, OutputTarget replyTarget) {
  String command = rawCommand;
  command.trim();
  if (command.isEmpty()) {
    return;
  }

  gState.displayDirty = true;

  String upper = command;
  upper.toUpperCase();

  if (upper == "HELP") {
    printHelp(replyTarget);
    return;
  }

  if (upper == "STREAM") {
    gState.streamEnabled = !gState.streamEnabled;
    gState.lastStreamAt = millis();
    sendLine(gState.streamEnabled ? "STREAM ON" : "STREAM OFF", replyTarget);
    return;
  }

  for (const ReplyCommand &entry : kReplyCommands) {
    if (upper == entry.name) {
      sendLine(entry.response, replyTarget);
      return;
    }
  }

  sendLine("UNKNOWN COMMAND", replyTarget);
}

void readCommandInput(char incoming, String &buffer, OutputTarget replyTarget) {
  if (incoming == '\n' || incoming == '\r') {
    if (!buffer.isEmpty()) {
      handleCommand(buffer, replyTarget);
      buffer = "";
    }
    return;
  }

  if (buffer.length() < 64) {
    buffer += incoming;
  }
}

void readSerialInput() {
  while (Serial.available() > 0) {
    markRxActivity();
    const char incoming = static_cast<char>(Serial.read());
    readCommandInput(incoming, gCommandBuffer, OutputTarget::SERIAL_ONLY);
  }
}

void updateStream() {
  if (!gState.streamEnabled) {
    return;
  }

  const uint32_t now = millis();
  if (now - gState.lastStreamAt < STREAM_INTERVAL_MS) {
    return;
  }

  gState.lastStreamAt = now;
  sendStreamFrame();
}

// TCP/WIFI: join a local Wi-Fi network and expose the same command set over a single TCP client.
void handleTcpClientDisconnected() {
  if (gTcpClient) {
    gTcpClient.stop();
  }

  gState.tcpClientConnected = false;
  gTcpCommandBuffer = "";
  gState.displayDirty = true;
  setTcpLedMode(TcpLedMode::DISCONNECT_FLASH);
  sendLine("TCP client disconnected", OutputTarget::SERIAL_ONLY);
}

void handleTcpClientConnected(WiFiClient &incomingClient) {
  gTcpClient = incomingClient;
  gTcpClient.setNoDelay(true);

  gState.tcpClientConnected = true;
  gState.displayDirty = true;
  setTcpLedMode(TcpLedMode::CLIENT_CONNECTED);
  sendLine("TCP client connected: " + ipToString(gTcpClient.remoteIP()),
           OutputTarget::SERIAL_ONLY);
}

void beginWifiConnection() {
  WiFi.begin(WIFI_STA_SSID, WIFI_STA_PASSWORD);
  gState.lastWifiConnectAttemptAt = millis();
  gState.displayDirty = true;
  sendLine("Wi-Fi connect requested: " + String(WIFI_STA_SSID), OutputTarget::SERIAL_ONLY);
}

void initTcpServer() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.disconnect();
  gState.wifiConnected = false;
  gState.tcpServerReady = false;
  gState.displayDirty = true;
  beginWifiConnection();
}

void updateTcpServer() {
  const bool wifiNowConnected = isWifiConnected();

  if (wifiNowConnected != gState.wifiConnected) {
    gState.wifiConnected = wifiNowConnected;
    gState.displayDirty = true;

    if (wifiNowConnected) {
      sendLine("Wi-Fi connected: " + ipToString(WiFi.localIP()), OutputTarget::SERIAL_ONLY);
    } else {
      if (gTcpClient) {
        gTcpClient.stop();
      }
      gState.tcpClientConnected = false;
      gTcpCommandBuffer = "";
      gState.tcpServerReady = false;
      sendLine("Wi-Fi disconnected", OutputTarget::SERIAL_ONLY);
      setTcpLedMode(TcpLedMode::OFFLINE);
    }
  }

  if (!wifiNowConnected) {
    if (gState.tcpLedMode != TcpLedMode::OFFLINE) {
      setTcpLedMode(TcpLedMode::OFFLINE);
    }

    if (millis() - gState.lastWifiConnectAttemptAt >= WIFI_RECONNECT_INTERVAL_MS) {
      beginWifiConnection();
    }
    return;
  }

  if (!gState.tcpServerReady) {
    gTcpServer.begin();
    gTcpServer.setNoDelay(true);
    gState.tcpServerReady = true;
    gState.displayDirty = true;
    setTcpLedMode(TcpLedMode::SERVER_READY);

    sendLine("TCP IP: " + ipToString(WiFi.localIP()), OutputTarget::SERIAL_ONLY);
    sendLine("TCP port open: " + String(TCP_PORT), OutputTarget::SERIAL_ONLY);
    printTcpConnectInfo();
  }

  WiFiClient incomingClient = gTcpServer.available();
  if (incomingClient) {
    if (isTcpClientConnected()) {
      incomingClient.stop();
    } else {
      handleTcpClientConnected(incomingClient);
    }
  }

  if (isTcpClientConnected()) {
    while (gTcpClient.available() > 0) {
      markRxActivity();
      const char incoming = static_cast<char>(gTcpClient.read());
      readCommandInput(incoming, gTcpCommandBuffer, OutputTarget::TCP_ONLY);
    }

    if (!gTcpClient.connected()) {
      handleTcpClientDisconnected();
    }
    return;
  }

  if (gState.tcpClientConnected) {
    handleTcpClientDisconnected();
  }
}

// DISPLAY: small helpers keep each section isolated and easy to edit later.
void drawLamp(int16_t x, int16_t y, bool active, const char *label, uint16_t activeColor) {
  const uint16_t fillColor = active ? activeColor : RGB565_DARKGREY;
  gDisplay->fillCircle(x, y, 15, fillColor);
  gDisplay->drawCircle(x, y, 15, RGB565_WHITE);
  gDisplay->setTextSize(2);
  gDisplay->setTextColor(RGB565_WHITE);
  gDisplay->setCursor(x - 7, y + 36);
  gDisplay->print(label);
}

void drawHeader() {
  const int16_t screenW = gDisplay->width();
  gDisplay->fillRect(0, 0, screenW, 40, COLOR_COBALT_BLUE);

  gDisplay->setTextColor(RGB565_WHITE);
  gDisplay->setTextSize(2);
  gDisplay->setCursor(20, 10);
  gDisplay->print("SERIAL DEV");
}

void drawPlaceholderWidget() {
  const int16_t x = 8;
  const int16_t y = 52;
  const int16_t w = gDisplay->width() - 16;
  const int16_t h = 102;
  const uint16_t liveValue = gState.widgetValue;

  gDisplay->drawRect(x, y, w, h, RGB565_WHITE);
  gDisplay->fillRect(x + 1, y + 1, w - 2, h - 2, 0x0841);

  gDisplay->setTextSize(2);
  gDisplay->setTextColor(RGB565_WHITE);
  // gDisplay->setCursor(x + 10, y + 10);
  // gDisplay->print("PLACEHOLDER WIDGET");

  drawLamp(x + 40, y + 30, rxLampActive(), "RX", COLOR_RX_GREEN);
  drawLamp(x + 110, y + 30, txLampActive(), "TX", COLOR_TX_YELLOW);

}

void drawTcpWidget() {
  const int16_t x = 8;
  const int16_t y = 166;
  const int16_t w = gDisplay->width() - 16;
  const int16_t h = 112;
  const String clientState = !gState.wifiConnected ? "WIFI..." :
                             isTcpClientConnected() ? "CONNECTED" :
                             gState.tcpServerReady ? "WAITING" : "STARTING";
  const String ipLine = gState.wifiConnected ? ipToString(WiFi.localIP()) : "connecting...";
  const String portLine = gState.wifiConnected ? String(TCP_PORT) : "-";
  const String ssidLine = String(WIFI_STA_SSID);

  gDisplay->drawRect(x, y, w, h, RGB565_WHITE);
  gDisplay->fillRect(x + 1, y + 1, w - 2, h - 2, 0x18C3);

#if METERSIM_HAS_TCP_WIDGET_FONT
  gDisplay->setFont(&FreeMono8pt7b);
  gDisplay->setTextSize(1);
  gDisplay->setTextColor(RGB565_WHITE);
  gDisplay->setCursor(x + 10, y + 20);
  gDisplay->print("TCP:");
  gDisplay->setCursor(x + 48, y + 20);
  gDisplay->print(clientState);

  gDisplay->setCursor(x + 10, y + 42);
  gDisplay->print(ipLine);

  gDisplay->setCursor(x + 10, y + 64);
  gDisplay->print(portLine);

  gDisplay->setCursor(x + 10, y + 86);
  gDisplay->print(ssidLine);
  gDisplay->setFont();
#else
  gDisplay->setTextSize(1);
  gDisplay->setTextColor(RGB565_WHITE);
  gDisplay->setCursor(x + 10, y + 10);
  gDisplay->print("TCP:");
  gDisplay->setCursor(x + 40, y + 10);
  gDisplay->print(clientState);

  gDisplay->setTextSize(1);
  gDisplay->setCursor(x + 10, y + 36);
  gDisplay->print(ipLine);

  gDisplay->setCursor(x + 10, y + 52);
  gDisplay->print(portLine);

  gDisplay->setCursor(x + 10, y + 68);
  gDisplay->print(ssidLine);
#endif
}

void drawFooter() {
  gDisplay->setTextSize(2);
  gDisplay->setTextColor(RGB565_WHITE);
  gDisplay->setCursor(10, 290);
  gDisplay->print("> HELP/help");

  // gDisplay->setCursor(10, 292);
  // gDisplay->print("RGB cycle active");
}

void renderDisplay() {
  if (!gState.displayReady) {
    return;
  }

  if (!gState.displayLayoutDrawn) {
    gDisplay->fillScreen(RGB565_BLACK);
    drawHeader();
    drawFooter();
    gState.displayLayoutDrawn = true;
  }

  drawPlaceholderWidget();
  drawTcpWidget();

  gState.lastRxLampState = rxLampActive();
  gState.lastTxLampState = txLampActive();
  gState.displayDirty = false;
}

void updateDisplay() {
  if (!gState.displayReady) {
    return;
  }

  const bool rxNow = rxLampActive();
  const bool txNow = txLampActive();
  if (rxNow != gState.lastRxLampState || txNow != gState.lastTxLampState) {
    gState.displayDirty = true;
  }

  if (gState.displayDirty) {
    renderDisplay();
  }
}

void initDisplay() {
  pinMode(PIN_LCD_BL, OUTPUT);
  digitalWrite(PIN_LCD_BL, HIGH);

  gState.displayReady = gDisplay->begin();
  if (!gState.displayReady) {
    return;
  }

  gDisplay->setRotation(0);
  gDisplay->setTextWrap(false);
  gState.displayLayoutDrawn = false;
  gState.displayDirty = true;
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  pinMode(PIN_RGB, OUTPUT);
  setTcpLedMode(TcpLedMode::BOOTING);
  updateTcpLed();

  const uint32_t waitStart = millis();
  while (!Serial && (millis() - waitStart < SERIAL_WAIT_MS)) {
    delay(10);
  }

  randomSeed(static_cast<uint32_t>(micros()));

  initDisplay();
  initTcpServer();
  sendLine("Startup String - Hello!", OutputTarget::SERIAL_ONLY);
}

void loop() {
  readSerialInput();
  updateTcpServer();
  updateStream();
  updateTcpLed();
  updateDisplay();

  // delay(5);
}

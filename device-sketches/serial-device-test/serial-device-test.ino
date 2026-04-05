/*
  ESP32 Serial Test Device
  Board: ESP32-WROOM (CH340 USB)
  Baud: 115200

  Features:
  - Multiple modes: ECHO, STREAM, STRUCTURED, FRAME, NOISE
  - Command interface
  - Non-blocking timing (millis)
  - Error injection
*/

#include <Arduino.h>

enum Mode {
  MODE_ECHO,
  MODE_STREAM,
  MODE_STRUCTURED,
  MODE_FRAME,
  MODE_NOISE
};

enum CommandCase {
  CMD_MODE,
  CMD_PING,
  CMD_STATUS,
  CMD_INTERVAL,
  CMD_ERRORS_ON,
  CMD_ERRORS_OFF,
  CMD_SILENT,
  CMD_BURST,
  CMD_HEARTBEAT_ON,
  CMD_HEARTBEAT_OFF,
  CMD_HELP,
  CMD_UNKNOWN
};

Mode currentMode = MODE_STREAM;

String inputBuffer = "";

unsigned long lastHeartbeat = 0;
unsigned long lastStream = 0;
unsigned long intervalMs = 1000;

bool errorInjection = false;
bool heartbeatEnabled = false;
unsigned long silentUntil = 0;

// Utility
float randf(float minVal, float maxVal) {
  return minVal + ((float)random(0, 10000) / 10000.0) * (maxVal - minVal);
}

const char* modeName(Mode mode) {
  switch (mode) {
    case MODE_ECHO:
      return "ECHO";
    case MODE_STREAM:
      return "STREAM";
    case MODE_STRUCTURED:
      return "STRUCTURED";
    case MODE_FRAME:
      return "FRAME";
    case MODE_NOISE:
      return "NOISE";
    default:
      return "UNKNOWN";
  }
}

void printCommandMenu() {
  Serial.println("[MENU] Commands:");
  Serial.println("  HELP");
  Serial.println("  MODE:ECHO|STREAM|STRUCTURED|FRAME|NOISE");
  Serial.println("  PING");
  Serial.println("  STATUS");
  Serial.println("  INTERVAL:<ms>");
  Serial.println("  ERRORS:ON|OFF");
  Serial.println("  SILENT:<ms>");
  Serial.println("  BURST:<count>");
  Serial.println("  HEARTBEAT:ON|OFF");
}

// ---------- Command Handling ----------
bool parseMode(const String& modeStr, Mode& modeOut) {
  if (modeStr == "ECHO") {
    modeOut = MODE_ECHO;
    return true;
  }
  if (modeStr == "STREAM") {
    modeOut = MODE_STREAM;
    return true;
  }
  if (modeStr == "STRUCTURED") {
    modeOut = MODE_STRUCTURED;
    return true;
  }
  if (modeStr == "FRAME") {
    modeOut = MODE_FRAME;
    return true;
  }
  if (modeStr == "NOISE") {
    modeOut = MODE_NOISE;
    return true;
  }
  return false;
}

CommandCase classifyCommand(const String& cmdUpper) {
  if (cmdUpper == "PING") return CMD_PING;
  if (cmdUpper == "STATUS") return CMD_STATUS;
  if (cmdUpper == "ERRORS:ON") return CMD_ERRORS_ON;
  if (cmdUpper == "ERRORS:OFF") return CMD_ERRORS_OFF;
  if (cmdUpper == "HEARTBEAT:ON") return CMD_HEARTBEAT_ON;
  if (cmdUpper == "HEARTBEAT:OFF") return CMD_HEARTBEAT_OFF;
  if (cmdUpper == "HELP" || cmdUpper == "MENU") return CMD_HELP;
  if (cmdUpper.startsWith("MODE:")) return CMD_MODE;
  if (cmdUpper.startsWith("INTERVAL:")) return CMD_INTERVAL;
  if (cmdUpper.startsWith("SILENT:")) return CMD_SILENT;
  if (cmdUpper.startsWith("BURST:")) return CMD_BURST;
  return CMD_UNKNOWN;
}

void processCommand(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;

  String cmdUpper = cmd;
  cmdUpper.toUpperCase();

  Serial.printf("[CMD] %s\n", cmd.c_str());

  switch (classifyCommand(cmdUpper)) {
    case CMD_MODE: {
      Mode parsedMode = currentMode;
      String modeToken = cmdUpper.substring(5);
      modeToken.trim();
      if (parseMode(modeToken, parsedMode)) {
        currentMode = parsedMode;
        Serial.printf("[SYS] Mode changed to %s\n", modeName(currentMode));
      } else {
        Serial.printf("[ERR] Unknown mode: %s\n", modeToken.c_str());
      }
      break;
    }

    case CMD_PING:
      Serial.println("PONG");
      break;

    case CMD_STATUS:
      Serial.printf(
          "MODE:%s,INTERVAL:%lu,HEARTBEAT:%s,UPTIME:%lu\n",
          modeName(currentMode),
          intervalMs,
          heartbeatEnabled ? "ON" : "OFF",
          millis());
      break;

    case CMD_INTERVAL:
      intervalMs = cmdUpper.substring(9).toInt();
      Serial.printf("[SYS] Interval set to %lu ms\n", intervalMs);
      break;

    case CMD_ERRORS_ON:
      errorInjection = true;
      Serial.println("[SYS] Error injection ON");
      break;

    case CMD_ERRORS_OFF:
      errorInjection = false;
      Serial.println("[SYS] Error injection OFF");
      break;

    case CMD_SILENT: {
      unsigned long dur = cmdUpper.substring(7).toInt();
      silentUntil = millis() + dur;
      Serial.printf("[SYS] Silent for %lu ms\n", dur);
      break;
    }

    case CMD_BURST: {
      int count = cmdUpper.substring(6).toInt();
      for (int i = 0; i < count; i++) {
        Serial.printf("BURST_MSG_%d\n", i);
      }
      break;
    }

    case CMD_HEARTBEAT_ON:
      heartbeatEnabled = true;
      lastHeartbeat = millis();
      Serial.println("[SYS] Heartbeat ON");
      break;

    case CMD_HEARTBEAT_OFF:
      heartbeatEnabled = false;
      Serial.println("[SYS] Heartbeat OFF");
      break;

    case CMD_HELP:
      printCommandMenu();
      break;

    case CMD_UNKNOWN:
    default:
      Serial.println("[ERR] Unknown command. Type HELP for menu.");
      break;
  }
}

// ---------- Serial Input ----------
void handleSerialInput() {
  while (Serial.available()) {
    char c = Serial.read();

    if (c == '\n' || c == '\r') {
      if (inputBuffer.length() > 0) {
        processCommand(inputBuffer);
        inputBuffer = "";
      }
    } else {
      inputBuffer += c;
    }
  }
}

// ---------- Output Modes ----------

void sendHeartbeat() {
  Serial.printf("[HB] uptime=%lu\n", millis());
}

void modeEcho() {
  // handled directly in command processor (echo behavior optional)
}

void modeStream() {
  float temp = randf(20.0, 30.0);
  float hum = randf(40.0, 70.0);
  float volt = randf(220.0, 240.0);

  Serial.printf("TEMP:%.2f,HUM:%.2f,VOLT:%.2f\n", temp, hum, volt);
}

void modeStructured() {
  float temp = randf(20.0, 30.0);
  float current = randf(1.0, 10.0);

  if (errorInjection && random(0, 5) == 0) {
    Serial.printf("{\"ts\":%lu,\"error\":\"sensor_timeout\"}\n", millis());
    return;
  }

  Serial.printf("{\"ts\":%lu,\"temp\":%.2f,\"current\":%.2f,\"status\":\"OK\"}\n",
                millis(), temp, current);
}

String fakeChecksum(String payload) {
  int sum = 0;
  for (char c : payload) sum += c;
  sum = sum % 256;

  char buf[5];
  sprintf(buf, "%02X", sum);
  return String(buf);
}

void modeFrame() {
  String payload = "|DATA:" + String(random(10000, 99999)) + "|";
  String chk = fakeChecksum(payload);

  String frame = "~" + String(payload.length()) + payload + chk + "#";

  if (errorInjection && random(0, 4) == 0) {
    // corrupt frame
    frame = frame.substring(0, frame.length() - 2);
  }

  Serial.println(frame);
}

void modeNoise() {
  int len = random(10, 40);
  String s = "";

  for (int i = 0; i < len; i++) {
    char c = random(33, 126);
    s += c;
  }

  Serial.println(s);
}

// ---------- Setup ----------
void setup() {
  Serial.begin(115200);
  delay(500);

  randomSeed(esp_random());

  Serial.println("[SYS] ESP32 Serial Test Device Ready");
  Serial.println("[SYS] Heartbeat is OFF by default.");
  printCommandMenu();
}

// ---------- Main Loop ----------
void loop() {
  handleSerialInput();

  if (millis() < silentUntil) return;

  unsigned long now = millis();

  // Heartbeat (disabled by default, command controlled)
  if (heartbeatEnabled && (now - lastHeartbeat >= 1000)) {
    lastHeartbeat = now;
    sendHeartbeat();
  }

  // Mode output
  if (now - lastStream >= intervalMs) {
    lastStream = now;

    switch (currentMode) {
      case MODE_ECHO:
        // Echo handled via command input
        break;

      case MODE_STREAM:
        modeStream();
        break;

      case MODE_STRUCTURED:
        modeStructured();
        break;

      case MODE_FRAME:
        modeFrame();
        break;

      case MODE_NOISE:
        modeNoise();
        break;
    }
  }
}

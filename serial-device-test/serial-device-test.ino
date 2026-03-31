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

Mode currentMode = MODE_STREAM;

String inputBuffer = "";

unsigned long lastHeartbeat = 0;
unsigned long lastStream = 0;
unsigned long intervalMs = 1000;

bool errorInjection = false;
unsigned long silentUntil = 0;

// Utility
float randf(float minVal, float maxVal) {
  return minVal + ((float)random(0, 10000) / 10000.0) * (maxVal - minVal);
}

// ---------- Command Handling ----------
void setMode(String modeStr) {
  modeStr.toUpperCase();

  if (modeStr == "ECHO") currentMode = MODE_ECHO;
  else if (modeStr == "STREAM") currentMode = MODE_STREAM;
  else if (modeStr == "STRUCTURED") currentMode = MODE_STRUCTURED;
  else if (modeStr == "FRAME") currentMode = MODE_FRAME;
  else if (modeStr == "NOISE") currentMode = MODE_NOISE;

  Serial.printf("[SYS] Mode changed to %s\n", modeStr.c_str());
}

void processCommand(String cmd) {
  cmd.trim();
  Serial.printf("[CMD] %s\n", cmd.c_str());

  if (cmd.startsWith("MODE:")) {
    setMode(cmd.substring(5));
  }
  else if (cmd == "PING") {
    Serial.println("PONG");
  }
  else if (cmd == "STATUS") {
    Serial.printf("MODE:%d\n", currentMode);
  }
  else if (cmd.startsWith("INTERVAL:")) {
    intervalMs = cmd.substring(9).toInt();
    Serial.printf("[SYS] Interval set to %lu ms\n", intervalMs);
  }
  else if (cmd == "ERRORS:ON") {
    errorInjection = true;
    Serial.println("[SYS] Error injection ON");
  }
  else if (cmd == "ERRORS:OFF") {
    errorInjection = false;
    Serial.println("[SYS] Error injection OFF");
  }
  else if (cmd.startsWith("SILENT:")) {
    unsigned long dur = cmd.substring(7).toInt();
    silentUntil = millis() + dur;
    Serial.printf("[SYS] Silent for %lu ms\n", dur);
  }
  else if (cmd.startsWith("BURST:")) {
    int count = cmd.substring(6).toInt();
    for (int i = 0; i < count; i++) {
      Serial.printf("BURST_MSG_%d\n", i);
    }
  }
}

// ---------- Serial Input ----------
void handleSerialInput() {
  while (Serial.available()) {
    char c = Serial.read();

    if (c == '\n') {
      processCommand(inputBuffer);
      inputBuffer = "";
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
}

// ---------- Main Loop ----------
void loop() {
  handleSerialInput();

  if (millis() < silentUntil) return;

  unsigned long now = millis();

  // Heartbeat
  if (now - lastHeartbeat >= 1000) {
    lastHeartbeat = now;
    if (currentMode != MODE_NOISE) {
      sendHeartbeat();
    }
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
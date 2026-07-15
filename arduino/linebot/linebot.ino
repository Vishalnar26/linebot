// LineBot Arduino Firmware
// Hardware: Arduino Uno + L298N motor driver + 3× TCRT5000 line sensors
//
// Serial protocol (115200 baud):
//   Arduino → PC  every 50 ms:  D:L,C,R|A:L,C,R\n
//     D = digital readings  (0 = white / LED on,  1 = black / LED off)
//     A = analog  readings  (0–1023)
//     Order: Left, Center, Right
//
//   PC → Arduino on demand:     P:left_pwm,right_pwm\n
//     signed integers, range −255 … +255
//     positive = forward,  negative = backward
//
// Safety: motors stop automatically if no P: command is received
//         within COMMAND_TIMEOUT ms.

// ─── Pin definitions ─────────────────────────────────────────────────────────

// TCRT5000 sensors  (black = 1, white = 0 on digital pin)
const int LEFT_SENSOR_D   = 3;    // UNO D3   (from spec: UNO D3)
const int CENTER_SENSOR_D = 4;    // UNO D4
const int RIGHT_SENSOR_D  = 2;    // UNO D2

const int LEFT_SENSOR_A   = A1;   // UNO A1
const int CENTER_SENSOR_A = A2;   // UNO A2
const int RIGHT_SENSOR_A  = A0;   // UNO A0

// L298N motor driver
// Left  motor: IN1, IN2, ENA
// Right motor: IN3, IN4, ENB
//
// Truth table (from hardware spec):
//   Forward:   IN1=LOW,  IN2=HIGH, IN3=HIGH, IN4=LOW
//   Backward:  IN1=HIGH, IN2=LOW,  IN3=LOW,  IN4=HIGH
//   Turn CW:   IN1=HIGH, IN2=LOW,  IN3=HIGH, IN4=LOW   (L back, R fwd)
//   Turn CCW:  IN1=LOW,  IN2=HIGH, IN3=LOW,  IN4=HIGH  (L fwd,  R back)
const int IN1 = 6;    // Left  motor direction A
const int IN2 = 7;    // Left  motor direction B
const int IN3 = 8;    // Right motor direction A
const int IN4 = 9;    // Right motor direction B
const int ENA = 5;    // Left  motor PWM (D5 — hardware PWM on Uno)
const int ENB = 10;   // Right motor PWM (D10 — hardware PWM on Uno)

// ─── Timing constants ─────────────────────────────────────────────────────────
const unsigned long SENSOR_INTERVAL = 50;    // ms  (20 Hz publish rate)
const unsigned long COMMAND_TIMEOUT = 500;   // ms  (safety stop threshold)

// ─── State ────────────────────────────────────────────────────────────────────
unsigned long lastSensorTime  = 0;
unsigned long lastCommandTime = 0;
bool          commandReceived = false;
String        serialBuffer    = "";

// ─── Motor control ────────────────────────────────────────────────────────────
// leftPwm / rightPwm: +255 = full forward,  -255 = full backward,  0 = stop
void setMotors(int leftPwm, int rightPwm) {
  leftPwm  = constrain(leftPwm,  -255, 255);
  rightPwm = constrain(rightPwm, -255, 255);

  // Left motor
  if (leftPwm > 0) {
    digitalWrite(IN1, LOW);
    digitalWrite(IN2, HIGH);
  } else if (leftPwm < 0) {
    digitalWrite(IN1, HIGH);
    digitalWrite(IN2, LOW);
  } else {
    digitalWrite(IN1, LOW);
    digitalWrite(IN2, LOW);
  }
  analogWrite(ENA, abs(leftPwm));

  // Right motor
  if (rightPwm > 0) {
    digitalWrite(IN3, HIGH);
    digitalWrite(IN4, LOW);
  } else if (rightPwm < 0) {
    digitalWrite(IN3, LOW);
    digitalWrite(IN4, HIGH);
  } else {
    digitalWrite(IN3, LOW);
    digitalWrite(IN4, LOW);
  }
  analogWrite(ENB, abs(rightPwm));
}

// ─── Command parser ───────────────────────────────────────────────────────────
// Expected format: P:left_pwm,right_pwm
void parseCommand(const String &cmd) {
  if (cmd.length() < 4) return;
  if (cmd.charAt(0) != 'P' || cmd.charAt(1) != ':') return;

  String payload  = cmd.substring(2);
  int    commaIdx = payload.indexOf(',');
  if (commaIdx < 1) return;   // malformed — no comma

  int leftPwm  = payload.substring(0, commaIdx).toInt();
  int rightPwm = payload.substring(commaIdx + 1).toInt();

  setMotors(leftPwm, rightPwm);
  lastCommandTime = millis();
  commandReceived = true;
}

// ─── Non-blocking serial reader ───────────────────────────────────────────────
void readSerial() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n') {
      serialBuffer.trim();
      if (serialBuffer.length() > 0) {
        parseCommand(serialBuffer);
      }
      serialBuffer = "";
    } else if (c != '\r') {
      // Guard against unbounded buffer growth (max command length is ~16 chars)
      if (serialBuffer.length() < 32) {
        serialBuffer += c;
      } else {
        serialBuffer = "";   // discard garbage
      }
    }
  }
}

// ─── Setup ────────────────────────────────────────────────────────────────────
void setup() {
  // Motor driver pins
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);
  pinMode(ENA, OUTPUT);
  pinMode(ENB, OUTPUT);
  setMotors(0, 0);   // ensure motors are stopped at startup

  // Sensor digital pins — sensors have onboard pull-up; INPUT is sufficient
  pinMode(LEFT_SENSOR_D,   INPUT);
  pinMode(CENTER_SENSOR_D, INPUT);
  pinMode(RIGHT_SENSOR_D,  INPUT);

  Serial.begin(115200);
}

// ─── Main loop ────────────────────────────────────────────────────────────────
void loop() {
  // 1. Process any incoming serial commands (non-blocking)
  readSerial();

  // 2. Safety timeout — stop motors if ROS2 side goes silent
  if (commandReceived && (millis() - lastCommandTime > COMMAND_TIMEOUT)) {
    setMotors(0, 0);
  }

  // 3. Publish sensor readings at 20 Hz
  if (millis() - lastSensorTime >= SENSOR_INTERVAL) {
    lastSensorTime = millis();

    int lDig = digitalRead(LEFT_SENSOR_D);
    int cDig = digitalRead(CENTER_SENSOR_D);
    int rDig = digitalRead(RIGHT_SENSOR_D);
    int lAna = analogRead(LEFT_SENSOR_A);
    int cAna = analogRead(CENTER_SENSOR_A);
    int rAna = analogRead(RIGHT_SENSOR_A);

    // Format: D:L,C,R|A:L,C,R
    Serial.print("D:");
    Serial.print(lDig);
    Serial.print(",");
    Serial.print(cDig);
    Serial.print(",");
    Serial.print(rDig);
    Serial.print("|A:");
    Serial.print(lAna);
    Serial.print(",");
    Serial.print(cAna);
    Serial.print(",");
    Serial.println(rAna);   // println appends \r\n
  }
}

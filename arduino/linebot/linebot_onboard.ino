// LineBot — Smooth Analog PID Line-Following Sketch
// Hardware: Arduino Uno + L298N motor driver + 3× TCRT5000 line sensors

// ─── Pin definitions ─────────────────────────────────────────────────────────
// We only need the Analog pins for reading the line now!
const int LEFT_SENSOR_A   = A1;   // UNO A1 
const int CENTER_SENSOR_A = A2;   // UNO A2
const int RIGHT_SENSOR_A  = A0;   // UNO A0

const int IN1 = 6;    // Left  motor direction A
const int IN2 = 7;    // Left  motor direction B
const int IN3 = 8;    // Right motor direction A
const int IN4 = 9;    // Right motor direction B
const int ENA = 5;    // Left  motor PWM (D5 — hardware PWM on Uno)
const int ENB = 10;   // Right motor PWM (D10 — hardware PWM on Uno)

// ─── Tuning / runtime parameters ─────────────────────────────────────────────
int BASE_PWM = 100;         // Slightly lower base speed for smoother testing
const int MAX_PWM = 255;

// PID gains (These will feel much smoother with analog data!)
float Kp = 150.0;           // Proportional gain (adjusted for analog scale)
float Ki = 0.0;             // Integral gain
float Kd = 25.0;            // Derivative gain (adjusted for analog scale)

// Maximum differential correction (in PWM units)
const int MAX_CORRECTION = 100;

// Lost-line behavior: 0 = stop, 1 = smart spin-search
const int LOST_BEHAVIOR = 1;

// Threshold to determine if we have lost the line completely
// If the sum of all analog readings is below this, we assume we are off the line.
const int LINE_THRESHOLD = 150; 

// Timing & State
unsigned long lastTime = 0;
float integral = 0.0;
float last_error = 0.0;
float last_derivative = 0.0; 

// Helpers
int clampInt(int v, int lo, int hi) { return v < lo ? lo : (v > hi ? hi : v); }

void setMotors(int leftPwm, int rightPwm) {
  leftPwm  = clampInt(leftPwm, -MAX_PWM, MAX_PWM);
  rightPwm = clampInt(rightPwm, -MAX_PWM, MAX_PWM);

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

// Read analog sensors and compute a smooth error value in range [-1..+1]
float readLineError() {
  float left  = analogRead(LEFT_SENSOR_A);
  float center = analogRead(CENTER_SENSOR_A);
  float right = analogRead(RIGHT_SENSOR_A);

  float total = left + center + right;

  // If the sensors don't see enough dark/reflected value, the line is lost
  if (total < LINE_THRESHOLD) {
    return NAN; 
  }

  // Weighted average calculation
  // (Right - Left) / Total gives us a smooth range from -1.0 to +1.0
  float err = (right - left) / total;
  return err;
}

void setup() {
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);
  pinMode(ENA, OUTPUT);
  pinMode(ENB, OUTPUT);

  // Note: Analog pins do not strictly require pinMode, but it's good practice
  pinMode(LEFT_SENSOR_A, INPUT);
  pinMode(CENTER_SENSOR_A, INPUT);
  pinMode(RIGHT_SENSOR_A, INPUT);

  Serial.begin(115200);
  delay(100);
  setMotors(0,0);
  lastTime = millis();
}

void loop() {
  unsigned long now = millis();
  float dt = (now - lastTime) / 1000.0; // seconds
  if (dt <= 0) dt = 0.001;
  lastTime = now;

  float error = readLineError();
  
  if (!isnan(error)) {
    // PID compute
    integral += error * dt;
    float derivative = (error - last_error) / dt;
    float output = Kp * error + Ki * integral + Kd * derivative;
    
    last_derivative = derivative;
    last_error = error;

    // Scale PID output to PWM correction
    int correction = (int)round(output);
    correction = clampInt(correction, -MAX_CORRECTION, MAX_CORRECTION);

    int leftPwm = BASE_PWM + correction;
    int rightPwm = BASE_PWM - correction;

    leftPwm = clampInt(leftPwm, -MAX_PWM, MAX_PWM);
    rightPwm = clampInt(rightPwm, -MAX_PWM, MAX_PWM);

    setMotors(leftPwm, rightPwm);

    // Command Parsing for Serial Tuning
    if (Serial.available() > 0) {
      String cmd = Serial.readStringUntil('\n');
      cmd.trim();
      if (cmd.length() > 0) {
        if (cmd.startsWith("BASE:")) BASE_PWM = clampInt(cmd.substring(5).toInt(), 0, MAX_PWM);
        else if (cmd.startsWith("Kp:")) Kp = cmd.substring(3).toFloat();
        else if (cmd.startsWith("Ki:")) Ki = cmd.substring(3).toFloat();
        else if (cmd.startsWith("Kd:")) Kd = cmd.substring(3).toFloat();
        else if (cmd == "STOP") { setMotors(0,0); }
      }
    }

    // Print periodic telemetry
    static unsigned long lastPrint = 0;
    if (now - lastPrint > 150) {
      lastPrint = now;
      int la = analogRead(LEFT_SENSOR_A);
      int ca = analogRead(CENTER_SENSOR_A);
      int ra = analogRead(RIGHT_SENSOR_A);
      Serial.print("A_Raw:");
      Serial.print(la); Serial.print(','); Serial.print(ca); Serial.print(','); Serial.print(ra);
      Serial.print(" E:"); Serial.print(error, 3);
      Serial.print(" P:"); Serial.print((int)round(Kp * error));
      Serial.print(" D:"); Serial.print((int)round(Kd * last_derivative));
      Serial.print(" PWM:"); Serial.print(leftPwm); Serial.print(','); Serial.println(rightPwm);
    }

  } else {
    // Smart Lost line handling
    integral = 0.0; 
    
    if (LOST_BEHAVIOR == 0) {
      setMotors(0,0);
    } else {
      // Look at the last known error to decide which way to spin
      if (last_error < 0) {
        // Line was last seen on the LEFT, spin left
        setMotors(-BASE_PWM/2, BASE_PWM);
      } else {
        // Line was last seen on the RIGHT, spin right
        setMotors(BASE_PWM, -BASE_PWM/2);
      }
    }

    // quick telemetry when lost
    static unsigned long lastLost = 0;
    if (now - lastLost > 500) {
      lastLost = now;
      Serial.println("LOST - Searching...");
    }
  }
}
#include <Arduino.h>
#include <WiFi.h>
#include <FastAccelStepper.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include <math.h>

// =====================================================
// ESP32-S3 GANTRY TCP V9.3.0 FREERTOS APP-COMPATIBLE
// Nen tu v9.2.15I dang on dinh, tach FreeRTOS nhung giu app GitHub.
//   - Khong sua app. Khong dung READY_COLOR/DONE handshake tren app.
//   - Lenh JOG tra ACK ngay, khong block Serial/TCP lam app tu ngat ket noi.
//   - MODE MANUAL / MODE AUTO_READY / AUTO START / PAUSE / RESUME tuong thich app cu.
//   - SORT khi robot dang ban: KHONG bo nua, dua vao FIFO queue nho.
//   - Co chan spam trung mau theo frame de tranh 1 san pham bi queue nhieu lan.
//   - Bo AI/hinh the: chi nhan mau qua SORT,<mau>. HANG LOI dung SORT,ERROR.
// =====================================================

// ----------------- WIFI TCP -----------------
const char *WIFI_SSID = "GANTRY_ESP32";
const char *WIFI_PASSWORD = "12345678";
const uint16_t TCP_PORT = 5000;
WiFiServer tcpServer(TCP_PORT);
unsigned long lastWifiCheckMs = 0;
const unsigned long WIFI_CHECK_INTERVAL_MS = 3000;

// ----------------- PIN MAP -----------------
#define X_STEP_PIN   4
#define X_DIR_PIN    5
#define X_LIMIT_PIN  14

#define Y_STEP_PIN   6
#define Y_DIR_PIN    7
#define Y_LIMIT_PIN  12

#define Z_STEP_PIN   15
#define Z_DIR_PIN    16
#define Z_LIMIT_PIN  13

#define PRODUCT_SENSOR_PIN 35
#define PRODUCT_ACTIVE_LEVEL LOW

#define VALVE_PIN 36
#define VALVE_ACTIVE_LEVEL HIGH

#define CONVEYOR_PIN 25
#define CONVEYOR_ACTIVE_LEVEL HIGH

// ----------------- MACHINE SETTINGS -----------------
const float PULSE_PER_REV = 1600.0f;
const float LEAD_MM_PER_REV = 8.0f;
const float STEPS_PER_MM = PULSE_PER_REV / LEAD_MM_PER_REV;  // 200 step/mm neu T8 lead 8mm

const float X_MAX_MM = 300.0f;
const float Y_MAX_MM = 300.0f;
const float Z_MAX_MM = 90.0f;

const uint32_t MOVE_SPEED_HZ = 15000;      // ~75 mm/s voi 200 step/mm
const uint32_t JOG_SPEED_HZ = 9000;        // ~45 mm/s
const uint32_t HOME_SPEED_HZ = 10000;      // ~50 mm/s
const uint32_t BACKOFF_SPEED_HZ = 5000;

// Gia toc de vua nhanh vua bot giat. Neu mat buoc: giam 20-30%.
const uint32_t ACCEL_X = 450000;
const uint32_t ACCEL_Y = 550000;
const uint32_t ACCEL_Z = 420000;

const float HOME_BACKOFF_MM = 2.0f;
const float HOME_SEARCH_EXTRA_MM = 30.0f;
const unsigned long HOME_TIMEOUT_MS = 18000;
const unsigned long BACKOFF_TIMEOUT_MS = 5000;

const float MAX_SINGLE_JOG_MM = 50.0f;

// ----------------- SORT COORDINATES -----------------
float pickXmm = 60.0f;
float pickYmm = 85.0f;
float pickZmm = 70.0f;
const float SAFE_Z_MM = 30.0f;

float blueXmm = 250.0f;
float blueYmm = 55.0f;
float blueZmm = 30.0f;

float redXmm = 250.0f;
float redYmm = 165.0f;
float redZmm = 30.0f;

float yellowXmm = 250.0f;
float yellowYmm = 270.0f;
float yellowZmm = 30.0f;

float errorXmm = 250.0f;
float errorYmm = 270.0f;
float errorZmm = 30.0f;

const unsigned long AFTER_HOME_MS = 300;
const unsigned long PRODUCT_STABLE_MS = 120;
const unsigned long CONVEYOR_SETTLE_MS = 450;
const unsigned long PICK_DWELL_MS = 700;
const unsigned long DROP_DWELL_MS = 500;
const unsigned long AFTER_DROP_ACCEPT_DELAY_MS = 900;   // nha xong doi ngan roi xu ly mon tiep

// Queue de khong mat hang khi app/camera gui SORT lien tiep trong luc robot dang ban.
const uint8_t SORT_QUEUE_SIZE = 6;
const uint8_t SORT_NAME_LEN = 18;
const uint8_t DROP_POINT_MAX = 16;
const unsigned long SORT_DUPLICATE_IGNORE_MS = 300;   // FINAL: can bang giua hang sat nhau va chong spam frame

const bool USE_PRODUCT_SENSOR = true;
const bool USE_CONVEYOR_CONTROL = true;
const bool USE_VACUUM = true;

// Huong HOME da test tu ban cu.
// App quy uoc: dau '-' la ve HOME, dau '+' la ra khoi HOME.
const int X_HOME_DIR = -1;
const int Y_HOME_DIR = +1;
const int Z_HOME_DIR = -1;

const bool X_DIR_INVERT = false;
const bool Y_DIR_INVERT = false;
const bool Z_DIR_INVERT = true;

// ----------------- STEPPERS -----------------
FastAccelStepperEngine engine = FastAccelStepperEngine();
FastAccelStepper *stepperX = nullptr;
FastAccelStepper *stepperY = nullptr;
FastAccelStepper *stepperZ = nullptr;

// ----------------- RUNTIME STATE -----------------
float xPosMm = 0.0f;
float yPosMm = 0.0f;
float zPosMm = 0.0f;

bool xHomed = false;
bool yHomed = false;
bool zHomed = false;

bool estopActive = false;
bool valveState = false;
bool conveyorState = false;

String serialBuffer = "";

// Forward declarations
void updateHoming();
void updateSort();
void updateGoto();
void updateJog();
void MotionTask(void *pvParameters);
void TcpTask(void *pvParameters);
void SerialTask(void *pvParameters);
void WifiWatchdogTask(void *pvParameters);
void processCommandQueue();
bool submitCommandAndWait(const char *cmd, char *response, size_t responseSize, TickType_t timeoutTicks);

// ----------------- HOME STATE -----------------
enum HomeMode { HOME_NONE, HOME_ALL, HOME_SINGLE };
enum AxisHomeState { HS_IDLE, HS_SEARCHING, HS_BACKOFF, HS_DONE, HS_FAILED };

struct AxisHomeTask {
  char axis;
  AxisHomeState state;
  unsigned long startMs;
  unsigned long backoffStartMs;
};

HomeMode homeMode = HOME_NONE;
char currentHomeAxis = 0;
AxisHomeTask homeX = {'X', HS_IDLE, 0, 0};
AxisHomeTask homeY = {'Y', HS_IDLE, 0, 0};
AxisHomeTask homeZ = {'Z', HS_IDLE, 0, 0};

// ----------------- SORT STATE -----------------
enum SortColor { COLOR_NONE, COLOR_BLUE, COLOR_RED, COLOR_YELLOW, COLOR_ERROR, COLOR_CUSTOM };
struct SortJob {
  SortColor color;
  char name[SORT_NAME_LEN];
};

struct DynamicDropPoint {
  char name[SORT_NAME_LEN];
  float x;
  float y;
  float z;
  bool used;
};

DynamicDropPoint dynamicDropPoints[DROP_POINT_MAX];

enum SortState {
  SORT_IDLE,
  SORT_HOME,
  SORT_AFTER_HOME,
  SORT_MOVE_PICK_SAFE,
  SORT_WAIT_PRODUCT,
  SORT_SETTLE_PRODUCT,
  SORT_MOVE_PICK_DOWN,
  SORT_PICK_DWELL,
  SORT_MOVE_PICK_UP,
  SORT_MOVE_DROP,
  SORT_DROP_DWELL,
  SORT_POST_DROP_HOLD,
  SORT_ERROR
};

SortState sortState = SORT_IDLE;
SortColor activeColor = COLOR_NONE;
char activeColorName[SORT_NAME_LEN] = "NONE";
SortColor pendingColor = COLOR_NONE;  // giu de tuong thich status cu
char pendingColorName[SORT_NAME_LEN] = "NONE";

SortJob sortQueue[SORT_QUEUE_SIZE];
uint8_t sortQHead = 0;
uint8_t sortQCount = 0;
SortColor lastAcceptedSortColor = COLOR_NONE;
char lastAcceptedSortName[SORT_NAME_LEN] = "NONE";
unsigned long lastAcceptedSortMs = 0;

unsigned long sortStateMs = 0;
unsigned long productSeenMs = 0;
String sortError = "";

float targetX = 0.0f;
float targetY = 0.0f;
float targetZ = 0.0f;

// ----------------- JOG STATE -----------------
bool jogActive = false;
char jogAxisName = 0;
float jogTargetMm = 0.0f;
unsigned long jogStartMs = 0;
const unsigned long JOG_TIMEOUT_MS = 7000;

// GOTO POINT state. Dùng cho nút ĐI ĐẾN trên app để kiểm tra tọa độ đã lưu.
bool gotoActive = false;
String gotoName = "";
unsigned long gotoStartMs = 0;
const unsigned long GOTO_TIMEOUT_MS = 12000;


// ----------------- FREERTOS COMMAND ROUTING -----------------
// TCP/Serial task chi nhan lenh. MotionTask la noi DUY NHAT duoc goi handleCommand()
// va thay doi trang thai HOME/JOG/SORT. Cach nay tranh xung dot khi WiFi den dung luc motor dang chay.
enum CommandSource : uint8_t {
  CMD_SRC_TCP = 1,
  CMD_SRC_SERIAL = 2
};

struct CommandReply {
  char text[256];
};

struct CommandPacket {
  char text[128];
  QueueHandle_t replyQueue;
  CommandSource source;
};

QueueHandle_t commandQueue = nullptr;

const uint8_t COMMAND_QUEUE_LENGTH = 12;
const TickType_t COMMAND_SEND_TIMEOUT = pdMS_TO_TICKS(30);
const TickType_t COMMAND_REPLY_TIMEOUT = pdMS_TO_TICKS(4500);

TaskHandle_t motionTaskHandle = nullptr;
TaskHandle_t tcpTaskHandle = nullptr;
TaskHandle_t serialTaskHandle = nullptr;
TaskHandle_t wifiTaskHandle = nullptr;


// =====================================================
// BASIC HELPERS
// =====================================================
bool xLimitHit() { return digitalRead(X_LIMIT_PIN) == HIGH; }
bool yLimitHit() { return digitalRead(Y_LIMIT_PIN) == HIGH; }
bool zLimitHit() { return digitalRead(Z_LIMIT_PIN) == HIGH; }

bool limitHit(char axis) {
  axis = toupper(axis);
  if (axis == 'X') return xLimitHit();
  if (axis == 'Y') return yLimitHit();
  if (axis == 'Z') return zLimitHit();
  return false;
}

bool productDetected() {
  return digitalRead(PRODUCT_SENSOR_PIN) == PRODUCT_ACTIVE_LEVEL;
}

bool allAxesHomed() {
  return xHomed && yHomed && zHomed;
}

FastAccelStepper *stepper(char axis) {
  axis = toupper(axis);
  if (axis == 'X') return stepperX;
  if (axis == 'Y') return stepperY;
  if (axis == 'Z') return stepperZ;
  return nullptr;
}

float axisPos(char axis) {
  axis = toupper(axis);
  if (axis == 'X') return xPosMm;
  if (axis == 'Y') return yPosMm;
  if (axis == 'Z') return zPosMm;
  return 0.0f;
}

void setAxisPos(char axis, float mm) {
  if (mm < 0.0f) mm = 0.0f;
  axis = toupper(axis);
  if (axis == 'X') xPosMm = mm;
  if (axis == 'Y') yPosMm = mm;
  if (axis == 'Z') zPosMm = mm;
}

void setAxisHomed(char axis, bool value) {
  axis = toupper(axis);
  if (axis == 'X') xHomed = value;
  if (axis == 'Y') yHomed = value;
  if (axis == 'Z') zHomed = value;
}

float axisMax(char axis) {
  axis = toupper(axis);
  if (axis == 'X') return X_MAX_MM;
  if (axis == 'Y') return Y_MAX_MM;
  if (axis == 'Z') return Z_MAX_MM;
  return 0.0f;
}

int homeDir(char axis) {
  axis = toupper(axis);
  if (axis == 'X') return X_HOME_DIR;
  if (axis == 'Y') return Y_HOME_DIR;
  if (axis == 'Z') return Z_HOME_DIR;
  return 0;
}

uint32_t axisAccel(char axis) {
  axis = toupper(axis);
  if (axis == 'X') return ACCEL_X;
  if (axis == 'Y') return ACCEL_Y;
  if (axis == 'Z') return ACCEL_Z;
  return 300000;
}

AxisHomeTask *homeTask(char axis) {
  axis = toupper(axis);
  if (axis == 'X') return &homeX;
  if (axis == 'Y') return &homeY;
  if (axis == 'Z') return &homeZ;
  return nullptr;
}

bool anyAxisRunning() {
  return (stepperX && stepperX->isRunning()) ||
         (stepperY && stepperY->isRunning()) ||
         (stepperZ && stepperZ->isRunning());
}

bool pointInsideLimit(float x, float y, float z) {
  return x >= -0.001f && y >= -0.001f && z >= -0.001f &&
         x <= X_MAX_MM + 0.001f && y <= Y_MAX_MM + 0.001f && z <= Z_MAX_MM + 0.001f;
}

String colorText(SortColor c) {
  if (c == COLOR_BLUE) return "BLUE";
  if (c == COLOR_RED) return "RED";
  if (c == COLOR_YELLOW) return "YELLOW";
  if (c == COLOR_ERROR) return "ERROR";
  if (c == COLOR_CUSTOM) return "CUSTOM";
  return "NONE";
}

void normalizeName(String raw, char *out, size_t outSize) {
  raw.trim();
  raw.toUpperCase();

  if (raw.startsWith("SORT,")) raw = raw.substring(5);
  if (raw.startsWith("SORT ")) raw = raw.substring(5);
  raw.trim();

  if (raw == "XANH") raw = "BLUE";
  else if (raw == "DO") raw = "RED";
  else if (raw == "VANG") raw = "YELLOW";
  else if (raw == "LOI" || raw == "HANG_LOI" || raw == "UNKNOWN" ||
           raw == "KHONG_XAC_DINH" || raw == "INVALID" || raw == "OTHER") raw = "ERROR";

  size_t j = 0;
  for (size_t i = 0; i < raw.length() && j < outSize - 1; i++) {
    char ch = raw.charAt(i);
    bool ok = (ch >= 'A' && ch <= 'Z') || (ch >= '0' && ch <= '9') || ch == '_';
    if (ok) out[j++] = ch;
  }
  out[j] = '\0';

  if (j == 0) {
    strncpy(out, "ERROR", outSize);
    out[outSize - 1] = '\0';
  }
}

SortColor nameToBaseColor(const char *name) {
  if (strcmp(name, "BLUE") == 0) return COLOR_BLUE;
  if (strcmp(name, "RED") == 0) return COLOR_RED;
  if (strcmp(name, "YELLOW") == 0) return COLOR_YELLOW;
  if (strcmp(name, "ERROR") == 0) return COLOR_ERROR;
  if (strcmp(name, "NONE") == 0) return COLOR_NONE;
  return COLOR_CUSTOM;
}

SortJob makeSortJob(SortColor color, const char *name) {
  SortJob job;
  job.color = color;
  strncpy(job.name, name, SORT_NAME_LEN);
  job.name[SORT_NAME_LEN - 1] = '\0';
  return job;
}

String jobText(const SortJob &job) {
  if (job.color == COLOR_CUSTOM) return String(job.name);
  return colorText(job.color);
}

String activeColorText() {
  if (activeColor == COLOR_CUSTOM) return String(activeColorName);
  return colorText(activeColor);
}

String pendingColorText() {
  if (pendingColor == COLOR_CUSTOM) return String(pendingColorName);
  return colorText(pendingColor);
}

String queueText() {
  if (sortQCount == 0) return "EMPTY";
  String s = "";
  for (uint8_t i = 0; i < sortQCount; i++) {
    uint8_t idx = (sortQHead + i) % SORT_QUEUE_SIZE;
    if (i > 0) s += ">";
    s += jobText(sortQueue[idx]);
  }
  return s;
}

void clearSortQueue() {
  sortQHead = 0;
  sortQCount = 0;
  pendingColor = COLOR_NONE;
  strncpy(pendingColorName, "NONE", SORT_NAME_LEN);
  lastAcceptedSortColor = COLOR_NONE;
  strncpy(lastAcceptedSortName, "NONE", SORT_NAME_LEN);
  lastAcceptedSortMs = 0;
}

bool sameSortJob(const SortJob &a, const SortJob &b) {
  if (a.color != b.color) return false;
  return strcmp(a.name, b.name) == 0;
}

bool duplicateSortTooSoon(const SortJob &job) {
  if (job.color == COLOR_NONE) return false;
  SortJob last = makeSortJob(lastAcceptedSortColor, lastAcceptedSortName);
  if (!sameSortJob(last, job)) return false;
  return (millis() - lastAcceptedSortMs) < SORT_DUPLICATE_IGNORE_MS;
}

void markSortAccepted(const SortJob &job) {
  lastAcceptedSortColor = job.color;
  strncpy(lastAcceptedSortName, job.name, SORT_NAME_LEN);
  lastAcceptedSortName[SORT_NAME_LEN - 1] = '\0';
  lastAcceptedSortMs = millis();
}

bool enqueueSortColor(const SortJob &job) {
  if (sortQCount >= SORT_QUEUE_SIZE) return false;
  uint8_t tail = (sortQHead + sortQCount) % SORT_QUEUE_SIZE;
  sortQueue[tail] = job;
  sortQCount++;
  pendingColor = sortQueue[sortQHead].color;
  strncpy(pendingColorName, sortQueue[sortQHead].name, SORT_NAME_LEN);
  pendingColorName[SORT_NAME_LEN - 1] = '\0';
  return true;
}

bool dequeueSortColor(SortJob &job) {
  if (sortQCount == 0) return false;
  job = sortQueue[sortQHead];
  sortQHead = (sortQHead + 1) % SORT_QUEUE_SIZE;
  sortQCount--;
  if (sortQCount > 0) {
    pendingColor = sortQueue[sortQHead].color;
    strncpy(pendingColorName, sortQueue[sortQHead].name, SORT_NAME_LEN);
    pendingColorName[SORT_NAME_LEN - 1] = '\0';
  } else {
    pendingColor = COLOR_NONE;
    strncpy(pendingColorName, "NONE", SORT_NAME_LEN);
  }
  return true;
}

String sortStateText() {
  switch (sortState) {
    case SORT_IDLE: return "IDLE";
    case SORT_HOME: return "HOME";
    case SORT_AFTER_HOME: return "AFTER_HOME";
    case SORT_MOVE_PICK_SAFE: return "MOVE_PICK_SAFE";
    case SORT_WAIT_PRODUCT: return "WAIT_PRODUCT";
    case SORT_SETTLE_PRODUCT: return "SETTLE_PRODUCT";
    case SORT_MOVE_PICK_DOWN: return "MOVE_PICK_DOWN";
    case SORT_PICK_DWELL: return "PICK_DWELL";
    case SORT_MOVE_PICK_UP: return "MOVE_PICK_UP";
    case SORT_MOVE_DROP: return "MOVE_DROP";
    case SORT_DROP_DWELL: return "DROP_DWELL";
    case SORT_POST_DROP_HOLD: return "POST_DROP_HOLD";
    case SORT_ERROR: return "ERROR";
  }
  return "UNKNOWN";
}

String homeStateText() {
  if (homeMode == HOME_NONE) return "NONE";
  if (homeMode == HOME_ALL) return "ALL";
  return String("SINGLE_") + currentHomeAxis;
}

String statusText() {
  // STATUS rut gon bang snprintf de giam cap phat String dong va giam timeout TCP.
  // Neu can debug queue chi tiet thi xem Serial Monitor, app chi can cac truong cot loi.
  char buf[384];
  snprintf(buf, sizeof(buf),
           "ACK STATUS X_MIN=%d Y_MIN=%d Z_MIN=%d PRODUCT=%d "
           "X_HOME=%d Y_HOME=%d Z_HOME=%d X_POS=%.1f Y_POS=%.1f Z_POS=%.1f "
           "VALVE=%s CONVEYOR=%s ESTOP=%d HOME=%s SORT=%s COLOR=%s Q=%u JOG=%d",
           xLimitHit() ? 1 : 0,
           yLimitHit() ? 1 : 0,
           zLimitHit() ? 1 : 0,
           productDetected() ? 1 : 0,
           xHomed ? 1 : 0,
           yHomed ? 1 : 0,
           zHomed ? 1 : 0,
           xPosMm, yPosMm, zPosMm,
           valveState ? "ON" : "OFF",
           conveyorState ? "ON" : "OFF",
           estopActive ? 1 : 0,
           homeStateText().c_str(),
           sortStateText().c_str(),
           activeColorText().c_str(),
           sortQCount,
           jogActive ? 1 : 0);
  return String(buf);
}

// ACK/ERR phai ngan de app khong timeout va ESP32 khong bi phan manh heap
// sau nhieu chu ky. Muon xem day du trang thai thi goi STATUS.
String ack(const String &msg) {
  return String("ACK ") + msg;
}

String err(const String &msg) {
  return String("ERR ") + msg;
}

// =====================================================
// IO CONTROL
// =====================================================
void valveOn() {
  if (!USE_VACUUM) return;
  digitalWrite(VALVE_PIN, VALVE_ACTIVE_LEVEL);
  valveState = true;
}

void valveOff() {
  digitalWrite(VALVE_PIN, !VALVE_ACTIVE_LEVEL);
  valveState = false;
}

void conveyorOn() {
  conveyorState = true;
  if (USE_CONVEYOR_CONTROL) digitalWrite(CONVEYOR_PIN, CONVEYOR_ACTIVE_LEVEL);
}

void conveyorOff() {
  conveyorState = false;
  if (USE_CONVEYOR_CONTROL) digitalWrite(CONVEYOR_PIN, !CONVEYOR_ACTIVE_LEVEL);
}

void resetHomeTasks() {
  homeX.state = HS_IDLE; homeY.state = HS_IDLE; homeZ.state = HS_IDLE;
  homeX.startMs = homeY.startMs = homeZ.startMs = 0;
  homeX.backoffStartMs = homeY.backoffStartMs = homeZ.backoffStartMs = 0;
}

void stopAllMotion() {
  homeMode = HOME_NONE;
  currentHomeAxis = 0;
  resetHomeTasks();
  if (stepperX) stepperX->forceStop();
  if (stepperY) stepperY->forceStop();
  if (stepperZ) stepperZ->forceStop();
  jogActive = false;
  jogAxisName = 0;
  gotoActive = false;
  gotoName = "";
}


void stopSort() {
  sortState = SORT_IDLE;
  activeColor = COLOR_NONE;
  strncpy(activeColorName, "NONE", SORT_NAME_LEN);
  clearSortQueue();
  productSeenMs = 0;
  sortError = "";
  valveOff();
  conveyorOff();
}

void failSort(const String &reason) {
  sortState = SORT_ERROR;
  clearSortQueue();
  sortError = reason;
  stopAllMotion();
  valveOff();
  conveyorOff();
  Serial.println(String("SORT_ERROR ") + reason);
}

// =====================================================
// MOTION
// =====================================================
void startAxisMoveMm(char axis, float targetMm, uint32_t speedHz) {
  FastAccelStepper *st = stepper(axis);
  if (!st) return;

  float currentMm = axisPos(axis);
  float deltaMm = targetMm - currentMm;
  if (fabs(deltaMm) < 0.001f) return;

  // delta duong = ra khoi HOME = -homeDir; delta am = ve HOME = homeDir.
  int dir = (deltaMm >= 0.0f) ? -homeDir(axis) : homeDir(axis);
  long steps = lround(fabs(deltaMm) * STEPS_PER_MM);
  if (steps < 1) steps = 1;

  st->setSpeedInHz(speedHz);
  st->setAcceleration(axisAccel(axis));
  st->move(dir * steps);
}

bool startMoveXYZ(float x, float y, float z) {
  if (estopActive) { sortError = "ESTOP_ACTIVE"; return false; }
  if (jogActive) { sortError = "JOG_BUSY"; return false; }
  if (!allAxesHomed()) { sortError = "HOME_REQUIRED"; return false; }
  if (!pointInsideLimit(x, y, z)) { sortError = "POINT_OUT_OF_LIMIT"; return false; }

  targetX = x; targetY = y; targetZ = z;
  startAxisMoveMm('X', x, MOVE_SPEED_HZ);
  startAxisMoveMm('Y', y, MOVE_SPEED_HZ);
  startAxisMoveMm('Z', z, MOVE_SPEED_HZ);
  return true;
}

void finishMoveTarget() {
  setAxisPos('X', targetX);
  setAxisPos('Y', targetY);
  setAxisPos('Z', targetZ);
}

bool dynamicDropPointToCoords(const char *name, float &x, float &y, float &z) {
  for (uint8_t i = 0; i < DROP_POINT_MAX; i++) {
    if (dynamicDropPoints[i].used && strcmp(dynamicDropPoints[i].name, name) == 0) {
      x = dynamicDropPoints[i].x;
      y = dynamicDropPoints[i].y;
      z = dynamicDropPoints[i].z;
      return true;
    }
  }
  return false;
}

bool saveDynamicDropPoint(const char *name, float x, float y, float z) {
  for (uint8_t i = 0; i < DROP_POINT_MAX; i++) {
    if (dynamicDropPoints[i].used && strcmp(dynamicDropPoints[i].name, name) == 0) {
      dynamicDropPoints[i].x = x;
      dynamicDropPoints[i].y = y;
      dynamicDropPoints[i].z = z;
      return true;
    }
  }

  for (uint8_t i = 0; i < DROP_POINT_MAX; i++) {
    if (!dynamicDropPoints[i].used) {
      dynamicDropPoints[i].used = true;
      strncpy(dynamicDropPoints[i].name, name, SORT_NAME_LEN);
      dynamicDropPoints[i].name[SORT_NAME_LEN - 1] = '\0';
      dynamicDropPoints[i].x = x;
      dynamicDropPoints[i].y = y;
      dynamicDropPoints[i].z = z;
      return true;
    }
  }

  return false;
}

void dropPointForColor(SortColor c, const char *name, float &x, float &y, float &z) {
  if (c == COLOR_CUSTOM) {
    if (dynamicDropPointToCoords(name, x, y, z)) {
      return;
    }

    // Nếu app gửi một màu mới nhưng chưa đồng bộ tọa độ thả,
    // đưa về khay ERROR thay vì rơi nhầm về BLUE.
    x = errorXmm;
    y = errorYmm;
    z = errorZmm;
    return;
  }

  if (c == COLOR_RED) {
    x = redXmm; y = redYmm; z = redZmm;
  } else if (c == COLOR_YELLOW) {
    x = yellowXmm; y = yellowYmm; z = yellowZmm;
  } else if (c == COLOR_ERROR) {
    x = errorXmm; y = errorYmm; z = errorZmm;
  } else {
    x = blueXmm; y = blueYmm; z = blueZmm;
  }
}

// =====================================================
// HOME NON-BLOCKING
// =====================================================
long homeSearchSteps(char axis) {
  float mm = axisMax(axis) + HOME_SEARCH_EXTRA_MM;
  long steps = lround(mm * STEPS_PER_MM);
  if (steps < 1000) steps = 1000;
  return steps;
}

bool beginAxisHome(char axis) {
  AxisHomeTask *t = homeTask(axis);
  FastAccelStepper *st = stepper(axis);
  if (!t || !st) return false;

  axis = toupper(axis);
  t->axis = axis;
  t->state = HS_SEARCHING;
  t->startMs = millis();
  t->backoffStartMs = 0;

  setAxisHomed(axis, false);
  setAxisPos(axis, 0.0f);

  if (limitHit(axis)) {
    st->forceStopAndNewPosition(0);
    st->setSpeedInHz(BACKOFF_SPEED_HZ);
    st->setAcceleration(axisAccel(axis));
    st->move((-homeDir(axis)) * lround(HOME_BACKOFF_MM * STEPS_PER_MM));
    t->state = HS_BACKOFF;
    t->backoffStartMs = millis();
    return true;
  }

  st->setSpeedInHz(HOME_SPEED_HZ);
  st->setAcceleration(axisAccel(axis));
  st->move(homeDir(axis) * homeSearchSteps(axis));
  return true;
}

void startHomeAll() {
  stopAllMotion();
  stopSort();
  homeMode = HOME_ALL;
  beginAxisHome('X');
  beginAxisHome('Y');
  beginAxisHome('Z');
  Serial.println("HOME_ALL_START");
}

void startHomeSingle(char axis) {
  stopAllMotion();
  stopSort();
  homeMode = HOME_SINGLE;
  currentHomeAxis = toupper(axis);
  beginAxisHome(currentHomeAxis);
  Serial.println(String("HOME_START ") + currentHomeAxis);
}

void updateOneHome(AxisHomeTask *t) {
  if (!t || t->state == HS_IDLE || t->state == HS_DONE || t->state == HS_FAILED) return;

  char axis = t->axis;
  FastAccelStepper *st = stepper(axis);
  if (!st) { t->state = HS_FAILED; return; }

  if (t->state == HS_SEARCHING) {
    if (limitHit(axis)) {
      st->forceStopAndNewPosition(0);
      st->setSpeedInHz(BACKOFF_SPEED_HZ);
      st->setAcceleration(axisAccel(axis));
      st->move((-homeDir(axis)) * lround(HOME_BACKOFF_MM * STEPS_PER_MM));
      t->state = HS_BACKOFF;
      t->backoffStartMs = millis();
      return;
    }

    if (!st->isRunning() || millis() - t->startMs > HOME_TIMEOUT_MS) {
      st->forceStop();
      t->state = HS_FAILED;
      return;
    }
  }

  if (t->state == HS_BACKOFF) {
    if (!st->isRunning() || millis() - t->backoffStartMs > BACKOFF_TIMEOUT_MS) {
      st->forceStopAndNewPosition(0);
      setAxisPos(axis, 0.0f);
      setAxisHomed(axis, true);
      t->state = HS_DONE;
      Serial.println(String("HOME_DONE ") + axis);
      return;
    }
  }
}

void updateHoming() {
  if (homeMode == HOME_NONE) return;

  if (homeMode == HOME_SINGLE) {
    AxisHomeTask *t = homeTask(currentHomeAxis);
    updateOneHome(t);
    if (!t || t->state == HS_FAILED) {
      homeMode = HOME_NONE;
      stopAllMotion();
      Serial.println("HOME_FAILED");
      return;
    }
    if (t->state == HS_DONE) {
      homeMode = HOME_NONE;
      currentHomeAxis = 0;
      Serial.println("HOME_SINGLE_DONE");
      return;
    }
  }

  if (homeMode == HOME_ALL) {
    updateOneHome(&homeX);
    updateOneHome(&homeY);
    updateOneHome(&homeZ);

    if (homeX.state == HS_FAILED || homeY.state == HS_FAILED || homeZ.state == HS_FAILED) {
      homeMode = HOME_NONE;
      stopAllMotion();
      Serial.println("HOME_ALL_FAILED");
      return;
    }

    if (homeX.state == HS_DONE && homeY.state == HS_DONE && homeZ.state == HS_DONE) {
      homeMode = HOME_NONE;
      Serial.println("HOME_ALL_DONE");
      return;
    }
  }
}

// =====================================================
// SORT STATE MACHINE
// =====================================================
bool sortBusy() {
  return sortState != SORT_IDLE && sortState != SORT_ERROR;
}

bool motionBusy() {
  return sortBusy() || homeMode != HOME_NONE || jogActive || gotoActive;
}

void setSortState(SortState st) {
  sortState = st;
  sortStateMs = millis();
}

void beginSortAfterHomeDelay() {
  conveyorOff();
  valveOff();
  setSortState(SORT_AFTER_HOME);
}

String startSortNow(const SortJob &job, bool fromQueue) {
  activeColor = job.color;
  strncpy(activeColorName, job.name, SORT_NAME_LEN);
  activeColorName[SORT_NAME_LEN - 1] = '\0';
  sortError = "";
  productSeenMs = 0;
  valveOff();
  conveyorOff();

  if (!allAxesHomed()) {
    sortState = SORT_HOME;
    sortStateMs = millis();
    homeMode = HOME_ALL;
    beginAxisHome('X');
    beginAxisHome('Y');
    beginAxisHome('Z');
    return ack(String("SORT_") + jobText(job) + (fromQueue ? " QUEUE_HOME_START" : " HOME_START"));
  }

  beginSortAfterHomeDelay();
  return ack(String("SORT_") + jobText(job) + (fromQueue ? " QUEUE_START" : " START"));
}

String startSort(const SortJob &job) {
  if (estopActive) return err("ESTOP_ACTIVE");

  // Neu dang JOG/bao tri thi khong queue, tranh tu chay bat ngo khi nguoi dung test tay.
  if (jogActive) return ack(String("SORT_") + jobText(job) + " JOG_BUSY_IGNORED");

  // Neu robot dang gap/tha/home trong chu trinh SORT thi luu hang doi.
  if (sortBusy() || homeMode != HOME_NONE) {
    if (duplicateSortTooSoon(job)) {
      return ack(String("SORT_") + jobText(job) + " DUPLICATE_IGNORED");
    }
    if (!enqueueSortColor(job)) {
      return ack(String("SORT_") + jobText(job) + " QUEUE_FULL");
    }
    markSortAccepted(job);
    return ack(String("SORT_") + jobText(job) + " QUEUED");
  }

  if (duplicateSortTooSoon(job)) {
    return ack(String("SORT_") + jobText(job) + " DUPLICATE_IGNORED");
  }

  markSortAccepted(job);
  return startSortNow(job, false);
}

void startNextQueuedSortIfAny() {
  if (estopActive || jogActive || homeMode != HOME_NONE || sortState != SORT_IDLE) return;
  SortJob nextJob = makeSortJob(COLOR_NONE, "NONE");
  if (!dequeueSortColor(nextJob)) return;
  Serial.println(String("SORT_DEQUEUE ") + jobText(nextJob) + " Q=" + String(sortQCount));
  String r = startSortNow(nextJob, true);
  Serial.println(r);
}

void updateSort() {
  if (sortState == SORT_IDLE || sortState == SORT_ERROR) return;

  if (estopActive) {
    failSort("ESTOP_ACTIVE");
    return;
  }

  switch (sortState) {
    case SORT_HOME:
      if (homeMode == HOME_NONE) {
        if (!allAxesHomed()) failSort("HOME_FAILED");
        else beginSortAfterHomeDelay();
      }
      break;

    case SORT_AFTER_HOME:
      if (millis() - sortStateMs >= AFTER_HOME_MS) {
        if (!startMoveXYZ(pickXmm, pickYmm, SAFE_Z_MM)) failSort(sortError);
        else setSortState(SORT_MOVE_PICK_SAFE);
      }
      break;

    case SORT_MOVE_PICK_SAFE:
      if (!anyAxisRunning()) {
        finishMoveTarget();
        productSeenMs = 0;
        if (USE_PRODUCT_SENSOR) {
          conveyorOn();
          setSortState(SORT_WAIT_PRODUCT);
        } else {
          conveyorOff();
          setSortState(SORT_SETTLE_PRODUCT);
        }
      }
      break;

    case SORT_WAIT_PRODUCT:
      if (!productDetected()) {
        productSeenMs = 0;
        break;
      }
      if (productSeenMs == 0) {
        productSeenMs = millis();
        break;
      }
      if (millis() - productSeenMs >= PRODUCT_STABLE_MS) {
        conveyorOff();
        setSortState(SORT_SETTLE_PRODUCT);
      }
      break;

    case SORT_SETTLE_PRODUCT:
      if (millis() - sortStateMs >= CONVEYOR_SETTLE_MS) {
        if (!startMoveXYZ(pickXmm, pickYmm, pickZmm)) failSort(sortError);
        else setSortState(SORT_MOVE_PICK_DOWN);
      }
      break;

    case SORT_MOVE_PICK_DOWN:
      if (!anyAxisRunning()) {
        finishMoveTarget();
        valveOn();
        setSortState(SORT_PICK_DWELL);
      }
      break;

    case SORT_PICK_DWELL:
      if (millis() - sortStateMs >= PICK_DWELL_MS) {
        if (!startMoveXYZ(pickXmm, pickYmm, SAFE_Z_MM)) failSort(sortError);
        else setSortState(SORT_MOVE_PICK_UP);
      }
      break;

    case SORT_MOVE_PICK_UP:
      if (!anyAxisRunning()) {
        finishMoveTarget();
        float dx, dy, dz;
        dropPointForColor(activeColor, activeColorName, dx, dy, dz);
        if (!startMoveXYZ(dx, dy, dz)) failSort(sortError);
        else setSortState(SORT_MOVE_DROP);
      }
      break;

    case SORT_MOVE_DROP:
      if (!anyAxisRunning()) {
        finishMoveTarget();
        valveOff();
        setSortState(SORT_DROP_DWELL);
      }
      break;

    case SORT_DROP_DWELL:
      if (millis() - sortStateMs >= DROP_DWELL_MS) {
        // Nha xong khong nhan mon tiep ngay. Giu bang tai OFF them 1 khoang
        // de tranh app/cam bien gui SORT khi dau gap con dang o vung tha.
        conveyorOff();
        setSortState(SORT_POST_DROP_HOLD);
      }
      break;

    case SORT_POST_DROP_HOLD:
      if (millis() - sortStateMs >= AFTER_DROP_ACCEPT_DELAY_MS) {
        String finishedColor = activeColorText();

        activeColor = COLOR_NONE;
        strncpy(activeColorName, "NONE", SORT_NAME_LEN);
        productSeenMs = 0;
        sortState = SORT_IDLE;
        sortStateMs = millis();

        Serial.println(String("SORT_DONE ") + finishedColor);
        Serial.println("DONE");

        // Neu queue co mau tiep theo thi xu ly tiep, khong bat bang tai lung tung o vung tha.
        if (sortQCount > 0) {
          startNextQueuedSortIfAny();
        } else {
          conveyorOn();
        }
      }
      break;

    default:
      break;
  }
}

// =====================================================
// GOTO POINT NON-BLOCKING
// =====================================================
void updateGoto() {
  if (!gotoActive) return;

  if (!anyAxisRunning()) {
    finishMoveTarget();
    Serial.println(String("GOTO_DONE ") + gotoName + " X=" + String(xPosMm, 1) + " Y=" + String(yPosMm, 1) + " Z=" + String(zPosMm, 1));
    gotoActive = false;
    gotoName = "";
    return;
  }

  if (millis() - gotoStartMs > GOTO_TIMEOUT_MS) {
    stopAllMotion();
    Serial.println("GOTO_TIMEOUT");
    return;
  }
}

// =====================================================
// JOG MANUAL
// =====================================================
String jogAxis(char axis, int appDir, float mm) {
  axis = toupper(axis);
  if (estopActive) return err("ESTOP_ACTIVE");
  if (motionBusy()) return ack("JOG_BUSY_IGNORED");
  if (axis != 'X' && axis != 'Y' && axis != 'Z') return err("JOG_AXIS_INVALID");
  if (mm <= 0.0f || mm > MAX_SINGLE_JOG_MM) return err("JOG_MM_INVALID");
  if (!allAxesHomed()) return err("HOME_REQUIRED_BEFORE_JOG");

  float nextPos = axisPos(axis) + ((appDir > 0) ? mm : -mm);
  if (nextPos < -0.001f || nextPos > axisMax(axis) + 0.001f) return err("JOG_SOFT_LIMIT");

  FastAccelStepper *st = stepper(axis);
  if (!st) return err("STEPPER_NULL");

  int dir = (appDir > 0) ? -homeDir(axis) : homeDir(axis);
  long steps = lround(mm * STEPS_PER_MM);
  st->setSpeedInHz(JOG_SPEED_HZ);
  st->setAcceleration(axisAccel(axis));
  st->move(dir * steps);

  jogActive = true;
  jogAxisName = axis;
  jogTargetMm = nextPos;
  jogStartMs = millis();

  return ack(String("JOG_START ") + axis + " " + (appDir > 0 ? "+" : "-") + " " + String(mm, 1));
}

void updateJog() {
  if (!jogActive) return;

  FastAccelStepper *st = stepper(jogAxisName);
  if (!st) {
    jogActive = false;
    jogAxisName = 0;
    return;
  }

  if (!st->isRunning()) {
    setAxisPos(jogAxisName, jogTargetMm);
    Serial.println(String("JOG_DONE ") + jogAxisName + " POS=" + String(jogTargetMm, 1));
    jogActive = false;
    jogAxisName = 0;
    return;
  }

  if (millis() - jogStartMs > JOG_TIMEOUT_MS) {
    st->forceStop();
    Serial.println(String("JOG_TIMEOUT ") + jogAxisName);
    jogActive = false;
    jogAxisName = 0;
    return;
  }
}

// =====================================================
// COMMAND PARSER
// =====================================================
bool parseSortJob(String s, SortJob &job) {
  char name[SORT_NAME_LEN];
  normalizeName(s, name, SORT_NAME_LEN);

  SortColor baseColor = nameToBaseColor(name);

  if (baseColor == COLOR_NONE) {
    return false;
  }

  job = makeSortJob(baseColor, name);
  return true;
}

String pointText(const char *name, float x, float y, float z) {
  char buf[128];
  snprintf(
    buf,
    sizeof(buf),
    "ACK %s X=%.1f Y=%.1f Z=%.1f",
    name,
    x,
    y,
    z
  );
  return String(buf);
}

String pickText() {
  return pointText("PICK", pickXmm, pickYmm, pickZmm);
}

bool pointNameToCoords(const String &rawName, float *&x, float *&y, float *&z) {
  char norm[SORT_NAME_LEN];
  normalizeName(rawName, norm, SORT_NAME_LEN);
  String name = String(norm);

  if (name == "PICK") {
    x = &pickXmm; y = &pickYmm; z = &pickZmm;
    return true;
  }
  if (name == "BLUE") {
    x = &blueXmm; y = &blueYmm; z = &blueZmm;
    return true;
  }
  if (name == "RED") {
    x = &redXmm; y = &redYmm; z = &redZmm;
    return true;
  }
  if (name == "YELLOW") {
    x = &yellowXmm; y = &yellowYmm; z = &yellowZmm;
    return true;
  }
  if (name == "ERROR") {
    x = &errorXmm; y = &errorYmm; z = &errorZmm;
    return true;
  }
  return false;
}

bool getAnyPointCoords(const String &rawName, float &x, float &y, float &z) {
  float *px = nullptr;
  float *py = nullptr;
  float *pz = nullptr;

  if (pointNameToCoords(rawName, px, py, pz)) {
    x = *px; y = *py; z = *pz;
    return true;
  }

  char norm[SORT_NAME_LEN];
  normalizeName(rawName, norm, SORT_NAME_LEN);
  return dynamicDropPointToCoords(norm, x, y, z);
}

String pointsText() {
  char buf[320];
  snprintf(
    buf,
    sizeof(buf),
    "ACK POINTS PICK=%.1f,%.1f,%.1f BLUE=%.1f,%.1f,%.1f RED=%.1f,%.1f,%.1f YELLOW=%.1f,%.1f,%.1f ERROR=%.1f,%.1f,%.1f",
    pickXmm, pickYmm, pickZmm,
    blueXmm, blueYmm, blueZmm,
    redXmm, redYmm, redZmm,
    yellowXmm, yellowYmm, yellowZmm,
    errorXmm, errorYmm, errorZmm
  );
  return String(buf);
}

String setPointValue(const String &rawName, float x, float y, float z) {
  if (motionBusy() || sortBusy() || homeMode != HOME_NONE || jogActive) {
    return err("POINT_BUSY_STOP_ROBOT_FIRST");
  }

  if (!pointInsideLimit(x, y, z)) {
    return err("POINT_SOFT_LIMIT");
  }

  char norm[SORT_NAME_LEN];
  normalizeName(rawName, norm, SORT_NAME_LEN);
  String name = String(norm);

  float *px = nullptr;
  float *py = nullptr;
  float *pz = nullptr;

  if (pointNameToCoords(name, px, py, pz)) {
    *px = x;
    *py = y;
    *pz = z;
  } else {
    if (!saveDynamicDropPoint(norm, x, y, z)) {
      return err("POINT_TABLE_FULL");
    }
  }

  char buf[128];
  snprintf(
    buf,
    sizeof(buf),
    "%s_SET X=%.1f Y=%.1f Z=%.1f",
    norm,
    x,
    y,
    z
  );

  return ack(String(buf));
}

String setPickFromCommand(const String &cmd) {
  float x = 0.0f;
  float y = 0.0f;
  float z = 0.0f;

  int parsed = sscanf(cmd.c_str(), "SET PICK %f %f %f", &x, &y, &z);

  if (parsed != 3) {
    return err("SET_PICK_FORMAT_USE_SET_PICK_X_Y_Z");
  }

  return setPointValue("PICK", x, y, z);
}

String setDropFromCommand(const String &cmd) {
  char nameBuf[20];
  float x = 0.0f;
  float y = 0.0f;
  float z = 0.0f;

  int parsed = sscanf(cmd.c_str(), "SET DROP %19s %f %f %f", nameBuf, &x, &y, &z);

  if (parsed != 4) {
    return err("SET_DROP_FORMAT_USE_SET_DROP_COLOR_X_Y_Z");
  }

  String name = String(nameBuf);
  name.trim();
  name.toUpperCase();

  return setPointValue(name, x, y, z);
}

String setPointFromCommand(const String &cmd) {
  char nameBuf[20];
  float x = 0.0f;
  float y = 0.0f;
  float z = 0.0f;

  int parsed = sscanf(cmd.c_str(), "SET POINT %19s %f %f %f", nameBuf, &x, &y, &z);

  if (parsed != 4) {
    return err("SET_POINT_FORMAT_USE_SET_POINT_NAME_X_Y_Z");
  }

  String name = String(nameBuf);
  name.trim();
  name.toUpperCase();

  return setPointValue(name, x, y, z);
}

String getPointFromCommand(const String &cmd) {
  String name = "";

  if (cmd.startsWith("GET DROP ")) {
    name = cmd.substring(9);
  } else if (cmd.startsWith("GET POINT ")) {
    name = cmd.substring(10);
  } else {
    return err("GET_POINT_FORMAT");
  }

  name.trim();
  name.toUpperCase();

  float x = 0.0f;
  float y = 0.0f;
  float z = 0.0f;

  if (!getAnyPointCoords(name, x, y, z)) {
    return err("POINT_NAME_INVALID");
  }

  char norm[SORT_NAME_LEN];
  normalizeName(name, norm, SORT_NAME_LEN);
  return pointText(norm, x, y, z);
}

String gotoPointFromCommand(const String &cmd) {
  if (estopActive) return err("ESTOP_ACTIVE");
  if (!allAxesHomed()) return err("HOME_REQUIRED");
  if (motionBusy() || sortBusy() || homeMode != HOME_NONE || jogActive) {
    return ack("GOTO_BUSY_IGNORED");
  }

  String name = "";

  if (cmd.startsWith("GOTO POINT ")) {
    name = cmd.substring(11);
  } else if (cmd.startsWith("GOTO ")) {
    name = cmd.substring(5);
  } else {
    return err("GOTO_FORMAT");
  }

  name.trim();
  name.toUpperCase();

  float gx = 0.0f;
  float gy = 0.0f;
  float gz = 0.0f;

  if (!getAnyPointCoords(name, gx, gy, gz)) {
    return err("POINT_NAME_INVALID");
  }

  if (!startMoveXYZ(gx, gy, gz)) {
    return err(sortError.length() ? sortError : "GOTO_FAILED");
  }

  gotoActive = true;
  gotoName = name;
  gotoStartMs = millis();

  char buf[128];
  snprintf(
    buf,
    sizeof(buf),
    "GOTO_%s_START X=%.1f Y=%.1f Z=%.1f",
    name.c_str(),
    gx,
    gy,
    gz
  );

  return ack(String(buf));
}

String handleCommand(String raw) {
  raw.trim();
  if (raw.length() == 0) return err("EMPTY");

  String cmd = raw;
  cmd.trim();
  cmd.toUpperCase();

  if (cmd == "PING") return "ACK PING";
  if (cmd == "STATUS" || cmd == "LIMITS" || cmd == "DEMO STATUS") return statusText();

  if (cmd == "GET PICK" || cmd == "PICK?") {
    return pickText();
  }

  if (cmd == "GET POINTS" || cmd == "POINTS") {
    return pointsText();
  }

  if (cmd.startsWith("GET DROP ") || cmd.startsWith("GET POINT ")) {
    return getPointFromCommand(cmd);
  }

  if (cmd.startsWith("SET PICK ")) {
    return setPickFromCommand(cmd);
  }

  if (cmd.startsWith("SET DROP ")) {
    return setDropFromCommand(cmd);
  }

  if (cmd.startsWith("SET POINT ")) {
    return setPointFromCommand(cmd);
  }

  if (cmd.startsWith("GOTO ")) {
    return gotoPointFromCommand(cmd);
  }

  if (cmd == "STOP" || cmd == "JOG STOP" || cmd == "DEMO STOP") {
    stopAllMotion();
    stopSort();
    return ack("STOP");
  }

  if (cmd == "ESTOP") {
    estopActive = true;
    stopAllMotion();
    stopSort();
    return ack("ESTOP");
  }

  if (cmd == "RESET") {
    estopActive = false;
    stopAllMotion();
    stopSort();
    conveyorOff();
    valveOff();
    return ack("RESET");
  }

  if (cmd == "QUEUE CLEAR" || cmd == "CLEAR QUEUE") {
    clearSortQueue();
    return ack("QUEUE_CLEAR");
  }

  if (cmd == "HOME") {
    if (estopActive) return err("ESTOP_ACTIVE");
    if (jogActive) stopAllMotion();
    if (sortBusy()) stopSort();
    startHomeAll();
    return ack("HOME_START");
  }

  if (cmd.startsWith("HOME ")) {
    if (estopActive) return err("ESTOP_ACTIVE");
    if (jogActive) stopAllMotion();
    if (sortBusy()) stopSort();
    char axis = cmd.charAt(5);
    if (axis != 'X' && axis != 'Y' && axis != 'Z') return err("HOME_AXIS_INVALID");
    startHomeSingle(axis);
    return ack(String("HOME_") + axis + "_START");
  }

  if (cmd.startsWith("SORT,") || cmd.startsWith("SORT ")) {
    SortJob job = makeSortJob(COLOR_NONE, "NONE");
    if (!parseSortJob(cmd, job)) return err("SORT_COLOR_INVALID");
    return startSort(job);
  }

  if (cmd == "VACUUM ON" || cmd == "VALVE ON") {
    if (estopActive) return err("ESTOP_ACTIVE");
    valveOn();
    return ack("VACUUM_ON");
  }

  if (cmd == "VACUUM OFF" || cmd == "VALVE OFF") {
    valveOff();
    return ack("VACUUM_OFF");
  }

  if (cmd == "CONVEYOR ON" || cmd == "BANGTAI ON" || cmd == "BANG TAI ON") {
    conveyorOn();
    return ack("CONVEYOR_ON");
  }

  if (cmd == "CONVEYOR OFF" || cmd == "BANGTAI OFF" || cmd == "BANG TAI OFF") {
    conveyorOff();
    return ack("CONVEYOR_OFF");
  }

  if (cmd.startsWith("JOG ")) {
    // Format: JOG X + 5.0
    int p1 = cmd.indexOf(' ');
    int p2 = cmd.indexOf(' ', p1 + 1);
    int p3 = cmd.indexOf(' ', p2 + 1);
    if (p1 < 0 || p2 < 0 || p3 < 0) return err("JOG_FORMAT");
    char axis = cmd.charAt(p1 + 1);
    char sign = cmd.charAt(p2 + 1);
    float mm = cmd.substring(p3 + 1).toFloat();
    int dir = (sign == '+') ? +1 : (sign == '-' ? -1 : 0);
    if (dir == 0) return err("JOG_SIGN_INVALID");
    return jogAxis(axis, dir, mm);
  }

  // Tuong thich app GitHub. Nhung lenh nay phai tra ACK nhanh, khong block.
  if (cmd == "MODE MANUAL") {
    stopAllMotion();
    stopSort();
    conveyorOff();
    valveOff();
    return ack("MODE_MANUAL");
  }

  if (cmd == "MODE AUTO_READY") {
    stopAllMotion();
    stopSort();
    conveyorOff();
    valveOff();
    return ack("MODE_AUTO_READY");
  }

  if (cmd == "AUTO START") {
    if (!estopActive) conveyorOn();
    return ack("AUTO_START");
  }

  if (cmd == "AUTO PAUSE") {
    conveyorOff();
    return ack("AUTO_PAUSE");
  }

  if (cmd == "AUTO RESUME") {
    if (!estopActive) conveyorOn();
    return ack("AUTO_RESUME");
  }

  return err("UNKNOWN_COMMAND");
}

// =====================================================
// TCP + SERIAL TASKS + COMMAND QUEUE
// =====================================================
void copyToBuffer(char *dst, size_t dstSize, const String &src) {
  if (!dst || dstSize == 0) return;
  src.toCharArray(dst, dstSize);
  dst[dstSize - 1] = '\0';
}

void copyCStr(char *dst, size_t dstSize, const char *src) {
  if (!dst || dstSize == 0) return;
  if (!src) src = "";
  strncpy(dst, src, dstSize - 1);
  dst[dstSize - 1] = '\0';
}

bool submitCommandAndWait(const char *cmd, char *response, size_t responseSize, TickType_t timeoutTicks) {
  if (!response || responseSize == 0) return false;
  response[0] = '\0';

  if (!cmd || strlen(cmd) == 0) {
    copyCStr(response, responseSize, "ERR EMPTY");
    return false;
  }

  if (commandQueue == nullptr) {
    copyCStr(response, responseSize, "ERR CMD_QUEUE_NOT_READY");
    return false;
  }

  QueueHandle_t replyQ = xQueueCreate(1, sizeof(CommandReply));
  if (replyQ == nullptr) {
    copyCStr(response, responseSize, "ERR REPLY_QUEUE_CREATE_FAILED");
    return false;
  }

  CommandPacket packet;
  memset(&packet, 0, sizeof(packet));
  copyCStr(packet.text, sizeof(packet.text), cmd);
  packet.replyQueue = replyQ;
  packet.source = CMD_SRC_TCP;

  bool ok = false;
  if (xQueueSend(commandQueue, &packet, COMMAND_SEND_TIMEOUT) != pdTRUE) {
    copyCStr(response, responseSize, "ERR CMD_QUEUE_FULL");
  } else {
    CommandReply reply;
    memset(&reply, 0, sizeof(reply));
    if (xQueueReceive(replyQ, &reply, timeoutTicks) == pdTRUE) {
      copyCStr(response, responseSize, reply.text);
      ok = true;
    } else {
      copyCStr(response, responseSize, "ERR MOTION_TASK_TIMEOUT");
    }
  }

  vQueueDelete(replyQ);
  return ok;
}

void processCommandQueue() {
  if (commandQueue == nullptr) return;

  CommandPacket packet;
  uint8_t processed = 0;

  // Gioi han moi tick de MotionTask van cap nhat HOME/SORT/JOG lien tuc.
  while (processed < 6 && xQueueReceive(commandQueue, &packet, 0) == pdTRUE) {
    String response = handleCommand(String(packet.text));

    CommandReply reply;
    memset(&reply, 0, sizeof(reply));
    copyToBuffer(reply.text, sizeof(reply.text), response);

    if (packet.replyQueue != nullptr) {
      xQueueSend(packet.replyQueue, &reply, 0);
    }

    processed++;
  }
}

bool readTcpCommand(WiFiClient &client, char *cmd, size_t cmdSize, uint32_t timeoutMs) {
  if (!cmd || cmdSize == 0) return false;
  cmd[0] = '\0';

  size_t len = 0;
  unsigned long t0 = millis();

  while (client.connected() && millis() - t0 < timeoutMs) {
    while (client.available()) {
      char c = client.read();

      if (c == '\n' || c == '\r') {
        if (len > 0) {
          cmd[len] = '\0';
          return true;
        }
        continue;
      }

      if (len < cmdSize - 1) {
        cmd[len++] = c;
        cmd[len] = '\0';
      } else {
        cmd[cmdSize - 1] = '\0';
        return true;
      }
    }

    if (len > 0) {
      // App GitHub co luc gui xong ma khong xuong dong ro rang; chap nhan lenh sau vai ms.
      vTaskDelay(pdMS_TO_TICKS(2));
      if (!client.available()) return true;
    }

    vTaskDelay(pdMS_TO_TICKS(1));
  }

  return len > 0;
}

void TcpTask(void *pvParameters) {
  (void) pvParameters;

  for (;;) {
    WiFiClient client = tcpServer.available();

    if (client) {
      client.setNoDelay(true);
      client.setTimeout(80);

      char cmd[128];
      char response[256];

      if (!readTcpCommand(client, cmd, sizeof(cmd), 120)) {
        copyCStr(response, sizeof(response), "ERR NO_COMMAND");
      } else {
        submitCommandAndWait(cmd, response, sizeof(response), COMMAND_REPLY_TIMEOUT);
      }

      client.println(response);
      client.flush();
      vTaskDelay(pdMS_TO_TICKS(1));
      client.stop();
    }

    vTaskDelay(pdMS_TO_TICKS(1));
  }
}

void SerialTask(void *pvParameters) {
  (void) pvParameters;

  char cmd[128];
  size_t len = 0;

  for (;;) {
    while (Serial.available()) {
      char c = Serial.read();

      if (c == '\n' || c == '\r') {
        if (len > 0) {
          cmd[len] = '\0';

          char response[256];
          submitCommandAndWait(cmd, response, sizeof(response), COMMAND_REPLY_TIMEOUT);
          Serial.println(response);

          len = 0;
          cmd[0] = '\0';
        }
      } else {
        if (len < sizeof(cmd) - 1) {
          cmd[len++] = c;
        } else {
          len = 0;
          cmd[0] = '\0';
          Serial.println("ERR SERIAL_COMMAND_TOO_LONG");
        }
      }
    }

    vTaskDelay(pdMS_TO_TICKS(2));
  }
}

void MotionTask(void *pvParameters) {
  (void) pvParameters;

  for (;;) {
    processCommandQueue();
    updateHoming();
    updateSort();
    updateGoto();
    updateJog();
    vTaskDelay(pdMS_TO_TICKS(1));
  }
}

void WifiWatchdogTask(void *pvParameters) {
  (void) pvParameters;

  for (;;) {
    updateWifiWatchdog();
    vTaskDelay(pdMS_TO_TICKS(1000));
  }
}

// =====================================================
// WIFI WATCHDOG
// =====================================================
void updateWifiWatchdog() {
  if (millis() - lastWifiCheckMs < WIFI_CHECK_INTERVAL_MS) return;
  lastWifiCheckMs = millis();

  // Neu mode WiFi bi doi bat thuong thi khoi tao lai AP nhe, khong reset may.
  if (WiFi.getMode() != WIFI_AP) {
    WiFi.mode(WIFI_AP);
    WiFi.setSleep(false);
    WiFi.softAP(WIFI_SSID, WIFI_PASSWORD);
    tcpServer.begin();
    tcpServer.setNoDelay(true);
    Serial.println("WIFI_AP_RESTARTED");
  }
}

// =====================================================
// SETUP / LOOP
// =====================================================
void setupSteppers() {
  engine.init();

  stepperX = engine.stepperConnectToPin(X_STEP_PIN);
  if (stepperX) {
    stepperX->setDirectionPin(X_DIR_PIN, X_DIR_INVERT);
    stepperX->setSpeedInHz(JOG_SPEED_HZ);
    stepperX->setAcceleration(ACCEL_X);
  }

  stepperY = engine.stepperConnectToPin(Y_STEP_PIN);
  if (stepperY) {
    stepperY->setDirectionPin(Y_DIR_PIN, Y_DIR_INVERT);
    stepperY->setSpeedInHz(JOG_SPEED_HZ);
    stepperY->setAcceleration(ACCEL_Y);
  }

  stepperZ = engine.stepperConnectToPin(Z_STEP_PIN);
  if (stepperZ) {
    stepperZ->setDirectionPin(Z_DIR_PIN, Z_DIR_INVERT);
    stepperZ->setSpeedInHz(JOG_SPEED_HZ);
    stepperZ->setAcceleration(ACCEL_Z);
  }
}

void setup() {
  Serial.begin(115200);
  delay(500);

  pinMode(X_LIMIT_PIN, INPUT_PULLUP);
  pinMode(Y_LIMIT_PIN, INPUT_PULLUP);
  pinMode(Z_LIMIT_PIN, INPUT_PULLUP);
  pinMode(PRODUCT_SENSOR_PIN, INPUT_PULLUP);

  pinMode(VALVE_PIN, OUTPUT);
  pinMode(CONVEYOR_PIN, OUTPUT);
  valveOff();
  conveyorOff();

  setupSteppers();

  WiFi.mode(WIFI_AP);
  WiFi.setSleep(false);
  WiFi.softAP(WIFI_SSID, WIFI_PASSWORD);
  tcpServer.begin();
  tcpServer.setNoDelay(true);

  commandQueue = xQueueCreate(COMMAND_QUEUE_LENGTH, sizeof(CommandPacket));
  if (commandQueue == nullptr) {
    Serial.println("FATAL CMD_QUEUE_CREATE_FAILED");
    while (true) delay(1000);
  }

  // Core 1 uu tien motion. Core 0 xu ly WiFi/TCP/Serial.
  xTaskCreatePinnedToCore(MotionTask, "MotionTask", 8192, nullptr, 3, &motionTaskHandle, 1);
  xTaskCreatePinnedToCore(TcpTask, "TcpTask", 8192, nullptr, 2, &tcpTaskHandle, 0);
  xTaskCreatePinnedToCore(SerialTask, "SerialTask", 4096, nullptr, 1, &serialTaskHandle, 0);
  xTaskCreatePinnedToCore(WifiWatchdogTask, "WifiWatchdog", 4096, nullptr, 1, &wifiTaskHandle, 0);

  Serial.println();
  Serial.println("ESP32-S3 GANTRY V9.3.0 FREERTOS APP-COMPATIBLE READY");
  Serial.println("Core0=TCP/Serial/WiFi | Core1=Motion HOME/JOG/SORT");
  Serial.print("IP="); Serial.print(WiFi.softAPIP());
  Serial.print(" PORT="); Serial.println(TCP_PORT);
}

void loop() {
  // Moi viec chay trong FreeRTOS tasks. Khong dat code dieu khien o loop nua.
  vTaskDelay(pdMS_TO_TICKS(1000));
}

# =============================================================================
# 파일명  : mabinogi_loading_test.py
# 목  적  : 마비노기 모바일 - 지역 이동 시 무한 로딩 감지 및 성능 측정
# 프레임워크: Airtest Project
# 실행 환경 : Galaxy S24 (USB 디버깅 연결)
# 작성일  : 2026.06.08
# =============================================================================

# 라이브러리 임포트
import csv          # CSV 파일 입출력 (결과 저장에 사용)
import os           # 파일/폴더 경로 관련 기능
import time         # 시간 측정 및 대기(sleep) 기능
import datetime     # 현재 날짜/시간 기록에 사용

# Airtest: 이미지 기반 UI 자동화의 핵심 라이브러리
from airtest.core.api import (
    auto_setup,     # 디바이스 연결 및 초기 설정
    snapshot,       # 현재 화면 스크린샷 저장
    touch,          # 화면 특정 위치 또는 이미지 터치(클릭)
    exists,         # 특정 이미지가 화면에 있는지 확인 (True/False 반환)
    wait,           # 특정 이미지가 나타날 때까지 대기
    swipe,          # 화면 드래그(스와이프) 동작
)
from airtest.core.cv import Template  # 이미지 파일을 인식 객체(Template)로 변환하는 클래스

# =============================================================================
# 상수 정의 구역
# =============================================================================

# 반복 횟수 설정
TOTAL_ROUNDS = 20       # Map A -> Map B 왕복 기준으로 1회

# 타임아웃 설정
LOADING_TIMEOUT_SEC  = 30   # 로딩이 30초를 초과하면 무한 로딩으로 판단
UI_WAIT_TIMEOUT_SEC  = 15   # UI 요소가 나타날 때까지 기다리는 최대 시간
UI_WAIT_INTERVAL_SEC = 0.5  # UI 요소를 0.5초마다 확인

# 결과 저장 파일명
RESULT_CSV_FILENAME = "mabinogi_loading_test.csv"   # 테스트 결과가 저장될 CSV 파일 이름
SCREENSHOT_DIR      = "screenshots"                 # 결함 발생 시 스크린샷을 저장할 폴더 이름

# 지역 이름 정의
# 실제 게임 지역명 대신 MAP_A / MAP_B 로 표기
MAP_A = "Map A"   # 실제 지역: 티르코네일 (테스트 시작 위치)
MAP_B = "Map B"   # 실제 지역: 던바튼

# 이미지 파일 경로
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # 현재 스크립트가 있는 폴더의 절대 경로
_IMG_DIR  = os.path.join(_BASE_DIR, "images")           # 이미지 파일들이 들어있는 폴더 경로

# 맵 버튼
MAP_BTN_POS = (916, 389)   # 맵 버튼의 화면 픽셀 좌표 (x, y)

IMG_WORLD_MAP    = Template(os.path.join(_IMG_DIR, "world_map_btn.png"),    threshold=0.8)  # '울라 대륙' 글씨 부분만 캡처
IMG_MAP_A        = Template(os.path.join(_IMG_DIR, "map_a_icon.png"),       threshold=0.95) # 티르코네일 (근처 아이콘과 혼동 방지를 위해 threshold 높임)
IMG_MAP_B        = Template(os.path.join(_IMG_DIR, "map_b_icon.png"),       threshold=0.8)  # 던바튼
IMG_MOVE_CONFIRM = Template(os.path.join(_IMG_DIR, "move_confirm_btn.png"), threshold=0.8)  # 이동 확인 버튼
IMG_SWIPE_ANCHOR = Template(os.path.join(_IMG_DIR, "swipe_anchor.png"), threshold=0.8)      # 스와이프 시작 지점

# 로딩 화면 감지 설정
IMG_LOADING_ICON = Template(os.path.join(_IMG_DIR, "loading_icon.png"), threshold=0.8)

# Map B → Map A 이동 시 스와이프 설정
SWIPE_TO_MAP_A_VECTOR = [0.0038, -0.1798]

# =============================================================================
# CsvLogger 클래스 (테스트 결과 CSV 저장)
# =============================================================================
class CsvLogger:
    # CSV 파일의 첫 번째 줄에 들어갈 헤더 목록
    HEADERS = ["테스트번호", "출발지", "목적지", "로딩시간(초)", "결과", "결함메모", "기록시각"]

    def __init__(self, filepath: str):
       
        self.filepath = filepath

        if not os.path.exists(self.filepath):
            self._write_header()

    def _write_header(self):
        with open(self.filepath, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)         # CSV 형식으로 쓸 수 있는 writer 객체 생성
            writer.writerow(self.HEADERS)  # 헤더 한 줄 작성

    def append(self, test_no: int, origin: str, destination: str,
               loading_sec: float, result: str, memo: str = ""):

        # 현재 날짜와 시간을 '년-월-일 시:분:초' 형식의 문자열로 생성
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 기존 내용을 지우지 않고 파일 맨 끝에 새 내용을 추가
        with open(self.filepath, mode="a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            # 저장할 데이터 한 행을 리스트로 구성
            writer.writerow([
                test_no,
                origin,
                destination,
                f"{loading_sec:.2f}",   # 소수점 둘째 자리까지 표시 (예: 3.57)
                result,
                memo,
                timestamp,
            ])
        # 저장 완료 후 콘솔에 알림 출력
        print(f"  [CSV 저장] #{test_no} {origin} → {destination} | {loading_sec:.2f}s | {result}")


# =============================================================================
# LoadingTestRunner 클래스 (테스트 실행)
# =============================================================================
class LoadingTestRunner:

    def __init__(self, total_rounds: int, csv_logger: CsvLogger):

        self.total_rounds = total_rounds    # 총 반복 횟수 저장
        self.logger = csv_logger            # CSV 저장 객체 보관
        self.test_no = 0                    # 현재까지 수행한 단방향 이동 횟수 (왕복 1회 = 이동 2회)

        # 스크린샷 저장 폴더가 없으면 새로 생성
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    # -------------------------------------------------------------------------
    # 내부 헬퍼 메서드 (클래스 내부에서만 사용)
    # -------------------------------------------------------------------------

    def _safe_touch(self, image_template: Template, description: str):
        
        print(f"  [대기] '{description}' 이미지 탐색 중...")
        
        # 이미지를 찾으면 해당 위치(좌표)를 반환합니다.
        pos = wait(image_template, timeout=UI_WAIT_TIMEOUT_SEC, interval=UI_WAIT_INTERVAL_SEC)
        touch(pos)
        print(f"  [클릭] '{description}' 클릭 완료")
        time.sleep(1.0)  # 클릭 후 화면 반응 대기

    def _capture_defect_screenshot(self, test_no: int, origin: str, destination: str):  # 오류 발생시, 해당 화면 스크린샷
        timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename  = f"FAIL_#{test_no:02d}_{origin}_to_{destination}_{timestamp_str}.png"
        filepath  = os.path.join(SCREENSHOT_DIR, filename)

        snapshot(filename=filepath)
        print(f"  [스크린샷] 결함 화면 저장 완료 → {filepath}")

    def _is_loading_screen(self) -> bool:
        
        return bool(exists(IMG_LOADING_ICON))

    # -------------------------------------------------------------------------
    # 로딩 시간 측정
    # -------------------------------------------------------------------------

    def _measure_loading_time(self, test_no: int, origin: str, destination: str) -> tuple:
       
        print(f"  [측정 시작] 로딩 화면(검은 화면) 감지 대기 중...")

        # 로딩 시작까지 대기
        loading_start_time = None  # 로딩 시작 시각 (아직 측정 전이므로 None)

        deadline_for_loading_start = time.time() + UI_WAIT_TIMEOUT_SEC  # 로딩 시작 탐지 마감 시각
        while time.time() < deadline_for_loading_start:
            if self._is_loading_screen():               # 지정한 이미지가 화면에 노출되면 측정 시작
                loading_start_time = time.time()        # 로딩 시작 시각 기록
                print(f"  [로딩 시작] 로딩 화면 감지됨, 시간 측정 시작")
                break
            time.sleep(0.2)  # 0.2초마다 화면 확인

        # 로딩 화면을 아예 감지하지 못한 경우 (이미 이동이 끝났거나 오류 상황)
        if loading_start_time is None:
            print(f"  [경고] 로딩 화면을 감지하지 못했습니다. 이동이 즉시 완료되었을 수 있습니다.")
            return (0.0, "PASS", "로딩 화면 미감지(즉시 완료 추정)")

        # 지정한 이미지가 화면에서 사라지면 작동
        deadline_for_loading_end = loading_start_time + LOADING_TIMEOUT_SEC  # 타임아웃 마감 시각

        while True:
            current_time = time.time()  # 현재 시각

            # 타임아웃 초과 : 무한 로딩 결함으로 판단
            if current_time >= deadline_for_loading_end:
                elapsed = current_time - loading_start_time
                memo = f"무한 로딩 결함: {LOADING_TIMEOUT_SEC}초 초과"
                print(f"  [FAIL] {memo}")
                self._capture_defect_screenshot(test_no, origin, destination)
                return (round(elapsed, 2), "FAIL", memo)

            # 지정한 이미지가 화면에서 사라짐 : 로딩 종료로 판단
            if not self._is_loading_screen():
                elapsed = current_time - loading_start_time
                print(f"  [로딩 종료] 이동 완료. 소요 시간: {elapsed:.2f}초")
                return (round(elapsed, 2), "PASS", "")

            time.sleep(0.2)  # 0.2초마다 화면 확인

    # -------------------------------------------------------------------------
    # 단방향 이동 수행 메서드
    # -------------------------------------------------------------------------

    def _perform_one_move(self, origin: str, destination: str,
                          map_icon: Template, need_swipe: bool = False) -> bool:
        self.test_no += 1  # 이동 횟수 1 증가
        print(f"\n{'='*60}")
        print(f" 이동 #{self.test_no:02d}: {origin} → {destination}")
        print(f"{'='*60}")

        # 1) 지도를 터치하여 마을 지도 열기
        print(f"  [클릭] 맵 버튼 좌표 클릭 {MAP_BTN_POS}")
        touch(MAP_BTN_POS)
        time.sleep(1.0)  # 동작 반응 대기

        # 2) 마을 지도에서 월드맵 버튼 클릭하여 전체 월드맵 열기
        self._safe_touch(IMG_WORLD_MAP, "월드맵 버튼")
        time.sleep(1.0)  # 동작 반응 대기

        # 3) 스와이프가 필요한 경우에만 드래그 수행 (Map B → Map A 이동 시)
        if need_swipe:
            print(f"  [스와이프] 지도를 드래그하여 {destination} 아이콘 탐색 중...")
            swipe(
                IMG_SWIPE_ANCHOR,              # 드래그 시작 기준점 이미지
                vector=SWIPE_TO_MAP_A_VECTOR,  # 드래그 방향 및 거리
            )
            time.sleep(1.0)  # 동작 반응 대기
            print(f"  [스와이프] 완료")

        # 4) 지도에서 목적지 아이콘 클릭
        self._safe_touch(map_icon, f"{destination} 아이콘")

        # 5) 이동 확인 버튼 클릭
        self._safe_touch(IMG_MOVE_CONFIRM, "이동 확인 버튼")

        # 6) 로딩 시간 측정
        loading_sec, result, memo = self._measure_loading_time(
            self.test_no, origin, destination
        )

        # 7) 결과를 CSV 파일에 저장
        self.logger.append(self.test_no, origin, destination, loading_sec, result, memo)

        # 8) 이동 완료 후 다음 행동 전 3초 대기
        # 이동 직후 지도가 한번 열렸다 닫히는 오류 존재로 대기 후 수행 필요
        time.sleep(3.0)

        # FAIL이면 테스트를 중단할 수 있도록 False를 반환
        return result == "PASS"

    # -------------------------------------------------------------------------
    # 전체 테스트 실행 메서드
    # -------------------------------------------------------------------------

    def run(self):
        print(f"\n{'#'*60}")
        print(f"  마비노기 모바일 - 지역 이동 로딩 테스트 시작")
        print(f"  시작 위치: {MAP_A} / 목적지: {MAP_B} / 왕복 {self.total_rounds}회")
        print(f"  총 단방향 이동 횟수: {self.total_rounds * 2}회")
        print(f"  결과 저장 파일: {RESULT_CSV_FILENAME}")
        print(f"{'#'*60}\n")

        # 왕복 반복 루프
        for round_no in range(1, self.total_rounds + 1):
            print(f"\n[{round_no}/{self.total_rounds} 라운드 시작]")

            # 전반: Map A → Map B (스와이프 불필요)
            success = self._perform_one_move(
                origin=MAP_A,           # 출발지: 티르코네일
                destination=MAP_B,      # 목적지: 던바튼
                map_icon=IMG_MAP_B,     # 지도에서 클릭할 아이콘: Map B 아이콘
                need_swipe=False,       # Map A -> Map B 는 스와이프 없이 바로 아이콘 클릭
            )
            if not success:
                # FAIL 발생 시 테스트를 즉시 중단
                print(f"\n[테스트 중단] 무한 로딩 결함 발생. 테스트를 종료합니다.")
                break

            # 후반: Map B -> Map A (스와이프 필요)
            success = self._perform_one_move(
                origin=MAP_B,           # 출발지: 던바튼
                destination=MAP_A,      # 목적지: 티르코네일
                map_icon=IMG_MAP_A,     # 지도에서 클릭할 아이콘: Map A 아이콘
                need_swipe=True,        # Map B -> Map A 는 스와이프 후 아이콘 클릭
            )
            if not success:
                print(f"\n[테스트 중단] 무한 로딩 결함 발생. 테스트를 종료합니다.")
                break

            print(f"[{round_no}/{self.total_rounds} 라운드 완료]")

        # 전체 테스트 종료 메시지
        print(f"\n{'#'*60}")
        print(f"  테스트 종료. 총 {self.test_no}회 이동 수행.")
        print(f"  결과 파일: {os.path.abspath(RESULT_CSV_FILENAME)}")
        print(f"{'#'*60}\n")


# =============================================================================
# 메인 실행부
# =============================================================================
if __name__ == "__main__":

    # Airtest 디바이스 연결 설정
    auto_setup(__file__, devices=["Android:///"])

    # CSV 로거 객체 생성
    # CsvLogger에 저장할 파일 경로를 전달하여 객체 생성
    csv_logger = CsvLogger(filepath=RESULT_CSV_FILENAME)

    # 테스트 실행 객체 생성
    runner = LoadingTestRunner(
        total_rounds=TOTAL_ROUNDS,  # 상단에서 정의한 반복 횟수 전달
        csv_logger=csv_logger,      # 결과를 저장할 로거 객체 전달
    )

    # 테스트 실행
    runner.run()
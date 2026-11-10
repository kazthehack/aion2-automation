
"""Main GUI application for AION.
Uses a local YOLO weight (models/aion.pt) to run realtime detections
and draw a click-through overlay on the selected game window.
"""
import sys
import os
import ctypes
from PySide6 import QtWidgets, QtCore
from loguru import logger
from utils import list_windows, get_window_rect
from overlay import OverlayWindow
from detection import DetectionController
import input_controller as ic


TRANSLATIONS = {
    'en': {
        'app_title': 'AION Autoplay',
        'nav_dashboard': 'Dashboard',
        'nav_skills': 'Skills',
        'nav_combos': 'Combos',
        'nav_cooldowns': 'Cooldowns',
        'nav_logs': 'Logs',
        'nav_settings': 'Settings',
        'label_game_window': 'Game window:',
        'label_settings': 'Settings:',
        'label_settings_info': 'Using local model weights: models/aion.pt (Ultralytics YOLO)',
        'label_input_backend': 'Input backend:',
        'checkbox_simulate': 'Simulate mode (log only, no real inputs)',
        'checkbox_auto_loot': 'Auto loot',
        'checkbox_sentry_mode': 'Sentry Mode',
        'checkbox_farming_mode': 'Farming Mode',
        'action_refresh': 'Refresh',
        'status_available': 'Available',
        'status_unavailable': 'Unavailable',
        'status_unknown': 'Unknown',
        'status_tooltip_unknown': 'Unable to determine backend status',
        'status_tooltip_available': "Backend '{backend}' is available",
        'status_tooltip_unavailable': '{error}',
        'group_skill_config': 'Skill Combo Configuration',
        'checkbox_stealth_attack': 'Enable randomized attack mode (randomize attacks)',
        'label_standard_weight': 'Standard Attack Weight (Tab-target):',
        'label_single_weight': 'Single Skill Weight:',
        'label_combo_weight': 'Combo Set Weight:',
        'checkbox_combat_skills': 'Enable skills & combos during combat',
        'button_edit_skills': '⚙️ Edit Individual Skills',
        'button_edit_combos': '🎯 Edit Combo Sets',
        'button_start': 'Start',
        'button_stop': 'Stop',
        'button_emergency_stop': 'EMERGENCY STOP',
        'group_cooldown_monitor': 'Cooldown Monitor',
        'skills_table_header_skill': 'Skill',
        'skills_table_header_remaining': 'Remaining(s)',
        'combos_table_header_combo': 'Combo',
        'combos_table_header_status': 'Status',
        'status_ready': 'Ready',
        'status_unknown_value': 'Unknown',
        'status_waiting': 'Waiting',
        'status_cooldown': 'Cooldown {seconds}s',
        'trailing_hint_skill_pool': 'Hint: Drag to reorder, double-click to edit, or capture keys with the add button.',
        'button_save_changes': 'Save Changes',
        'button_cancel': 'Cancel',
        'skill_editor_title': 'Skill Editor',
        'skill_editor_subtitle': 'Manage cooldowns and the single-skill pool used by the planner.',
        'group_single_skill_pool': 'Single Skill Pool',
        'group_skill_timing': 'Skill Timing',
        'placeholder_skill_pool': 'e.g. 1,2,3,f1',
        'skill_editor_search_placeholder': 'Search skill key...',
        'button_add_pool_skill': 'Add',
        'button_remove_pool_skill': 'Remove',
        'tooltip_skill_pool': 'Comma separated skill keys used for single-skill selection',
        'tooltip_add_pool_skill': 'Capture a key to add to the pool',
        'button_reset_filter': 'Reset',
        'label_single_skill_gcd': 'Single Skill Global Cooldown:',
        'group_skill_cooldowns': 'Individual Skill Cooldowns',
        'table_header_keybind': 'Keybind',
        'table_header_cooldown': 'Cooldown(s)',
        'suffix_seconds': ' sec',
        'skill_summary_total': 'Tracked skills',
        'skill_summary_pool': 'Pool entries',
        'skill_summary_gcd': 'Global cooldown',
        'button_add_skill': '➕ Add',
        'button_remove_skill': '➖ Remove',
        'msg_duplicate_keybind_title': 'Duplicate Keybind',
        'msg_duplicate_keybind_body': "Keybind '{keybind}' already exists!",
        'msg_failed_persist_skill': 'Failed to persist skill config to JSON: {error}',
        'combo_editor_title': 'Edit Combo Sets',
        'label_combo_sets': 'Combo Sets:',
        'button_new_combo': '➕ New Combo',
        'button_delete_combo': '➖ Delete Combo',
        'label_combo_name': 'Combo Name:',
        'checkbox_combo_enabled': 'Enabled',
        'label_combo_cooldown': 'Combo Cooldown:',
        'label_combo_delay': 'Delay Between Skills:',
        'label_combo_skills': 'Skills to Execute in Order:',
        'combo_editor_intro': (
            'Create and manage skill combo sets. Each combo set executes a sequence of skills with delays.\n'
            'Combo sets have their own cooldown timer and only execute when ALL skills are ready.'
        ),
        'button_add_skill_to_combo': '⌨️ Press Key to Add',
        'button_save_combo': '💾 Save Combo',
        'placeholder_combo_skills': (
            "Click 'Press Key to Add' button to add skills, or type manually:\n1\n2\nalt+1\n3"
        ),
        'default_combo_name': 'Combo {index}',
        'msg_combo_delete_title': 'Delete Combo',
        'msg_combo_delete_body': "Delete combo '{name}'?",
        'msg_combo_saved': "Combo '{name}' saved!",
        'msg_duplicate_skill_title': 'Duplicate Skill',
        'msg_duplicate_skill_body': "Skill '{skill}' already in pool!",
        'capture_title': 'Capture Key',
        'capture_instruction': 'Press the skill key:\n\nSupported: F1-F9, 1-9, 0, -, =',
        'capture_waiting': 'Waiting...',
        'capture_confirm': '✓ Confirm',
        'capture_cancel': '✗ Cancel',
        'capture_invalid': 'Invalid key! Use F1-F9 or 1-9, 0, -, =',
        'msg_backend_unavailable_title': 'Backend Unavailable',
        'msg_backend_unavailable_body': "Selected backend '{backend}' appears unavailable:\n\n{error}",
        'msg_persist_backend_fail': 'Failed to persist input backend to JSON: {error}',
        'msg_persist_dry_run_fail': 'Failed to persist DRY_RUN to JSON: {error}',
        'prestart_title': 'Before You Start - Read Carefully',
        'prestart_info': (
            'Please verify the following BEFORE starting the macro:\n\n'
            '- Make sure the Player is already in the hunting/farming area\n'
            '- Ensure the Interception driver is installed (the program can install it)\n'
            '- Double-check and configure your Skills and Combos (no misinputs)\n\n'
            'Recommended In-Game Settings to verify:\n'
            'Graphics -> Display Mode -> Windowed Mode\n'
            'Graphics -> Nvidia Reflex -> BOOST (if using Nvidia)\n'
            'Key Settings -> Change Target -> Tab\n'
            'Combat -> Target Search -> Preferred Direction -> Camera Forward\n'
            'Combat -> Target Search -> Advanced -> Closest target first\n'
            'Combat -> Controls -> Control Mode -> AION 1\n'
            'Combat -> Controls -> Ground click movement -> Allow both\n'
            'Combat -> Controls -> Follow target when using skills -> On\n'
            'Combat -> Controls -> Repeat basic attack -> On\n'
            'Combat -> Controls -> Auto target on skill use -> On'
        ),
        'prestart_button': 'I Understand and Done Everything',
        'prestart_remember': "Don't show this again",
        'msg_interception_missing_title': 'Interception Driver',
        'msg_interception_missing_body': (
            'Interception driver appears missing.\n'
            'Automatic installation failed or requires manual steps.\n'
            'Please install the Interception driver and reboot your PC.'
        ),
        'msg_interception_installed_title': 'Interception Installed',
        'msg_interception_installed_body': (
            'Interception driver installed. Please RESTART your computer to ensure the driver is activated.'
        ),
        'settings_language_group': 'Language',
        'settings_language_label': 'Interface language:',
        'language_english': 'English',
        'language_korean': 'Korean',
        'msg_failed_skill_json': 'Failed to persist skill config to JSON: {error}',
        'msg_failed_backend_json': 'Failed to persist input backend to JSON: {error}',
        'msg_failed_dry_run_json': 'Failed to persist DRY_RUN to JSON: {error}',
        'msg_failed_language_json': 'Failed to persist language preference: {error}',
        'log_skills_updated': '✓ Individual skills updated',
        'log_skill_config_updated': '✓ Skill combo configuration updated',
        'log_no_window_selected': 'No window selected',
        'log_unable_get_window_rect': 'Unable to get window rect',
        'log_started_detection': 'Started detection',
        'log_stopped': 'Stopped',
        'log_emergency_stop': 'EMERGENCY STOP: Automation disabled',
        'log_simulate_mode': 'Simulate mode (DRY_RUN) set to: {state}',
        'state_on': 'ON',
        'state_off': 'OFF',
        'log_hotkey_registered': 'Hotkey registered: Delete (RegisterHotKey)',
        'log_register_hotkey_failed': 'RegisterHotKey failed; falling back to low-level keyboard hook',
        'log_failed_hotkey_hook': 'Failed to install low-level keyboard hook for Delete key',
        'log_simulate_toggle_fail': 'Failed to toggle simulate mode: {error}',
        'log_backend_set_fail': 'Failed to set input backend: {error}',
        'log_backend_set': "Input backend set to: {backend}",
        'log_backend_unavailable': "Selected backend '{backend}' may be unavailable: {error}",
        'log_opened_config': '✓ Opened {path}',
        'log_config_not_found': 'Config file not found: {path}',
        'log_open_config_fail': 'Failed to open config file: {error}',
        'log_detection_start': 'Starting capture and detection',
        'log_detection_active': '✓ Automation active',
        'log_detection_stop': 'Stopping detection',
        'log_action_planner_error': 'Action planner error: {error}',
        'log_inference_error': 'Inference error: {error}',
        'language_combo_placeholder': 'Select language',
        'msg_combo_save_warning_title': 'Save Warning',
        'msg_combo_save_warning_body': (
            'Configuration updated in memory but failed to save to file:\n{error}\n\nChanges will be lost on restart.'
        ),
        'msg_combo_save_info_title': 'Saved',
        'msg_interception_warning': 'Warning',
        'msg_interception_warning_body': 'Interception folder not found. Build will continue but Interception will not be bundled.',
        'button_close': 'Close',
        'button_ok': 'OK',
    },
    'ko': {
        'app_title': 'AION 자동 실행',
        'nav_dashboard': '대시보드',
        'nav_skills': '스킬',
        'nav_combos': '콤보',
        'nav_cooldowns': '재사용 대기',
        'nav_logs': '로그',
        'nav_settings': '설정',
        'label_game_window': '게임 창:',
        'label_settings': '설정:',
        'label_settings_info': '로컬 모델 가중치 사용: models/aion.pt (Ultralytics YOLO)',
        'label_input_backend': '입력 백엔드:',
        'checkbox_simulate': '시뮬레이션 모드 (로그만 기록, 실제 입력 없음)',
        'action_refresh': '새로 고침',
        'status_available': '사용 가능',
        'status_unavailable': '사용 불가',
        'status_unknown': '알 수 없음',
        'status_tooltip_unknown': '백엔드 상태를 확인할 수 없습니다',
        'status_tooltip_available': "백엔드 '{backend}' 를 사용할 수 있습니다", 
        'status_tooltip_unavailable': '{error}',
        'group_skill_config': '스킬 콤보 설정',
        'checkbox_stealth_attack': '랜덤 공격 모드 활성화 (공격 무작위화)',
        'label_standard_weight': '일반 공격 가중치 (탭 타겟):',
        'label_single_weight': '단일 스킬 가중치:',
        'label_combo_weight': '콤보 세트 가중치:',
        'checkbox_combat_skills': '전투 중 스킬 & 콤보 사용',
        'button_edit_skills': '⚙️ 개별 스킬 편집',
        'button_edit_combos': '🎯 콤보 세트 편집',
        'button_start': '시작',
        'button_stop': '중지',
        'button_emergency_stop': '비상 정지',
        'group_cooldown_monitor': '재사용 대기 모니터',
        'skills_table_header_skill': '스킬',
        'skills_table_header_remaining': '남은 시간(초)',
        'combos_table_header_combo': '콤보',
        'combos_table_header_status': '상태',
        'status_ready': '준비됨',
        'status_unknown_value': '알 수 없음',
        'status_waiting': '대기 중',
        'status_cooldown': '재사용 {seconds}초',
        'trailing_hint_skill_pool': '팁: 드래그로 순서를 변경하고 더블클릭으로 수정하거나 캡처 버튼으로 키를 추가하세요.',
        'button_save_changes': '변경 사항 저장',
        'button_cancel': '취소',
        'skill_editor_title': '스킬 편집기',
        'skill_editor_subtitle': '플래너가 사용하는 단일 스킬 풀과 재사용 대기 시간을 관리하세요.',
        'group_single_skill_pool': '단일 스킬 풀',
        'group_skill_timing': '스킬 타이밍',
        'placeholder_skill_pool': '예: 1,2,3,f1',
        'skill_editor_search_placeholder': '스킬 키 검색...',
        'button_add_pool_skill': '추가',
        'button_remove_pool_skill': '제거',
        'tooltip_skill_pool': '싱글 스킬 선택에 사용되는 스킬 키를 쉼표로 구분하여 입력하세요',
        'tooltip_add_pool_skill': '풀에 추가할 키를 캡처합니다',
        'button_reset_filter': '초기화',
        'label_single_skill_gcd': '싱글 스킬 글로벌 쿨다운:',
        'group_skill_cooldowns': '개별 스킬 재사용 대기',
        'table_header_keybind': '키 바인딩',
        'table_header_cooldown': '재사용 대기(초)',
        'suffix_seconds': ' 초',
        'skill_summary_total': '추적 중인 스킬',
        'skill_summary_pool': '풀 항목 수',
        'skill_summary_gcd': '전역 쿨다운',
        'button_add_skill': '➕ 추가',
        'button_remove_skill': '➖ 제거',
        'msg_duplicate_keybind_title': '중복 키 바인딩',
        'msg_duplicate_keybind_body': "키 바인딩 '{keybind}' 이(가) 이미 존재합니다!",
        'msg_failed_persist_skill': '스킬 설정을 JSON에 저장하지 못했습니다: {error}',
        'combo_editor_title': '콤보 세트 편집',
        'label_combo_sets': '콤보 세트:',
        'button_new_combo': '➕ 새 콤보',
        'button_delete_combo': '➖ 콤보 삭제',
        'label_combo_name': '콤보 이름:',
        'checkbox_combo_enabled': '사용',
        'label_combo_cooldown': '콤보 재사용 대기:',
        'label_combo_delay': '스킬 간 지연:',
        'label_combo_skills': '실행 순서의 스킬:',
        'combo_editor_intro': (
            '콤보 세트를 생성하고 관리하세요. 각 콤보 세트는 지연을 두고 스킬을 순차적으로 실행합니다.\n'
            '콤보 세트는 고유 재사용 대기시간을 가지며 모든 스킬이 준비되었을 때만 실행됩니다.'
        ),
        'button_add_skill_to_combo': '⌨️ 키 입력 추가',
        'button_save_combo': '💾 콤보 저장',
        'placeholder_combo_skills': (
            "'키 입력 추가' 버튼을 눌러 스킬을 추가하거나 직접 입력하세요:\n1\n2\nalt+1\n3"
        ),
        'default_combo_name': '콤보 {index}',
        'msg_combo_delete_title': '콤보 삭제',
        'msg_combo_delete_body': "콤보 '{name}' 을(를) 삭제하시겠습니까?",
        'msg_combo_saved': "콤보 '{name}' 이(가) 저장되었습니다!",
        'msg_duplicate_skill_title': '중복 스킬',
        'msg_duplicate_skill_body': "스킬 '{skill}' 이(가) 이미 풀에 있습니다!",
        'capture_title': '키 입력',
        'capture_instruction': '스킬 키를 눌러주세요:\n\n지원: F1-F9, 1-9, 0, -, =',
        'capture_waiting': '대기 중...',
        'capture_confirm': '✓ 확인',
        'capture_cancel': '✗ 취소',
        'capture_invalid': '잘못된 키입니다! F1-F9 또는 1-9, 0, -, =을 사용하세요',
        'msg_backend_unavailable_title': '백엔드 사용 불가',
        'msg_backend_unavailable_body': "선택한 백엔드 '{backend}' 를 사용할 수 없습니다:\n\n{error}",
        'msg_persist_backend_fail': '입력 백엔드를 JSON에 저장하지 못했습니다: {error}',
        'msg_persist_dry_run_fail': 'DRY_RUN 값을 JSON에 저장하지 못했습니다: {error}',
        'prestart_title': '시작 전에 반드시 확인하세요',
        'prestart_info': (
            '매크로를 시작하기 전에 다음을 확인하세요:\n\n'
            '- 게임이 창 모드로 실행 중인지 확인하세요\n'
            '- 사냥/파밍 지역에 캐릭터가 배치되어 있는지 확인하세요\n'
            '- Interception 드라이버가 설치되어 있는지 확인하세요 (프로그램에서 설치 가능)\n'
            '- 스킬 및 콤보 구성을 다시 확인하세요 (잘못된 입력 방지)\n\n'
            '권장 인게임 설정:\n'
            '그래픽 -> 표시 모드 -> 창 모드\n'
            '그래픽 -> Nvidia Reflex -> BOOST (Nvidia 사용 시)\n'
            '키 설정 -> 타겟 변경 -> Tab 키\n'
            '전투 -> 타겟 탐색 -> 우선 탐색 방향 -> 카메라 전방\n'
            '전투 -> 타겟 탐색 -> 세부 설정 -> 가장 가까운 대상 우선\n'
            '전투 -> 조작 -> 조작 모드 -> AION 1\n'
            '전투 -> 조작 -> 지면 클릭 이동 -> 양쪽 허용\n'
            '전투 -> 조작 -> 스킬 사용 시 대상 추적 -> 켬\n'
            '전투 -> 조작 -> 기본 공격 반복 사용 -> 켬\n'
            '전투 -> 조작 -> 스킬 사용 시 자동 타겟 -> 켬'
        ),
        'prestart_button': '모두 완료했습니다',
        'prestart_remember': '다시 표시하지 않기',
        'msg_interception_missing_title': 'Interception 드라이버',
        'msg_interception_missing_body': (
            'Interception 드라이버가 설치되지 않은 것으로 보입니다.\n'
            '자동 설치가 실패했거나 추가 단계가 필요합니다.\n'
            'Interception 드라이버를 설치한 후 PC를 재부팅하세요.'
        ),
        'msg_interception_installed_title': 'Interception 설치 완료',
        'msg_interception_installed_body': (
            'Interception 드라이버가 설치되었습니다. 드라이버 활성화를 위해 PC를 반드시 재부팅하세요.'
        ),
        'settings_language_group': '언어',
        'settings_language_label': '인터페이스 언어:',
        'language_english': '영어',
        'language_korean': '한국어',
        'msg_failed_skill_json': '스킬 설정을 JSON에 저장하지 못했습니다: {error}',
        'msg_failed_backend_json': '입력 백엔드를 JSON에 저장하지 못했습니다: {error}',
        'msg_failed_dry_run_json': 'DRY_RUN 값을 JSON에 저장하지 못했습니다: {error}',
        'msg_failed_language_json': '언어 설정을 저장하지 못했습니다: {error}',
        'log_skills_updated': '✓ 개별 스킬이 업데이트되었습니다',
        'log_skill_config_updated': '✓ 스킬 콤보 구성이 업데이트되었습니다',
        'log_no_window_selected': '선택된 창이 없습니다',
        'log_unable_get_window_rect': '창 위치를 가져올 수 없습니다',
        'log_started_detection': '감지를 시작했습니다',
        'log_stopped': '정지했습니다',
        'log_emergency_stop': '긴급 정지: 자동화 비활성화',
        'log_simulate_mode': '시뮬레이션 모드 (DRY_RUN) 상태: {state}',
        'state_on': '켬',
        'state_off': '끔',
        'log_hotkey_registered': '단축키 등록됨: Delete (RegisterHotKey)',
        'log_register_hotkey_failed': 'RegisterHotKey 실패: 저수준 키보드 후크로 전환합니다',
        'log_failed_hotkey_hook': 'Delete 키에 대한 저수준 키보드 후크 설치에 실패했습니다',
        'log_simulate_toggle_fail': '시뮬레이션 모드를 전환하지 못했습니다: {error}',
        'log_backend_set_fail': '입력 백엔드를 설정하지 못했습니다: {error}',
        'log_backend_set': "입력 백엔드를 설정했습니다: {backend}",
        'log_backend_unavailable': "선택한 입력 백엔드 '{backend}' 를 사용할 수 없을 수 있습니다: {error}",
        'log_opened_config': '✓ {path} 파일을 열었습니다',
        'log_config_not_found': '구성 파일을 찾을 수 없습니다: {path}',
        'log_open_config_fail': '구성 파일을 열지 못했습니다: {error}',
        'log_detection_start': '캡처 및 감지를 시작합니다',
        'log_detection_active': '✓ 자동화가 활성화되었습니다',
        'log_detection_stop': '감지를 중지합니다',
        'log_action_planner_error': '액션 플래너 오류: {error}',
        'log_inference_error': '추론 오류: {error}',
        'language_combo_placeholder': '언어 선택',
        'msg_combo_save_warning_title': '저장 경고',
        'msg_combo_save_warning_body': (
            '구성이 메모리에만 업데이트되었고 파일 저장에 실패했습니다:\n{error}\n\n재시작 시 변경 사항이 사라집니다.'
        ),
        'msg_combo_save_info_title': '저장 완료',
        'msg_interception_warning': '경고',
        'msg_interception_warning_body': 'Interception 폴더를 찾을 수 없습니다. 빌드는 계속되지만 Interception이 포함되지 않습니다.',
        'button_close': '닫기',
        'button_ok': '확인',
    },
}


def translate_text(language: str, key: str, **kwargs) -> str:
    lang_map = TRANSLATIONS.get(language, TRANSLATIONS.get('en', {}))
    text = lang_map.get(key)
    if text is None:
        text = TRANSLATIONS['en'].get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except Exception:
            pass
    return text


def is_admin():
    """Check if the program is running with administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def run_as_admin():
    """Restart the program with administrator privileges."""
    try:
        # Build the full command line: script path + any additional arguments
        # sys.argv[0] is the script being run (main.py)
        script_path = os.path.abspath(sys.argv[0])
        # Build quoted argument string including the script itself
        args = f'"{script_path}"'
        if len(sys.argv) > 1:
            args += ' ' + ' '.join([f'"{arg}"' for arg in sys.argv[1:]])
        
        # Use the current Python executable (this will be the venv interpreter when using the venv)
        # ShellExecuteW with verb "runas" prompts for elevation and starts a new elevated process.
        ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, args, os.getcwd(), 1)
        # ShellExecuteW returns a value > 32 on success
        if int(ret) <= 32:
            raise OSError(f"ShellExecuteW failed with code {ret}")
        # If ShellExecute succeeded we should exit this (non-elevated) process so only elevated instance runs
        sys.exit(0)
    except Exception as e:
        logger.error(f"Failed to elevate privileges: {e}")
        return False
    return True


class MainWindow(QtWidgets.QMainWindow):
    stop_shortcut_pressed = QtCore.Signal()

    def __init__(self):
        super().__init__()
        try:
            import skill_combo_config as scc
        except Exception:
            scc = None
        self._config_module = scc
        lang = 'en'
        if scc is not None:
            lang = getattr(scc, 'LANGUAGE', 'en') or 'en'
        self.current_language = lang
        self._translatables = []
        self._register_translatable(self.setWindowTitle, 'app_title')
        self.setWindowTitle(self.tr('app_title'))
        self.resize(900, 640)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        # Main layout: left navigation sidebar + right stacked pages
        main_h = QtWidgets.QHBoxLayout(central)

        # Sidebar (navigation)
        self.sidebar = QtWidgets.QWidget()
        self.sidebar.setFixedWidth(180)
        sb_layout = QtWidgets.QVBoxLayout(self.sidebar)
        sb_layout.setContentsMargins(8, 8, 8, 8)
        sb_layout.setSpacing(12)

        # Create nav buttons
        def _nav_btn(text):
            b = QtWidgets.QPushButton(text)
            b.setCursor(QtCore.Qt.PointingHandCursor)
            b.setCheckable(True)
            b.setStyleSheet(self._nav_button_style())
            b.setFixedHeight(44)
            return b

        self.btn_dashboard = _nav_btn(self.tr('nav_dashboard'))
        self.btn_skills = _nav_btn(self.tr('nav_skills'))
        self.btn_combos = _nav_btn(self.tr('nav_combos'))
        self.btn_cooldowns = _nav_btn(self.tr('nav_cooldowns'))
        self.btn_settings = _nav_btn(self.tr('nav_settings'))
        self._register_translatable(self.btn_dashboard.setText, 'nav_dashboard')
        self._register_translatable(self.btn_skills.setText, 'nav_skills')
        self._register_translatable(self.btn_combos.setText, 'nav_combos')
        self._register_translatable(self.btn_cooldowns.setText, 'nav_cooldowns')
        self._register_translatable(self.btn_settings.setText, 'nav_settings')

        for b in (self.btn_dashboard, self.btn_skills, self.btn_combos, self.btn_cooldowns, self.btn_settings):
            sb_layout.addWidget(b)
        sb_layout.addStretch()

        # Right side: stacked pages
        self.pages = QtWidgets.QStackedWidget()
        self.pages.setObjectName('pages')

        main_h.addWidget(self.sidebar)
        main_h.addWidget(self.pages, stretch=1)

        # Create pages
        self.page_dashboard = QtWidgets.QWidget()
        self.page_skills = QtWidgets.QWidget()
        self.page_combos = QtWidgets.QWidget()
        self.page_cooldowns = QtWidgets.QWidget()
        self.page_settings = QtWidgets.QWidget()

        self.page_dashboard_layout = QtWidgets.QVBoxLayout(self.page_dashboard)
        self.page_skills_layout = QtWidgets.QVBoxLayout(self.page_skills)
        self.page_combos_layout = QtWidgets.QVBoxLayout(self.page_combos)
        self.page_cooldowns_layout = QtWidgets.QVBoxLayout(self.page_cooldowns)
        self.page_settings_layout = QtWidgets.QVBoxLayout(self.page_settings)

        for p in (self.page_dashboard, self.page_skills, self.page_combos, self.page_cooldowns, self.page_settings):
            self.pages.addWidget(p)

        # Connect nav buttons
        self.btn_dashboard.clicked.connect(lambda: self.change_page(0))
        self.btn_skills.clicked.connect(lambda: self.change_page(1))
        self.btn_combos.clicked.connect(lambda: self.change_page(2))
        self.btn_cooldowns.clicked.connect(lambda: self.change_page(3))
        self.btn_settings.clicked.connect(lambda: self.change_page(4))

        # Select dashboard by default
        self.btn_dashboard.setChecked(True)
        self.pages.setCurrentIndex(0)

        # top controls (placed on Dashboard page)
        form = QtWidgets.QFormLayout()
        self.win_combo = QtWidgets.QComboBox()
        self.refresh_btn = QtWidgets.QPushButton()
        self._register_translatable(self.refresh_btn.setText, 'action_refresh')
        self.refresh_btn.setText(self.tr('action_refresh'))
        self.refresh_btn.clicked.connect(self._refresh_windows)
        h = QtWidgets.QHBoxLayout()
        h.addWidget(self.win_combo)
        h.addWidget(self.refresh_btn)
        self.label_game_window = QtWidgets.QLabel(self.tr('label_game_window'))
        self._register_translatable(self.label_game_window.setText, 'label_game_window')
        form.addRow(self.label_game_window, h)

        # Using local model weights placed at models/aion.pt
        self.settings_info_label = QtWidgets.QLabel(self.tr('label_settings_info'))
        self.settings_info_label.setWordWrap(True)
        self._register_translatable(self.settings_info_label.setText, 'label_settings_info')
        self.label_settings = QtWidgets.QLabel(self.tr('label_settings'))
        self._register_translatable(self.label_settings.setText, 'label_settings')
        form.addRow(self.label_settings, self.settings_info_label)

        # Input backend controls (UI toggle)
        backend_layout = QtWidgets.QHBoxLayout()
        self.backend_combo = QtWidgets.QComboBox()
        # Available backends (interception-only build)
        self.backend_combo.addItems(['interception'])
        # Use stored config if present, otherwise reflect runtime value
        try:
            import skill_combo_config as scc
            initial_backend = getattr(scc, 'INPUT_BACKEND', ic.INPUT_BACKEND)
        except Exception:
            initial_backend = ic.INPUT_BACKEND
        idx = self.backend_combo.findText(initial_backend)
        if idx >= 0:
            self.backend_combo.setCurrentIndex(idx)
        self.backend_combo.currentTextChanged.connect(self._on_backend_changed)

        self.simulate_cb = QtWidgets.QCheckBox()
        self._register_translatable(self.simulate_cb.setText, 'checkbox_simulate')
        self.simulate_cb.setText(self.tr('checkbox_simulate'))
        try:
            initial_dry = getattr(scc, 'INPUT_DRY_RUN', ic.INPUT_DRY_RUN)
        except Exception:
            initial_dry = ic.INPUT_DRY_RUN
        self.simulate_cb.setChecked(bool(initial_dry))
        self.simulate_cb.toggled.connect(self._on_dry_run_toggled)

        # Small status indicator for backend availability
        self.backend_status = QtWidgets.QLabel("")
        self.backend_status.setFixedWidth(140)
        backend_layout.addWidget(self.backend_combo)
        backend_layout.addWidget(self.backend_status)
        backend_layout.addWidget(self.simulate_cb)
        self.label_input_backend = QtWidgets.QLabel(self.tr('label_input_backend'))
        self._register_translatable(self.label_input_backend.setText, 'label_input_backend')
        form.addRow(self.label_input_backend, backend_layout)

        # initialize backend status indicator
        try:
            self._update_backend_status(initial_backend)
        except Exception:
            pass

        # Add the top form to the dashboard page
        self.page_dashboard_layout.addLayout(form)

        # Show action feedback directly below Simulate mode and above Start/Stop.
        self.log_view = QtWidgets.QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(160)
        self.page_dashboard_layout.addWidget(self.log_view, stretch=1)

        # Skill Combo Configuration Section
        skill_group = QtWidgets.QGroupBox()
        self._register_translatable(skill_group.setTitle, 'group_skill_config')
        skill_group.setTitle(self.tr('group_skill_config'))
        skill_layout = QtWidgets.QVBoxLayout()
        
        # Load existing configuration
        import skill_combo_config
        
        # Attack mode randomization checkbox
        self.stealth_attack_cb = QtWidgets.QCheckBox()
        self._register_translatable(self.stealth_attack_cb.setText, 'checkbox_stealth_attack')
        self.stealth_attack_cb.setText(self.tr('checkbox_stealth_attack'))
        self.stealth_attack_cb.setChecked(skill_combo_config.STEALTH_ATTACK_MODE_ENABLED)
        self.stealth_attack_cb.stateChanged.connect(self._update_skill_config)
        skill_layout.addWidget(self.stealth_attack_cb)
        
        # Attack mode weights
        weights_layout = QtWidgets.QFormLayout()
        self.standard_attack_weight = QtWidgets.QDoubleSpinBox()
        self.standard_attack_weight.setRange(0.0, 1.0)
        self.standard_attack_weight.setSingleStep(0.05)
        self.standard_attack_weight.setValue(skill_combo_config.ATTACK_MODE_WEIGHTS.get('standard_attack', 0.50))
        self.standard_attack_weight.setSuffix(f" ({int(skill_combo_config.ATTACK_MODE_WEIGHTS.get('standard_attack', 0.50)*100)}%)")
        self.standard_attack_weight.valueChanged.connect(lambda v: self.standard_attack_weight.setSuffix(f" ({int(v*100)}%)"))
        self.standard_attack_weight.valueChanged.connect(self._update_skill_config)
        label_standard = QtWidgets.QLabel(self.tr('label_standard_weight'))
        self._register_translatable(label_standard.setText, 'label_standard_weight')
        weights_layout.addRow(label_standard, self.standard_attack_weight)
        
        self.single_skill_weight = QtWidgets.QDoubleSpinBox()
        self.single_skill_weight.setRange(0.0, 1.0)
        self.single_skill_weight.setSingleStep(0.05)
        self.single_skill_weight.setValue(skill_combo_config.ATTACK_MODE_WEIGHTS.get('single_skill', 0.30))
        self.single_skill_weight.setSuffix(f" ({int(skill_combo_config.ATTACK_MODE_WEIGHTS.get('single_skill', 0.30)*100)}%)")
        self.single_skill_weight.valueChanged.connect(lambda v: self.single_skill_weight.setSuffix(f" ({int(v*100)}%)"))
        self.single_skill_weight.valueChanged.connect(self._update_skill_config)
        label_single = QtWidgets.QLabel(self.tr('label_single_weight'))
        self._register_translatable(label_single.setText, 'label_single_weight')
        weights_layout.addRow(label_single, self.single_skill_weight)
        
        self.combo_set_weight = QtWidgets.QDoubleSpinBox()
        self.combo_set_weight.setRange(0.0, 1.0)
        self.combo_set_weight.setSingleStep(0.05)
        self.combo_set_weight.setValue(skill_combo_config.ATTACK_MODE_WEIGHTS.get('combo_set', 0.20))
        self.combo_set_weight.setSuffix(f" ({int(skill_combo_config.ATTACK_MODE_WEIGHTS.get('combo_set', 0.20)*100)}%)")
        self.combo_set_weight.valueChanged.connect(lambda v: self.combo_set_weight.setSuffix(f" ({int(v*100)}%)"))
        self.combo_set_weight.valueChanged.connect(self._update_skill_config)
        label_combo_weight = QtWidgets.QLabel(self.tr('label_combo_weight'))
        self._register_translatable(label_combo_weight.setText, 'label_combo_weight')
        weights_layout.addRow(label_combo_weight, self.combo_set_weight)
        
        skill_layout.addLayout(weights_layout)
        
        # Combat skills & combos toggle
        self.combat_skills_cb = QtWidgets.QCheckBox()
        self._register_translatable(self.combat_skills_cb.setText, 'checkbox_combat_skills')
        self.combat_skills_cb.setText(self.tr('checkbox_combat_skills'))
        # New config key: COMBAT_USE_SKILLS
        self.combat_skills_cb.setChecked(getattr(skill_combo_config, 'COMBAT_USE_SKILLS', True))
        self.combat_skills_cb.stateChanged.connect(self._update_skill_config)
        skill_layout.addWidget(self.combat_skills_cb)
        
        # Configuration buttons in a horizontal layout
        config_buttons_layout = QtWidgets.QHBoxLayout()
        
        # Edit Individual Skills button
        # edit_skills_btn = QtWidgets.QPushButton("⚙️ Edit Individual Skills")
        # edit_skills_btn.setStyleSheet("QPushButton { background-color: #2196F3; color: white; font-weight: bold; padding: 8px; }")
        # # Navigate to the Skills screen (embedded editor) instead of opening a dialog
        # edit_skills_btn.clicked.connect(lambda: self.change_page(1))
        # config_buttons_layout.addWidget(edit_skills_btn)
        
        # Edit Combo Sets button
        edit_combos_btn = QtWidgets.QPushButton()
        self._register_translatable(edit_combos_btn.setText, 'button_edit_combos')
        edit_combos_btn.setText(self.tr('button_edit_combos'))
        edit_combos_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px; }")
        # Navigate to the Combos screen (embedded editor) instead of opening a dialog
        edit_combos_btn.clicked.connect(lambda: self.change_page(2))
        config_buttons_layout.addWidget(edit_combos_btn)
        
        skill_layout.addLayout(config_buttons_layout)
        
        skill_group.setLayout(skill_layout)
        # Add skill group to Skills page
        self.page_skills_layout.addWidget(skill_group)
        # Embed the full skill editor as a screen under the Skills page
        try:
            self.skill_editor_screen = SkillEditorScreen(self)
            self.page_skills_layout.addWidget(self.skill_editor_screen)
        except Exception:
            pass
        # Cooldown monitor panel placed on Cooldowns page
        self._setup_cooldown_panel(self.page_cooldowns_layout)
        # Embed the combo editor on the Combos page
        try:
            self.combo_editor_screen = ComboEditorScreen(self)
            self.page_combos_layout.addWidget(self.combo_editor_screen)
        except Exception:
            pass

        # Build settings page content (language selector, etc.)
        self._build_settings_page()

        # Anti-detection GUI removed (no stealth_config support)

        # Start/Stop and Emergency Stop
        btns = QtWidgets.QHBoxLayout()
        self.start_btn = QtWidgets.QPushButton()
        self._register_translatable(self.start_btn.setText, 'button_start')
        self.start_btn.setText(self.tr('button_start'))
        self.stop_btn = QtWidgets.QPushButton()
        self._register_translatable(self.stop_btn.setText, 'button_stop')
        self.stop_btn.setText(self.tr('button_stop'))
        self.emergency_stop_btn = QtWidgets.QPushButton()
        self._register_translatable(self.emergency_stop_btn.setText, 'button_emergency_stop')
        self.emergency_stop_btn.setText(self.tr('button_emergency_stop'))
        self.emergency_stop_btn.setStyleSheet("QPushButton { background-color: red; color: white; font-weight: bold; }")
        self.emergency_stop_btn.clicked.connect(self.emergency_stop)
        self.stop_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.start)
        self.stop_btn.clicked.connect(self.stop)
        btns.addWidget(self.start_btn)
        btns.addWidget(self.stop_btn)
        btns.addWidget(self.emergency_stop_btn)
        # Start/Stop buttons go on Dashboard page
        self.page_dashboard_layout.addLayout(btns)

        self.auto_loot_cb = QtWidgets.QCheckBox()
        self._register_translatable(self.auto_loot_cb.setText, 'checkbox_auto_loot')
        self.auto_loot_cb.setText(self.tr('checkbox_auto_loot'))
        self.auto_loot_cb.setToolTip('Enable when the game loots automatically; skips F-key looting and its cooldown.')
        self.auto_loot_cb.setChecked(skill_combo_config.AUTO_LOOT)
        self.auto_loot_cb.toggled.connect(self._update_auto_loot)
        self.page_dashboard_layout.addWidget(self.auto_loot_cb)

        self.sentry_mode_cb = QtWidgets.QCheckBox()
        self._register_translatable(self.sentry_mode_cb.setText, 'checkbox_sentry_mode')
        self.sentry_mode_cb.setText(self.tr('checkbox_sentry_mode'))
        self.sentry_mode_cb.setToolTip('Select with Tab; attack only with a fresh distance of 15 m or less. Clear distant or unreadable targets and rotate to search. No movement keys.')
        self.sentry_mode_cb.setChecked(skill_combo_config.SENTRY_MODE)
        self.sentry_mode_cb.toggled.connect(self._update_sentry_mode)
        self.page_dashboard_layout.addWidget(self.sentry_mode_cb)

        self.farming_mode_cb = QtWidgets.QCheckBox()
        self._register_translatable(self.farming_mode_cb.setText, 'checkbox_farming_mode')
        self.farming_mode_cb.setText(self.tr('checkbox_farming_mode'))
        self.farming_mode_cb.setToolTip('Press F once per second. Overrides combat, movement, Sentry Mode, and Auto loot.')
        self.farming_mode_cb.setChecked(skill_combo_config.FARMING_MODE)
        self.farming_mode_cb.toggled.connect(self._update_farming_mode)
        self.page_dashboard_layout.addWidget(self.farming_mode_cb)

        # track desired automation state (applies to controller when created)
        # Default automation ON as requested
        self._automation_enabled = True
        self._overlay = OverlayWindow()
        # ensure overlay matches the desired automation default immediately
        try:
            self._overlay.set_automation_enabled(self._automation_enabled)
        except Exception:
            pass
        self._controller = None
        self.stop_shortcut_pressed.connect(self.stop, QtCore.Qt.QueuedConnection)
        self._start_stop_hotkey_listener()
        # Start the existing Delete shortcut to toggle automation.
        self._hotkey_thread = None
        self._start_hotkey_listener()
        self._pos_timer = QtCore.QTimer(self)
        self._pos_timer.setInterval(300)  # ms
        self._pos_timer.timeout.connect(self._reposition_overlay)

        self._refresh_windows()
        self._apply_translations()

    def _setup_cooldown_panel(self, parent_layout):
        """Create a small panel showing skill/combo cooldowns."""
        cooldown_group = QtWidgets.QGroupBox()
        self._register_translatable(cooldown_group.setTitle, 'group_cooldown_monitor')
        cooldown_group.setTitle(self.tr('group_cooldown_monitor'))
        self._cooldown_group = cooldown_group
        v = QtWidgets.QVBoxLayout()

        # Skills table
        self._skills_table = QtWidgets.QTableWidget(0, 2)
        self._skills_table.setHorizontalHeaderLabels([
            self.tr('skills_table_header_skill'),
            self.tr('skills_table_header_remaining')
        ])
        self._skills_table.horizontalHeader().setStretchLastSection(True)
        v.addWidget(self._skills_table)

        # Combos table
        self._combos_table = QtWidgets.QTableWidget(0, 2)
        self._combos_table.setHorizontalHeaderLabels([
            self.tr('combos_table_header_combo'),
            self.tr('combos_table_header_status')
        ])
        self._combos_table.horizontalHeader().setStretchLastSection(True)
        v.addWidget(self._combos_table)

        cooldown_group.setLayout(v)
        parent_layout.addWidget(cooldown_group)

        # Timer to refresh cooldowns periodically
        self._cooldown_timer = QtCore.QTimer(self)
        self._cooldown_timer.setInterval(500)
        self._cooldown_timer.timeout.connect(self._refresh_cooldown_panel)

    def _build_settings_page(self):
        self.page_settings_layout.setSpacing(12)
        language_group = QtWidgets.QGroupBox()
        self._register_translatable(language_group.setTitle, 'settings_language_group')
        language_group.setTitle(self.tr('settings_language_group'))

        language_layout = QtWidgets.QFormLayout()
        self.language_label = QtWidgets.QLabel(self.tr('settings_language_label'))
        self._register_translatable(self.language_label.setText, 'settings_language_label')

        self.language_combo = QtWidgets.QComboBox()
        self._language_items = [('en', 'language_english'), ('ko', 'language_korean')]
        for code, key in self._language_items:
            self.language_combo.addItem(self.tr(key), code)
        idx = self.language_combo.findData(self.current_language)
        if idx >= 0:
            self.language_combo.setCurrentIndex(idx)
        else:
            self.language_combo.setCurrentIndex(0)
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)

        language_layout.addRow(self.language_label, self.language_combo)
        language_group.setLayout(language_layout)
        self.page_settings_layout.addWidget(language_group)
        self.page_settings_layout.addStretch(1)

    def _retranslate_language_combo(self):
        if not hasattr(self, 'language_combo'):
            return
        for idx, (code, key) in enumerate(getattr(self, '_language_items', [])):
            if idx < self.language_combo.count():
                try:
                    self.language_combo.setItemText(idx, self.tr(key))
                except Exception:
                    pass

    def _retranslate_tables(self):
        if hasattr(self, '_skills_table'):
            self._skills_table.setHorizontalHeaderLabels([
                self.tr('skills_table_header_skill'),
                self.tr('skills_table_header_remaining')
            ])
        if hasattr(self, '_combos_table'):
            self._combos_table.setHorizontalHeaderLabels([
                self.tr('combos_table_header_combo'),
                self.tr('combos_table_header_status')
            ])
        if hasattr(self, '_cooldown_group'):
            try:
                self._cooldown_group.setTitle(self.tr('group_cooldown_monitor'))
            except Exception:
                pass

    def _on_language_changed(self):
        if not hasattr(self, 'language_combo'):
            return
        lang = self.language_combo.currentData()
        if not lang or lang == self.current_language:
            return
        self.current_language = lang
        self._apply_translations()
        self._persist_language_setting(lang)

    def _persist_language_setting(self, lang: str):
        if not self._config_module:
            return
        try:
            self._config_module.update_config({'LANGUAGE': lang})
        except Exception as e:
            try:
                self.log(self.tr('msg_failed_language_json').format(error=e))
            except Exception:
                pass

    def tr(self, key: str, disambiguation=None, n=-1, **kwargs):  # type: ignore[override]
        return translate_text(self.current_language, key, **kwargs)

    def _register_translatable(self, setter, key: str):
        if not hasattr(self, '_translatables'):
            self._translatables = []
        self._translatables.append((setter, key))

    def _apply_translations(self):
        for setter, key in getattr(self, '_translatables', []):
            try:
                setter(self.tr(key))
            except Exception:
                pass
        # Update elements that require custom handling
        self._retranslate_language_combo()
        self._retranslate_tables()
        try:
            backend = self.backend_combo.currentText()
            if backend:
                self._update_backend_status(backend)
        except Exception:
            pass
        for attr in ('skill_editor_screen', 'combo_editor_screen'):
            screen = getattr(self, attr, None)
            if screen and hasattr(screen, 'apply_translations'):
                try:
                    screen.apply_translations(self.current_language)
                except Exception:
                    pass

    def _nav_button_style(self) -> str:
        """Return stylesheet for sidebar nav buttons (modern purple theme)."""
        return (
            "QPushButton { background-color: transparent; color: #EDE7F6; border: none; text-align: left; "
            "padding-left: 12px; font-size: 12pt; }"
            "QPushButton:checked { background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #6A1B9A, stop:1 #8E24AA); "
            "border-radius: 6px; color: white; font-weight: bold; }"
            "QPushButton:hover { background-color: rgba(255,255,255,0.03); }"
        )

    def change_page(self, index: int):
        """Animate transition and switch to the given page index."""
        # Immediate, robust page switch without animations to ensure reliability.
        try:
            if index < 0 or index >= self.pages.count():
                return
            self.pages.setCurrentIndex(index)
            # update sidebar checked state
            for i, btn in enumerate((self.btn_dashboard, self.btn_skills, self.btn_combos, self.btn_cooldowns, self.btn_settings)):
                try:
                    btn.setChecked(i == index)
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"change_page failed: {e}")

    def log(self, text: str):
        # append thread-safely
        localized = self._localize_log(text)
        QtCore.QMetaObject.invokeMethod(
            self.log_view,
            "appendPlainText",
            QtCore.Qt.QueuedConnection,
            QtCore.Q_ARG(str, localized)
        )

    def _localize_log(self, text: str) -> str:
        mapping = {
            "Starting capture and detection": 'log_detection_start',
            "✓ Automation active": 'log_detection_active',
            "Stopping detection": 'log_detection_stop',
            "No window selected": 'log_no_window_selected',
            "Unable to get window rect": 'log_unable_get_window_rect',
            "Started detection": 'log_started_detection',
            "Stopped": 'log_stopped',
            "EMERGENCY STOP: Automation disabled": 'log_emergency_stop',
            "Hotkey registered: Delete (RegisterHotKey)": 'log_hotkey_registered',
            "RegisterHotKey failed; falling back to low-level keyboard hook": 'log_register_hotkey_failed',
            "Failed to install low-level keyboard hook for Delete key": 'log_failed_hotkey_hook',
            "✓ Skill combo configuration updated": 'log_skill_config_updated',
        }
        if text in mapping:
            return self.tr(mapping[text])
        if text.startswith("Simulate mode (DRY_RUN) set to:"):
            state_value = text.split(":", 1)[1].strip()
            state_key = 'state_on' if state_value.lower() in ('true', 'on', '1', 'yes', '켬') else 'state_off'
            return self.tr('log_simulate_mode').format(state=self.tr(state_key))
        if text.startswith("Failed to toggle simulate mode:"):
            error = text.split(":", 1)[1].strip()
            return self.tr('log_simulate_toggle_fail').format(error=error)
        if text.startswith("Failed to set input backend:"):
            error = text.split(":", 1)[1].strip()
            return self.tr('log_backend_set_fail').format(error=error)
        if text.startswith("Failed to persist input backend to JSON:"):
            error = text.split(":", 1)[1].strip()
            return self.tr('msg_failed_backend_json').format(error=error)
        if text.startswith("Failed to persist DRY_RUN to JSON:"):
            error = text.split(":", 1)[1].strip()
            return self.tr('msg_failed_dry_run_json').format(error=error)
        if text.startswith("Action planner error:"):
            error = text.split(":", 1)[1].strip()
            return self.tr('log_action_planner_error').format(error=error)
        if text.startswith("Inference error:"):
            error = text.split(":", 1)[1].strip()
            return self.tr('log_inference_error').format(error=error)
        if text.startswith("✓ Opened ") and '{' not in text:
            path = text.replace('✓ Opened ', '', 1).strip()
            return self.tr('log_opened_config').format(path=path)
        if text.startswith("Config file not found:"):
            path = text.split(":", 1)[1].strip()
            return self.tr('log_config_not_found').format(path=path)
        if text.startswith("Failed to open config file:"):
            error = text.split(":", 1)[1].strip()
            return self.tr('log_open_config_fail').format(error=error)
        return text

    def _update_auto_loot(self, enabled):
        import skill_combo_config
        skill_combo_config.update_config({'AUTO_LOOT': bool(enabled)})

    def _update_sentry_mode(self, enabled):
        import skill_combo_config
        skill_combo_config.update_config({'SENTRY_MODE': bool(enabled)})
        if self._controller is not None:
            self._controller.action_planner.set_sentry_mode(enabled)

    def _update_farming_mode(self, enabled):
        import skill_combo_config
        skill_combo_config.update_config({'FARMING_MODE': bool(enabled)})
        if self._controller is not None:
            self._controller.action_planner.set_farming_mode(enabled)

    def _update_skill_config(self):
        """Update skill combo configuration based on GUI settings."""
        try:
            import skill_combo_config
            
            # Update stealth attack mode
            skill_combo_config.STEALTH_ATTACK_MODE_ENABLED = self.stealth_attack_cb.isChecked()
            # Update combat skill usage toggle
            skill_combo_config.COMBAT_USE_SKILLS = self.combat_skills_cb.isChecked()
            
            # Update attack mode weights
            skill_combo_config.ATTACK_MODE_WEIGHTS['standard_attack'] = self.standard_attack_weight.value()
            skill_combo_config.ATTACK_MODE_WEIGHTS['single_skill'] = self.single_skill_weight.value()
            skill_combo_config.ATTACK_MODE_WEIGHTS['combo_set'] = self.combo_set_weight.value()
            
            # Update health requirement
            # Persist to JSON-backed config for durability
            try:
                skill_combo_config.update_config({
                    'STEALTH_ATTACK_MODE_ENABLED': skill_combo_config.STEALTH_ATTACK_MODE_ENABLED,
                    'ATTACK_MODE_WEIGHTS': skill_combo_config.ATTACK_MODE_WEIGHTS,
                    'COMBAT_USE_SKILLS': skill_combo_config.COMBAT_USE_SKILLS,
                })
            except Exception as e:
                self.log(f"Failed to persist skill config to JSON: {e}")
            else:
                self.log(self.tr('log_skill_config_updated'))
        except Exception as e:
            self.log(f"Failed to update skill config: {e}")
    
    def _save_main_config_to_file(self):
        """Save main window configuration to file."""
        try:
            import skill_combo_config
            import os
            config_path = os.path.join(os.path.dirname(__file__), 'skill_combo_config.py')
            
            # Read the current file
            with open(config_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Find and replace configuration values
            new_lines = []
            
            for i, line in enumerate(lines):
                # Replace STEALTH_ATTACK_MODE_ENABLED
                if 'STEALTH_ATTACK_MODE_ENABLED = ' in line and not line.strip().startswith('#'):
                    new_lines.append(f'STEALTH_ATTACK_MODE_ENABLED = {skill_combo_config.STEALTH_ATTACK_MODE_ENABLED}\n')
                
                # Replace ATTACK_MODE_WEIGHTS dictionary
                elif 'ATTACK_MODE_WEIGHTS = {' in line:
                    new_lines.append('ATTACK_MODE_WEIGHTS = {\n')
                    new_lines.append(f"    'standard_attack': {skill_combo_config.ATTACK_MODE_WEIGHTS['standard_attack']},\n")
                    new_lines.append(f"    'single_skill': {skill_combo_config.ATTACK_MODE_WEIGHTS['single_skill']},\n")
                    new_lines.append(f"    'combo_set': {skill_combo_config.ATTACK_MODE_WEIGHTS['combo_set']},\n")
                    new_lines.append('}\n')
                    # Skip old dictionary content
                    while i < len(lines) - 1 and '}' not in lines[i]:
                        i += 1
                
                else:
                    new_lines.append(line)
            
            # Also ensure INPUT_BACKEND / INPUT_DRY_RUN entries are updated
            backend_written = False
            dry_written = False
            for i, line in enumerate(new_lines):
                if 'INPUT_BACKEND = ' in line and not line.strip().startswith('#'):
                    new_lines[i] = f"INPUT_BACKEND = '{ic.INPUT_BACKEND}'\n"
                    backend_written = True
                if 'INPUT_DRY_RUN = ' in line and not line.strip().startswith('#'):
                    new_lines[i] = f"INPUT_DRY_RUN = {ic.INPUT_DRY_RUN}\n"
                    dry_written = True

            if not backend_written:
                new_lines.append('\n# Input backend (interception)\n')
                new_lines.append(f"INPUT_BACKEND = '{ic.INPUT_BACKEND}'\n")
            if not dry_written:
                new_lines.append(f"INPUT_DRY_RUN = {ic.INPUT_DRY_RUN}\n")

            # Write back to file
            with open(config_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            
            logger.info("✓ Main configuration saved to file")
            
        except Exception as e:
            logger.error(f"Failed to save main configuration to file: {e}")

    def _refresh_cooldown_panel(self):
        """Refresh the cooldown tables from the runtime SkillComboManager if available."""
        scm = None
        try:
            if self._controller and hasattr(self._controller, 'action_planner'):
                scm = getattr(self._controller.action_planner, 'skill_combo_manager', None)
        except Exception:
            scm = None

        # Skills
        skill_names = []
        try:
            import skill_combo_config as scc
            if hasattr(scc, 'SKILL_COOLDOWNS'):
                skill_names = list(scc.SKILL_COOLDOWNS.keys())
        except Exception:
            skill_names = []

        self._skills_table.setRowCount(len(skill_names))
        for r, name in enumerate(skill_names):
            try:
                item_name = QtWidgets.QTableWidgetItem(name)
                if scm:
                    rem = scm.get_skill_cooldown_remaining(name)
                    txt = f"{rem:.1f}" if rem > 0 else "Ready"
                else:
                    txt = "Ready"
                self._skills_table.setItem(r, 0, item_name)
                self._skills_table.setItem(r, 1, QtWidgets.QTableWidgetItem(txt))
            except Exception:
                pass

        # Combos
        combo_names = []
        try:
            import skill_combo_config as scc
            if hasattr(scc, 'COMBO_SETS'):
                combo_names = list(scc.COMBO_SETS.keys())
        except Exception:
            combo_names = []

        self._combos_table.setRowCount(len(combo_names))
        for r, cname in enumerate(combo_names):
            try:
                item_name = QtWidgets.QTableWidgetItem(cname)
                status = "Unknown"
                if scm:
                    rem = scm.get_combo_cooldown_remaining(cname)
                    # try to get skills for the combo to determine readiness
                    skills = []
                    if hasattr(scm, 'get_combo_skills'):
                        try:
                            skills = scm.get_combo_skills(cname)
                        except Exception:
                            skills = []
                    all_ready = True
                    if hasattr(scm, 'are_all_skills_ready') and skills:
                        all_ready = scm.are_all_skills_ready(skills)
                    if rem > 0:
                        status = self.tr('status_cooldown').format(seconds=f"{rem:.1f}")
                    else:
                        status = self.tr('status_ready') if all_ready else self.tr('status_waiting')
                else:
                    status = self.tr('status_ready')
                self._combos_table.setItem(r, 0, item_name)
                self._combos_table.setItem(r, 1, QtWidgets.QTableWidgetItem(status))
            except Exception:
                pass

    def _on_backend_changed(self, backend: str):
        """User changed the input backend from the UI dropdown."""
        try:
            # Validate availability and persist via JSON-backed config
            try:
                import skill_combo_config as scc
                # Validate backend and show a dialog if unavailable
                try:
                    ic.validate_backend(backend)
                    scc.update_config({'INPUT_BACKEND': backend})
                    ic.INPUT_BACKEND = backend
                    self.log(self.tr('log_backend_set').format(backend=backend))
                except RuntimeError as ve:
                    # Persist selection so UI reflects user's choice, but inform the user
                    try:
                        scc.update_config({'INPUT_BACKEND': backend})
                    except Exception:
                        pass
                    ic.INPUT_BACKEND = backend
                    QtWidgets.QMessageBox.warning(
                        self,
                        self.tr('msg_backend_unavailable_title'),
                        self.tr('msg_backend_unavailable_body', backend=backend, error=ve)
                    )
                    self.log(self.tr('log_backend_unavailable').format(backend=backend, error=ve))
            except Exception:
                # Fallback: set module var and try to persist to JSON config
                try:
                    ic.INPUT_BACKEND = backend
                    import skill_combo_config as scc2
                    scc2.update_config({'INPUT_BACKEND': backend})
                    self.log(self.tr('log_backend_set').format(backend=backend))
                except Exception as e:
                    self.log(self.tr('msg_failed_backend_json').format(error=e))
            # update status indicator after attempting to set backend
            try:
                self._update_backend_status(backend)
            except Exception:
                pass
        except Exception as e:
            self.log(self.tr('log_backend_set_fail').format(error=e))

    def _on_dry_run_toggled(self, enabled: bool):
        """User toggled DRY_RUN simulate mode in the UI."""
        try:
            ic.INPUT_DRY_RUN = bool(enabled)
            try:
                import skill_combo_config as scc
                scc.update_config({'INPUT_DRY_RUN': bool(enabled)})
            except Exception:
                try:
                    import skill_combo_config as scc2
                    scc2.update_config({'INPUT_DRY_RUN': bool(enabled)})
                except Exception as e:
                    self.log(self.tr('msg_failed_dry_run_json').format(error=e))
            state_text = self.tr('state_on') if enabled else self.tr('state_off')
            self.log(self.tr('log_simulate_mode').format(state=state_text))
        except Exception as e:
            self.log(self.tr('log_simulate_toggle_fail').format(error=e))
    
    def _update_backend_status(self, backend: str):
        """Update the small status label next to the backend selector."""
        try:
            ic.validate_backend(backend)
            self.backend_status.setText(self.tr('status_available'))
            self.backend_status.setStyleSheet('color: green; font-weight: bold;')
            self.backend_status.setToolTip(self.tr('status_tooltip_available', backend=backend))
        except RuntimeError as e:
            self.backend_status.setText(self.tr('status_unavailable'))
            self.backend_status.setStyleSheet('color: red; font-weight: bold;')
            self.backend_status.setToolTip(self.tr('status_tooltip_unavailable', error=str(e)))
        except Exception:
            self.backend_status.setText(self.tr('status_unknown'))
            self.backend_status.setStyleSheet('color: orange;')
            self.backend_status.setToolTip(self.tr('status_tooltip_unknown'))
    
    def _open_skill_config(self):
        """Open skill configuration file in default editor."""
        try:
            import os
            import subprocess
            # Prefer JSON config for editing; fallback to python file if JSON missing
            json_path = os.path.join(os.path.dirname(__file__), 'skill_combo_config.json')
            py_path = os.path.join(os.path.dirname(__file__), 'skill_combo_config.py')
            target = json_path if os.path.exists(json_path) else py_path

            if os.path.exists(target):
                if sys.platform == 'win32':
                    os.startfile(target)
                else:
                    subprocess.call(['open' if sys.platform == 'darwin' else 'xdg-open', target])
                self.log(self.tr('log_opened_config').format(path=target))
            else:
                self.log(self.tr('log_config_not_found').format(path=target))
        except Exception as e:
            self.log(self.tr('log_open_config_fail').format(error=e))

    def _refresh_windows(self):
        import re
        previous_hwnd = self.win_combo.currentData()
        self.win_combo.clear()
        wins = list_windows()
        for title, hwnd in wins:
            self.win_combo.addItem(f"{title} (hwnd={hwnd})", hwnd)
        # Preserve a user's selection on Refresh; prefer AION2 on initial load.
        previous_index = self.win_combo.findData(previous_hwnd) if previous_hwnd is not None else -1
        if previous_index >= 0:
            self.win_combo.setCurrentIndex(previous_index)
            return
        exact = [i for i, (title, _) in enumerate(wins)
                 if ''.join(title.casefold().split()) == 'aion2']
        matches = exact or [i for i, (title, _) in enumerate(wins)
                           if re.search(r'\baion\s*2\b', title, re.IGNORECASE)]
        if matches:
            self.win_combo.setCurrentIndex(matches[0])
            self.log(f'Automatically selected AION2: {wins[matches[0]][0]}')

    def start(self):
        idx = self.win_combo.currentIndex()
        if idx < 0:
            self.log(self.tr('log_no_window_selected'))
            return
        hwnd = self.win_combo.currentData()
        try:
            ic.set_active_hwnd(hwnd)
        except Exception:
            pass
        rect = get_window_rect(hwnd)
        if not rect:
            self.log(self.tr('log_unable_get_window_rect'))
            return
        left, top, w, h = rect
        # show overlay aligned to window
        self._overlay.setGeometry(left, top, w, h)
        self._overlay.show()
        self._overlay.make_clickthrough()

        # create controller (local model) - use default FPS (None uses default inside detection controller)
        self._controller = DetectionController(hwnd=hwnd, overlay_update=self._overlay.update_overlay,
            log_fn=self.log, fps=None, on_failsafe=self.stop_shortcut_pressed.emit)
        # apply stored automation preference
        try:
            self._controller.action_planner.set_enabled(self._automation_enabled)
        except Exception:
            pass
        self._controller.start()
        # Focus the game window immediately when starting
        try:
            ic.focus_window(hwnd)
        except Exception:
            pass
        # start periodic overlay repositioning to follow the target window
        self._pos_timer.start()
        # start cooldown monitor refresh
        try:
            self._cooldown_timer.start()
        except Exception:
            pass
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.log(self.tr('log_started_detection'))

    def stop(self):
        if self._controller:
            self._controller.stop()
            self._controller = None
        self._overlay.hide()
        self._pos_timer.stop()
        try:
            self._cooldown_timer.stop()
        except Exception:
            pass
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.log(self.tr('log_stopped'))

    def emergency_stop(self):
        # Immediately disable automation and stop controller
        self._automation_enabled = False
        try:
            self._overlay.set_automation_enabled(False)
        except Exception:
            pass
        if self._controller:
            try:
                self._controller.action_planner.set_enabled(False)
            except Exception:
                pass
        self.log(self.tr('log_emergency_stop'))

    def _reposition_overlay(self):
        # Keep overlay aligned to the target window while running
        idx = self.win_combo.currentIndex()
        if idx < 0:
            return
        hwnd = self.win_combo.currentData()
        rect = get_window_rect(hwnd)
        if rect:
            left, top, w, h = rect
            self._overlay.setGeometry(left, top, w, h)

    @QtCore.Slot()
    def toggle_automation(self):
        # toggle desired automation state and apply to controller if present
        self._automation_enabled = not self._automation_enabled
        enabled = self._automation_enabled
        # update overlay indicator
        try:
            self._overlay.set_automation_enabled(enabled)
        except Exception:
            pass
        # apply to running controller
        if self._controller:
            try:
                self._controller.action_planner.set_enabled(enabled)
            except Exception:
                pass

    def _start_stop_hotkey_listener(self):
        """Register Alt+Shift+C globally; stop workers before queuing UI cleanup."""
        import ctypes
        import threading
        from ctypes import wintypes

        def listen():
            user32 = ctypes.windll.user32
            hotkey_id = 2
            # MOD_ALT | MOD_SHIFT | MOD_NOREPEAT
            if not user32.RegisterHotKey(None, hotkey_id, 0x0001 | 0x0004 | 0x4000, ord('C')):
                self.log('Unable to register Alt+Shift+C stop shortcut (it may be in use).')
                return
            self.log('Stop shortcut registered: Alt+Shift+C')
            msg = wintypes.MSG()
            try:
                while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                    if msg.message == 0x0312 and msg.wParam == hotkey_id:
                        controller = self._controller
                        if controller is not None:
                            controller._cancel_execution.set()
                            controller._running.clear()
                        self.stop_shortcut_pressed.emit()
            finally:
                user32.UnregisterHotKey(None, hotkey_id)

        self._stop_hotkey_thread = threading.Thread(target=listen, daemon=True)
        self._stop_hotkey_thread.start()

    def _start_hotkey_listener(self):
        # Start background thread that registers a global Delete hotkey and
        # invokes toggle_automation when pressed.
        import threading, ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        WM_HOTKEY = 0x0312
        VK_DELETE = 0x2E

        def _hotkey_thread_fn():
            HOTKEY_ID = 1
            # Try RegisterHotKey first (simple, preferred)
            if user32.RegisterHotKey(None, HOTKEY_ID, 0, VK_DELETE):
                # registration succeeded
                try:
                    self.log(self.tr('log_hotkey_registered'))
                except Exception:
                    pass
                msg = wintypes.MSG()
                try:
                    while True:
                        b = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                        if b == 0:
                            break
                        if msg.message == WM_HOTKEY:
                            try:
                                QtCore.QMetaObject.invokeMethod(self, "toggle_automation", QtCore.Qt.QueuedConnection)
                            except Exception:
                                pass
                        user32.TranslateMessage(ctypes.byref(msg))
                        user32.DispatchMessageW(ctypes.byref(msg))
                finally:
                    try:
                        user32.UnregisterHotKey(None, HOTKEY_ID)
                    except Exception:
                        pass
                return

            # If RegisterHotKey failed, fall back to a low-level keyboard hook
            try:
                self.log(self.tr('log_register_hotkey_failed'))
            except Exception:
                pass

            # WH_KEYBOARD_LL hook to catch Delete presses
            WH_KEYBOARD_LL = 13
            WM_KEYDOWN = 0x0100

            kernel32 = ctypes.windll.kernel32

            # define KBDLLHOOKSTRUCT
            class KBDLLHOOKSTRUCT(ctypes.Structure):
                _fields_ = [("vkCode", wintypes.DWORD),
                            ("scanCode", wintypes.DWORD),
                            ("flags", wintypes.DWORD),
                            ("time", wintypes.DWORD),
                            ("dwExtraInfo", ctypes.c_size_t)]

            # LRESULT is a signed pointer-sized integer; some Python versions
            # do not define it in ctypes.wintypes.
            LowLevelKeyboardProc = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.INT, wintypes.WPARAM, wintypes.LPARAM)
            # Explicit signatures prevent 64-bit hook/module handles from truncating.
            kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
            kernel32.GetModuleHandleW.restype = wintypes.HMODULE
            user32.SetWindowsHookExW.argtypes = [wintypes.INT, LowLevelKeyboardProc, wintypes.HINSTANCE, wintypes.DWORD]
            user32.SetWindowsHookExW.restype = wintypes.HANDLE
            user32.CallNextHookEx.argtypes = [wintypes.HANDLE, wintypes.INT, wintypes.WPARAM, wintypes.LPARAM]
            user32.CallNextHookEx.restype = ctypes.c_ssize_t
            user32.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
            user32.UnhookWindowsHookEx.restype = wintypes.BOOL

            @LowLevelKeyboardProc
            def _ll_keyboard_proc(nCode, wParam, lParam):
                try:
                    if nCode >= 0 and wParam == WM_KEYDOWN:
                        kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                        if kb.vkCode == VK_DELETE:
                            try:
                                QtCore.QMetaObject.invokeMethod(self, "toggle_automation", QtCore.Qt.QueuedConnection)
                            except Exception:
                                pass
                except Exception:
                    pass
                return user32.CallNextHookEx(None, nCode, wParam, lParam)

            # install hook
            hook_id = user32.SetWindowsHookExW(WH_KEYBOARD_LL, _ll_keyboard_proc, kernel32.GetModuleHandleW(None), 0)
            if not hook_id:
                try:
                    self.log(self.tr('log_failed_hotkey_hook'))
                except Exception:
                    pass
                return

            # message loop to keep the hook alive
            msg = wintypes.MSG()
            try:
                while True:
                    b = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                    if b == 0:
                        break
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
            finally:
                try:
                    user32.UnhookWindowsHookEx(hook_id)
                except Exception:
                    pass

        t = threading.Thread(target=_hotkey_thread_fn, daemon=True)
        t.start()
        self._hotkey_thread = t

    def _open_skill_editor(self):
        """Navigate to the embedded skill editor screen."""
        try:
            self.change_page(1)
        except Exception:
            pass
    
    def _open_combo_editor(self):
        """Navigate to the embedded combo editor screen."""
        try:
            self.change_page(2)
        except Exception:
            pass

    # Anti-detection dialog removed (stealth_config no longer supported)

    def closeEvent(self, event):
        # ensure controller stopped and leave
        try:
            if self._controller:
                self._controller.stop()
        except Exception:
            pass
        return super().closeEvent(event)


class KeybindCaptureDialog(QtWidgets.QDialog):
    """Dialog for capturing a keybind press."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._language = self._resolve_language()
        self.setWindowTitle(self._t('capture_title'))
        self.setModal(True)
        self.setFixedSize(400, 200)
        
        self.captured_key = None
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # Instructions
        self.instruction_label = QtWidgets.QLabel(self._t('capture_instruction'))
        self.instruction_label.setAlignment(QtCore.Qt.AlignCenter)
        self.instruction_label.setStyleSheet("font-size: 14pt; padding: 20px;")
        layout.addWidget(self.instruction_label)
        
        # Display captured key
        self.key_display = QtWidgets.QLabel(self._t('capture_waiting'))
        self.key_display.setAlignment(QtCore.Qt.AlignCenter)
        self.key_display.setStyleSheet("font-size: 18pt; font-weight: bold; color: #4CAF50; padding: 10px;")
        layout.addWidget(self.key_display)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        self.confirm_btn = QtWidgets.QPushButton(self._t('capture_confirm'))
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.clicked.connect(self.accept)
        self.confirm_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px; }")
        
        self.cancel_btn = QtWidgets.QPushButton(self._t('capture_cancel'))
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; font-weight: bold; padding: 8px; }")
        
        button_layout.addWidget(self.confirm_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)
    
    def keyPressEvent(self, event):
        """Capture key press."""
        key = event.key()
        modifiers = event.modifiers()
        
        # Map numeric and punctuation keys
        key_map = {
            QtCore.Qt.Key_1: '1', QtCore.Qt.Key_2: '2', QtCore.Qt.Key_3: '3',
            QtCore.Qt.Key_4: '4', QtCore.Qt.Key_5: '5', QtCore.Qt.Key_6: '6',
            QtCore.Qt.Key_7: '7', QtCore.Qt.Key_8: '8', QtCore.Qt.Key_9: '9',
            QtCore.Qt.Key_0: '0', QtCore.Qt.Key_Minus: '-', QtCore.Qt.Key_Equal: '=',
        }

        # Accept F1-F9 and numeric keys only; explicitly ignore modifier keys
        if key in key_map and not (modifiers & (QtCore.Qt.AltModifier | QtCore.Qt.ControlModifier)):
            self.captured_key = key_map[key]
            self.key_display.setText(self.captured_key)
            self.key_display.setStyleSheet("font-size: 18pt; font-weight: bold; color: #4CAF50; padding: 10px;")
            self.confirm_btn.setEnabled(True)
            return

        # Function keys F1..F9
        f_keys = {QtCore.Qt.Key_F1: 'f1', QtCore.Qt.Key_F2: 'f2', QtCore.Qt.Key_F3: 'f3',
                  QtCore.Qt.Key_F4: 'f4', QtCore.Qt.Key_F5: 'f5', QtCore.Qt.Key_F6: 'f6',
                  QtCore.Qt.Key_F7: 'f7', QtCore.Qt.Key_F8: 'f8', QtCore.Qt.Key_F9: 'f9'}
        if key in f_keys and not (modifiers & (QtCore.Qt.AltModifier | QtCore.Qt.ControlModifier)):
            self.captured_key = f_keys[key]
            self.key_display.setText(self.captured_key.upper())
            self.key_display.setStyleSheet("font-size: 18pt; font-weight: bold; color: #4CAF50; padding: 10px;")
            self.confirm_btn.setEnabled(True)
            return

        # Otherwise invalid for skill binds
        self.key_display.setText(self._t('capture_invalid'))
        self.key_display.setStyleSheet("font-size: 18pt; font-weight: bold; color: #f44336; padding: 10px;")

    def _resolve_language(self) -> str:
        parent = self.parent()
        while parent is not None and not hasattr(parent, 'current_language'):
            parent = parent.parent()
        return getattr(parent, 'current_language', 'en')

    def _t(self, key: str, **kwargs) -> str:
        return translate_text(self._language, key, **kwargs)


class SkillEditorScreen(QtWidgets.QWidget):
    """Embedded screen for editing individual skill cooldowns."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('skill_editor_screen')
        self.setMinimumSize(720, 520)
        self._language = self._resolve_language()
        self._pool_guard = False

        import skill_combo_config
        self.config = skill_combo_config

        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(16)

        header_layout = QtWidgets.QVBoxLayout()
        header_layout.setSpacing(4)
        self.title_label = QtWidgets.QLabel()
        self.title_label.setStyleSheet('font-size:20pt; font-weight:600;')
        header_layout.addWidget(self.title_label)

        self.subtitle_label = QtWidgets.QLabel()
        self.subtitle_label.setStyleSheet('color:#bdbdbd;')
        self.subtitle_label.setWordWrap(True)
        header_layout.addWidget(self.subtitle_label)
        root_layout.addLayout(header_layout)

        stats_layout = QtWidgets.QHBoxLayout()
        stats_layout.setSpacing(12)
        card, value, caption = self._create_stat_card()
        self.total_skills_card = card
        self.total_skills_value = value
        self.total_skills_caption = caption
        stats_layout.addWidget(card)
        card, value, caption = self._create_stat_card()
        self.pool_card = card
        self.pool_value = value
        self.pool_caption = caption
        stats_layout.addWidget(card)
        card, value, caption = self._create_stat_card()
        self.gcd_card = card
        self.gcd_value = value
        self.gcd_caption = caption
        stats_layout.addWidget(card)
        stats_layout.addStretch()
        root_layout.addLayout(stats_layout)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        root_layout.addWidget(splitter, 1)

        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        left_layout.setSpacing(10)

        search_row = QtWidgets.QHBoxLayout()
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._filter_skills)
        search_row.addWidget(self.search_edit)
        self.reset_filter_btn = QtWidgets.QPushButton()
        self.reset_filter_btn.setFixedWidth(90)
        self.reset_filter_btn.clicked.connect(self._reset_filter)
        search_row.addWidget(self.reset_filter_btn)
        left_layout.addLayout(search_row)

        self.cooldown_group = QtWidgets.QGroupBox()
        cooldown_group_layout = QtWidgets.QVBoxLayout()
        cooldown_group_layout.setSpacing(8)
        self.cooldown_group.setLayout(cooldown_group_layout)

        self.skill_table = QtWidgets.QTableWidget()
        self.skill_table.setColumnCount(2)
        self.skill_table.setHorizontalHeaderLabels(['Skill', 'Cooldown'])
        header = self.skill_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.skill_table.verticalHeader().setVisible(False)
        self.skill_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.skill_table.setAlternatingRowColors(True)
        self.skill_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        cooldown_group_layout.addWidget(self.skill_table)

        table_btn_row = QtWidgets.QHBoxLayout()
        table_btn_row.setSpacing(6)
        self.add_skill_btn = QtWidgets.QPushButton()
        self.add_skill_btn.setFixedWidth(110)
        self.add_skill_btn.clicked.connect(self._add_skill)
        table_btn_row.addWidget(self.add_skill_btn)
        self.remove_skill_btn = QtWidgets.QPushButton()
        self.remove_skill_btn.setFixedWidth(110)
        self.remove_skill_btn.clicked.connect(self._remove_skill)
        table_btn_row.addWidget(self.remove_skill_btn)
        table_btn_row.addStretch()
        cooldown_group_layout.addLayout(table_btn_row)

        left_layout.addWidget(self.cooldown_group, 1)
        splitter.addWidget(left_widget)

        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_widget)
        right_layout.setSpacing(12)

        self.pool_group = QtWidgets.QGroupBox()
        pool_layout = QtWidgets.QVBoxLayout()
        pool_layout.setSpacing(6)

        self.skill_pool_edit = QtWidgets.QLineEdit()
        self.skill_pool_edit.setClearButtonEnabled(True)
        self.skill_pool_edit.editingFinished.connect(self._sync_pool_list_from_text)
        pool_layout.addWidget(self.skill_pool_edit)

        self.pool_list = QtWidgets.QListWidget()
        self.pool_list.setAlternatingRowColors(True)
        self.pool_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.pool_list.setEditTriggers(QtWidgets.QAbstractItemView.DoubleClicked | QtWidgets.QAbstractItemView.EditKeyPressed)
        self.pool_list.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.pool_list.setDefaultDropAction(QtCore.Qt.MoveAction)
        self.pool_list.setMinimumHeight(160)
        self.pool_list.itemChanged.connect(self._on_pool_item_changed)
        self.pool_list.itemSelectionChanged.connect(self._on_pool_selection_changed)
        pool_layout.addWidget(self.pool_list)

        pool_btn_row = QtWidgets.QHBoxLayout()
        pool_btn_row.setSpacing(6)
        self.add_pool_skill_btn = QtWidgets.QPushButton()
        self.add_pool_skill_btn.clicked.connect(self._add_skill_to_pool)
        pool_btn_row.addWidget(self.add_pool_skill_btn)
        self.remove_pool_skill_btn = QtWidgets.QPushButton()
        self.remove_pool_skill_btn.clicked.connect(self._remove_pool_skill)
        self.remove_pool_skill_btn.setEnabled(False)
        pool_btn_row.addWidget(self.remove_pool_skill_btn)
        pool_btn_row.addStretch()
        pool_layout.addLayout(pool_btn_row)

        self.hint_label = QtWidgets.QLabel()
        self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet('color:#bdbdbd;')
        pool_layout.addWidget(self.hint_label)

        self.pool_group.setLayout(pool_layout)
        right_layout.addWidget(self.pool_group)

        model = self.pool_list.model()
        if model is not None:
            model.rowsInserted.connect(self._on_pool_rows_changed)
            model.rowsRemoved.connect(self._on_pool_rows_changed)
            model.rowsMoved.connect(self._on_pool_rows_changed)

        self.timing_group = QtWidgets.QGroupBox()
        timing_layout = QtWidgets.QHBoxLayout()
        timing_layout.setSpacing(6)
        self.gcd_label = QtWidgets.QLabel()
        timing_layout.addWidget(self.gcd_label)
        self.gcd_spin = QtWidgets.QDoubleSpinBox()
        self.gcd_spin.setRange(0.1, 600.0)
        self.gcd_spin.setSingleStep(0.1)
        self.gcd_spin.valueChanged.connect(lambda _: self._update_stats())
        timing_layout.addWidget(self.gcd_spin)
        timing_layout.addStretch()
        self.timing_group.setLayout(timing_layout)
        right_layout.addWidget(self.timing_group)

        right_layout.addStretch()

        actions_row = QtWidgets.QHBoxLayout()
        actions_row.setSpacing(10)
        self.save_btn = QtWidgets.QPushButton()
        self.save_btn.setStyleSheet('background-color:#4CAF50; color:white; font-weight:bold;')
        self.save_btn.clicked.connect(self._save_and_accept)
        actions_row.addWidget(self.save_btn)
        self.cancel_btn = QtWidgets.QPushButton()
        self.cancel_btn.setStyleSheet('background-color:#f44336; color:white; font-weight:bold;')
        self.cancel_btn.clicked.connect(self._on_cancel)
        actions_row.addWidget(self.cancel_btn)
        right_layout.addLayout(actions_row)

        splitter.addWidget(right_widget)
        splitter.setSizes([540, 280])

        self._sync_pool_list_from_config()
        self._load_skills()
        self.gcd_spin.blockSignals(True)
        self.gcd_spin.setValue(self.config.SINGLE_SKILL_GLOBAL_COOLDOWN)
        self.gcd_spin.blockSignals(False)

        self._apply_theme()
        self.apply_translations(self._language)
        self._update_stats()

    def _create_stat_card(self):
        frame = QtWidgets.QFrame()
        frame.setObjectName('skillStatCard')
        frame.setStyleSheet(
            'QFrame#skillStatCard { background-color: #211331; border: 1px solid #3b1c5d; border-radius: 10px; }'
        )
        layout = QtWidgets.QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        value = QtWidgets.QLabel('0')
        value.setStyleSheet('font-size:18pt; font-weight:600; color:#E6E1FF;')
        layout.addWidget(value)
        caption = QtWidgets.QLabel()
        caption.setStyleSheet('color:#B39DDB;')
        caption.setWordWrap(True)
        layout.addWidget(caption)
        return frame, value, caption

    def _apply_theme(self):
        primary = '#5E35B1'
        accent = '#7C4DFF'
        neutral = '#1B102A'
        neutral_alt = '#241233'
        border = '#3A1F5A'

        table_style = (
            f"QTableWidget {{\n"
            f"    background-color: {neutral};\n"
            f"    alternate-background-color: {neutral_alt};\n"
            "    color: #E6E1FF;\n"
            "    gridline-color: #33204F;\n"
            "    border: 1px solid #33204F;\n"
            "    border-radius: 8px;\n"
            "}\n"
            "QTableWidget::item {\n"
            "    background-color: transparent;\n"
            "}\n"
            "QTableWidget::item:selected {\n"
            "    background-color: #4527A0;\n"
            "    color: #FFFFFF;\n"
            "}\n"
            "QHeaderView::section {\n"
            "    background-color: #2A1840;\n"
            "    color: #D1C4E9;\n"
            "    border: 0;\n"
            "    padding: 6px;\n"
            "}\n"
        )
        self.skill_table.setStyleSheet(table_style)

        list_style = (
            f"QListWidget {{\n"
            f"    background-color: {neutral};\n"
            "    color: #E6E1FF;\n"
            f"    border: 1px solid {border};\n"
            "    border-radius: 8px;\n"
            "}\n"
            "QListWidget::item {\n"
            "    background-color: #241233;\n"
            "}\n"
            "QListWidget::item:alternate {\n"
            "    background-color: #1B102A;\n"
            "}\n"
            "QListWidget::item:selected {\n"
            "    background-color: #4527A0;\n"
            "    color: #FFFFFF;\n"
            "}\n"
        )
        self.pool_list.setStyleSheet(list_style)

        line_edit_style = (
            f"QLineEdit {{\n"
            "    background-color: #190E27;\n"
            "    color: #E6E1FF;\n"
            f"    border: 1px solid {border};\n"
            "    border-radius: 6px;\n"
            "    padding: 6px;\n"
            "    selection-background-color: #4527A0;\n"
            "    selection-color: #FFFFFF;\n"
            "}}\n"
        )
        for edit in (self.search_edit, self.skill_pool_edit):
            edit.setStyleSheet(line_edit_style)

        button_base = (
            "QPushButton {\n"
            "    background-color:%(bg)s;\n"
            "    color:%(fg)s;\n"
            "    border:none;\n"
            "    border-radius:8px;\n"
            "    padding:6px 16px;\n"
            "    font-weight:600;\n"
            "}\n"
            "QPushButton:hover {\n"
            "    background-color:%(hover)s;\n"
            "}\n"
            "QPushButton:disabled {\n"
            "    background-color:#2D1C45;\n"
            "    color:#74618F;\n"
            "}\n"
        )
        themed_buttons = [
            (self.reset_filter_btn, {'bg': '#4527A0', 'fg': '#FFFFFF', 'hover': '#5E35B1'}),
            (self.add_skill_btn, {'bg': primary, 'fg': '#FFFFFF', 'hover': accent}),
            (self.remove_skill_btn, {'bg': '#8E24AA', 'fg': '#FFFFFF', 'hover': '#9C27B0'}),
            (self.add_pool_skill_btn, {'bg': primary, 'fg': '#FFFFFF', 'hover': accent}),
            (self.remove_pool_skill_btn, {'bg': '#8E24AA', 'fg': '#FFFFFF', 'hover': '#9C27B0'}),
        ]
        for btn, colors in themed_buttons:
            btn.setStyleSheet(button_base % colors)

        self.save_btn.setStyleSheet(
            "QPushButton {\n"
            "    background-color:#2E7D32;\n"
            "    color:#FFFFFF;\n"
            "    border:none;\n"
            "    border-radius:8px;\n"
            "    padding:8px 20px;\n"
            "    font-weight:700;\n"
            "}\n"
            "QPushButton:hover {\n"
            "    background-color:#388E3C;\n"
            "}\n"
        )
        self.cancel_btn.setStyleSheet(
            "QPushButton {\n"
            "    background-color:#C62828;\n"
            "    color:#FFFFFF;\n"
            "    border:none;\n"
            "    border-radius:8px;\n"
            "    padding:8px 20px;\n"
            "    font-weight:700;\n"
            "}\n"
            "QPushButton:hover {\n"
            "    background-color:#D32F2F;\n"
            "}\n"
        )

        group_style = (
            f"QGroupBox {{\n"
            f"    border:1px solid {border};\n"
            "    border-radius:10px;\n"
            "    margin-top:12px;\n"
            "    padding:12px;\n"
            "    color:#D1C4E9;\n"
            "}}\n"
            "QGroupBox::title {\n"
            "    subcontrol-origin: margin;\n"
            "    left:14px;\n"
            "    padding:0 6px;\n"
            "}\n"
        )
        for group in (self.cooldown_group, self.pool_group, self.timing_group):
            group.setStyleSheet(group_style)

        self.subtitle_label.setStyleSheet('color:#B39DDB;')

    def _filter_skills(self, text: str):
        term = (text or '').strip().lower()
        for row in range(self.skill_table.rowCount()):
            item = self.skill_table.item(row, 0)
            key_text = (item.text() if item else '').lower()
            hidden = bool(term) and term not in key_text
            self.skill_table.setRowHidden(row, hidden)

    def _reset_filter(self):
        self.search_edit.clear()

    def _load_skills(self):
        self.skill_table.setRowCount(0)
        for keybind, cooldown in self.config.SKILL_COOLDOWNS.items():
            row = self.skill_table.rowCount()
            self.skill_table.insertRow(row)
            key_item = QtWidgets.QTableWidgetItem(keybind)
            key_item.setFlags(key_item.flags() & ~QtCore.Qt.ItemIsEditable)
            self.skill_table.setItem(row, 0, key_item)

            cooldown_spin = QtWidgets.QDoubleSpinBox()
            cooldown_spin.setRange(0.1, 600.0)
            cooldown_spin.setSingleStep(0.5)
            cooldown_spin.setValue(cooldown)
            cooldown_spin.setSuffix(self._t('suffix_seconds'))
            self.skill_table.setCellWidget(row, 1, cooldown_spin)

    def apply_translations(self, language: str):
        self._language = language or 'en'
        self.title_label.setText(self._t('skill_editor_title'))
        self.subtitle_label.setText(self._t('skill_editor_subtitle'))
        self.search_edit.setPlaceholderText(self._t('skill_editor_search_placeholder'))
        self.reset_filter_btn.setText(self._t('button_reset_filter'))
        self.cooldown_group.setTitle(self._t('group_skill_cooldowns'))
        self.skill_table.setHorizontalHeaderLabels([
            self._t('table_header_keybind'),
            self._t('table_header_cooldown')
        ])
        self.add_skill_btn.setText(self._t('button_add_skill'))
        self.remove_skill_btn.setText(self._t('button_remove_skill'))
        self.pool_group.setTitle(self._t('group_single_skill_pool'))
        self.pool_group.setToolTip(self._t('tooltip_skill_pool'))
        self.pool_list.setToolTip(self._t('tooltip_skill_pool'))
        self.skill_pool_edit.setPlaceholderText(self._t('placeholder_skill_pool'))
        self.add_pool_skill_btn.setText(self._t('button_add_pool_skill'))
        self.add_pool_skill_btn.setToolTip(self._t('tooltip_add_pool_skill'))
        self.remove_pool_skill_btn.setText(self._t('button_remove_pool_skill'))
        self.hint_label.setText(self._t('trailing_hint_skill_pool'))
        self.timing_group.setTitle(self._t('group_skill_timing'))
        self.gcd_label.setText(self._t('label_single_skill_gcd'))
        self.save_btn.setText(self._t('button_save_changes'))
        self.cancel_btn.setText(self._t('button_cancel'))
        self.total_skills_caption.setText(self._t('skill_summary_total'))
        self.pool_caption.setText(self._t('skill_summary_pool'))
        self.gcd_caption.setText(self._t('skill_summary_gcd'))
        suffix = self._t('suffix_seconds')
        self.gcd_spin.setSuffix(suffix)
        self._refresh_spinbox_suffixes()
        self._update_stats()

    def _refresh_spinbox_suffixes(self):
        suffix = self._t('suffix_seconds')
        for row in range(self.skill_table.rowCount()):
            spin = self.skill_table.cellWidget(row, 1)
            if isinstance(spin, QtWidgets.QDoubleSpinBox):
                spin.setSuffix(suffix)

    def _resolve_language(self) -> str:
        parent = self.parent()
        while parent is not None and not hasattr(parent, 'current_language'):
            parent = parent.parent()
        return getattr(parent, 'current_language', 'en')

    def _t(self, key: str, **kwargs) -> str:
        return translate_text(getattr(self, '_language', 'en'), key, **kwargs)

    def _add_skill(self):
        capture_dialog = KeybindCaptureDialog(self)
        if capture_dialog.exec() and capture_dialog.captured_key:
            keybind = capture_dialog.captured_key
            for row in range(self.skill_table.rowCount()):
                existing_item = self.skill_table.item(row, 0)
                if existing_item and existing_item.text() == keybind:
                    QtWidgets.QMessageBox.warning(
                        self,
                        self._t('msg_duplicate_keybind_title'),
                        self._t('msg_duplicate_keybind_body', keybind=keybind)
                    )
                    return

            row = self.skill_table.rowCount()
            self.skill_table.insertRow(row)
            key_item = QtWidgets.QTableWidgetItem(keybind)
            key_item.setFlags(key_item.flags() & ~QtCore.Qt.ItemIsEditable)
            self.skill_table.setItem(row, 0, key_item)

            cooldown_spin = QtWidgets.QDoubleSpinBox()
            cooldown_spin.setRange(0.1, 600.0)
            cooldown_spin.setSingleStep(0.5)
            cooldown_spin.setValue(60.0)
            cooldown_spin.setSuffix(self._t('suffix_seconds'))
            self.skill_table.setCellWidget(row, 1, cooldown_spin)
            self.skill_table.setCurrentCell(row, 0)
            self._update_stats()

    def _remove_skill(self):
        current_row = self.skill_table.currentRow()
        if current_row >= 0:
            self.skill_table.removeRow(current_row)
            self._update_stats()

    def _pool_key_exists(self, keybind: str) -> bool:
        key_lower = keybind.strip().lower()
        for value in self._current_pool_values():
            if value.strip().lower() == key_lower:
                return True
        return False

    def _add_skill_to_pool(self):
        capture_dialog = KeybindCaptureDialog(self)
        if capture_dialog.exec() and capture_dialog.captured_key:
            keybind = capture_dialog.captured_key
            if self._pool_key_exists(keybind):
                QtWidgets.QMessageBox.warning(
                    self,
                    self._t('msg_duplicate_skill_title'),
                    self._t('msg_duplicate_skill_body', skill=keybind)
                )
                return

            self._pool_guard = True
            item = QtWidgets.QListWidgetItem(keybind)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsDragEnabled)
            item.setData(QtCore.Qt.UserRole, keybind)
            self.pool_list.addItem(item)
            self.pool_list.setCurrentItem(item)
            self._pool_guard = False
            self._sync_pool_text_from_list(force=True)
            self._update_stats()

    def _remove_pool_skill(self):
        item = self.pool_list.currentItem()
        if item is None:
            return
        row = self.pool_list.row(item)
        self._pool_guard = True
        self.pool_list.takeItem(row)
        self._pool_guard = False
        self._sync_pool_text_from_list(force=True)
        self._on_pool_selection_changed()
        self._update_stats()

    def _current_pool_values(self):
        values = []
        seen = set()
        for idx in range(self.pool_list.count()):
            text = self.pool_list.item(idx).text().strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            values.append(text)
        return values

    def _sync_pool_text_from_list(self, *, force: bool = False):
        if self._pool_guard and not force:
            return
        joined = ', '.join(self._current_pool_values())
        self._pool_guard = True
        self.skill_pool_edit.setText(joined)
        self._pool_guard = False

    def _sync_pool_list_from_text(self):
        if self._pool_guard:
            return
        raw_tokens = [s.strip() for s in (self.skill_pool_edit.text() or '').split(',')]
        tokens = []
        seen = set()
        for token in raw_tokens:
            if not token:
                continue
            key = token.lower()
            if key in seen:
                continue
            seen.add(key)
            tokens.append(token)

        self._pool_guard = True
        self.pool_list.clear()
        for token in tokens:
            item = QtWidgets.QListWidgetItem(token)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsDragEnabled)
            item.setData(QtCore.Qt.UserRole, token)
            self.pool_list.addItem(item)
        self.pool_list.clearSelection()
        self.remove_pool_skill_btn.setEnabled(False)
        self._pool_guard = False
        self._sync_pool_text_from_list(force=True)
        self._update_stats()

    def _on_pool_rows_changed(self, *args):
        if self._pool_guard:
            return
        self._sync_pool_text_from_list(force=True)
        self._update_stats()

    def _on_pool_selection_changed(self):
        self.remove_pool_skill_btn.setEnabled(self.pool_list.currentItem() is not None)

    def _on_pool_item_changed(self, item: QtWidgets.QListWidgetItem):
        if self._pool_guard or item is None:
            return
        new_text = item.text().strip()
        original = item.data(QtCore.Qt.UserRole) or ''
        if not new_text:
            self._pool_guard = True
            item.setText(original)
            self._pool_guard = False
            return

        lower_new = new_text.lower()
        for idx in range(self.pool_list.count()):
            other = self.pool_list.item(idx)
            if other is item:
                continue
            if other.text().strip().lower() == lower_new:
                QtWidgets.QMessageBox.warning(
                    self,
                    self._t('msg_duplicate_skill_title'),
                    self._t('msg_duplicate_skill_body', skill=new_text)
                )
                self._pool_guard = True
                item.setText(original)
                self._pool_guard = False
                return

        self._pool_guard = True
        item.setText(new_text)
        item.setData(QtCore.Qt.UserRole, new_text)
        self._pool_guard = False
        self._sync_pool_text_from_list(force=True)
        self._update_stats()

    def _update_stats(self):
        self.total_skills_value.setText(str(self.skill_table.rowCount()))
        self.pool_value.setText(str(len(self._current_pool_values())))
        suffix = self._t('suffix_seconds').strip()
        suffix = f" {suffix}" if suffix else ''
        self.gcd_value.setText(f"{self.gcd_spin.value():.1f}{suffix}")

    def _sync_pool_list_from_config(self):
        values = list(self.config.SINGLE_SKILL_POOL)
        self._pool_guard = True
        self.pool_list.clear()
        for token in values:
            item = QtWidgets.QListWidgetItem(token)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsDragEnabled)
            item.setData(QtCore.Qt.UserRole, token)
            self.pool_list.addItem(item)
        self.pool_list.clearSelection()
        self.remove_pool_skill_btn.setEnabled(False)
        self._pool_guard = False
        self._sync_pool_text_from_list(force=True)

    def _save_and_accept(self):
        new_pool = self._current_pool_values()
        new_cooldowns = {}
        for row in range(self.skill_table.rowCount()):
            keybind_item = self.skill_table.item(row, 0)
            cooldown_spin = self.skill_table.cellWidget(row, 1)
            if keybind_item and cooldown_spin:
                keybind = keybind_item.text().strip()
                cooldown = cooldown_spin.value()
                if keybind:
                    new_cooldowns[keybind] = cooldown

        payload = {
            'SINGLE_SKILL_POOL': new_pool,
            'SINGLE_SKILL_GLOBAL_COOLDOWN': self.gcd_spin.value(),
            'SKILL_COOLDOWNS': new_cooldowns,
        }

        try:
            self.config.update_config(payload)
        except Exception as e:
            logger.error(f"Failed to persist skill config to JSON: {e}")
            QtWidgets.QMessageBox.warning(
                self,
                self._t('msg_combo_save_warning_title'),
                self._t('msg_failed_skill_json', error=e)
            )
            return

        try:
            parent = self.parent()
            if parent and hasattr(parent, '_update_skill_config'):
                parent._update_skill_config()
            if parent and hasattr(parent, 'log'):
                try:
                    parent.log(translate_text(getattr(parent, 'current_language', 'en'), 'log_skills_updated'))
                except Exception:
                    parent.log('✓ Individual skills updated')
        except Exception:
            pass
        self._sync_pool_list_from_config()
        self._load_skills()
        self._update_stats()

    def _on_cancel(self):
        try:
            parent = self.parent()
            if parent and hasattr(parent, 'change_page'):
                parent.change_page(0)
        except Exception:
            pass


class ComboEditorScreen(QtWidgets.QWidget):
    """Embedded screen for editing combo sets."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('combo_editor_screen')
        self.setMinimumSize(800, 600)

        import skill_combo_config
        self.config = skill_combo_config
        self._language = self._resolve_language()

        layout = QtWidgets.QVBoxLayout(self)

        # Instructions
        self.info_label = QtWidgets.QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("background-color: #424242; padding: 10px; border-radius: 5px;")
        layout.addWidget(self.info_label)
        
        # Combo list
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        
        # Left side: Combo list
        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        self.combo_list_label = QtWidgets.QLabel()
        left_layout.addWidget(self.combo_list_label)
        
        self.combo_list = QtWidgets.QListWidget()
        self.combo_list.currentRowChanged.connect(self._load_combo_details)
        left_layout.addWidget(self.combo_list)
        
        # List buttons
        list_btn_layout = QtWidgets.QHBoxLayout()
        self.new_combo_btn = QtWidgets.QPushButton()
        self.new_combo_btn.clicked.connect(self._new_combo)
        self.delete_combo_btn = QtWidgets.QPushButton()
        self.delete_combo_btn.clicked.connect(self._delete_combo)
        list_btn_layout.addWidget(self.new_combo_btn)
        list_btn_layout.addWidget(self.delete_combo_btn)
        left_layout.addLayout(list_btn_layout)
        
        splitter.addWidget(left_widget)
        
        # Right side: Combo details
        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_widget)
        
        # Combo name
        name_layout = QtWidgets.QFormLayout()
        self.combo_name_edit = QtWidgets.QLineEdit()
        self.combo_name_label = QtWidgets.QLabel()
        name_layout.addRow(self.combo_name_label, self.combo_name_edit)
        right_layout.addLayout(name_layout)
        
        # Enabled checkbox
        self.combo_enabled_cb = QtWidgets.QCheckBox()
        self.combo_enabled_cb.setChecked(True)
        right_layout.addWidget(self.combo_enabled_cb)
        
        # Cooldown
        cooldown_layout = QtWidgets.QHBoxLayout()
        self.combo_cooldown_label = QtWidgets.QLabel()
        cooldown_layout.addWidget(self.combo_cooldown_label)
        self.combo_cooldown_spin = QtWidgets.QDoubleSpinBox()
        self.combo_cooldown_spin.setRange(0.0, 600.0)
        self.combo_cooldown_spin.setSingleStep(1.0)
        self.combo_cooldown_spin.setValue(60.0)
        cooldown_layout.addWidget(self.combo_cooldown_spin)
        cooldown_layout.addStretch()
        right_layout.addLayout(cooldown_layout)
        
        # Delay between skills
        delay_layout = QtWidgets.QHBoxLayout()
        self.combo_delay_label = QtWidgets.QLabel()
        delay_layout.addWidget(self.combo_delay_label)
        self.combo_delay_spin = QtWidgets.QDoubleSpinBox()
        self.combo_delay_spin.setRange(0.0, 5.0)
        self.combo_delay_spin.setSingleStep(0.1)
        self.combo_delay_spin.setValue(0.5)
        delay_layout.addWidget(self.combo_delay_spin)
        delay_layout.addStretch()
        right_layout.addLayout(delay_layout)
        
        # Skills list
        skills_label_layout = QtWidgets.QHBoxLayout()
        self.skills_label = QtWidgets.QLabel()
        skills_label_layout.addWidget(self.skills_label)
        self.add_skill_btn = QtWidgets.QPushButton()
        self.add_skill_btn.setStyleSheet("QPushButton { background-color: #2196F3; color: white; font-weight: bold; padding: 5px; }")
        self.add_skill_btn.clicked.connect(self._add_skill_to_combo)
        skills_label_layout.addWidget(self.add_skill_btn)
        skills_label_layout.addStretch()
        right_layout.addLayout(skills_label_layout)
        
        self.combo_skills_edit = QtWidgets.QPlainTextEdit()
        right_layout.addWidget(self.combo_skills_edit)
        
        # Save combo button
        self.save_combo_btn = QtWidgets.QPushButton()
        self.save_combo_btn.clicked.connect(self._save_current_combo)
        self.save_combo_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px; }")
        right_layout.addWidget(self.save_combo_btn)
        
        splitter.addWidget(right_widget)
        splitter.setSizes([250, 550])
        
        layout.addWidget(splitter)
        
        # Load combo list
        self._load_combo_list()
        
        # Close button will navigate back to Dashboard when embedded
        self.button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        self.button_box.rejected.connect(self._on_close)
        layout.addWidget(self.button_box)
        
        self.current_combo_index = -1

        self.apply_translations(self._language)
    
    def _load_combo_list(self):
        """Load combo sets into list."""
        self.combo_list.clear()
        for combo in self.config.COMBO_SETS:
            enabled_icon = "✓" if combo.get('enabled', True) else "✗"
            self.combo_list.addItem(f"{enabled_icon} {combo['name']}")

    def apply_translations(self, language: str):
        self._language = language or 'en'
        self.info_label.setText(self._t('combo_editor_intro'))
        self.combo_list_label.setText(self._t('label_combo_sets'))
        self.new_combo_btn.setText(self._t('button_new_combo'))
        self.delete_combo_btn.setText(self._t('button_delete_combo'))
        self.combo_name_label.setText(self._t('label_combo_name'))
        self.combo_enabled_cb.setText(self._t('checkbox_combo_enabled'))
        self.combo_cooldown_label.setText(self._t('label_combo_cooldown'))
        self.combo_delay_label.setText(self._t('label_combo_delay'))
        self.skills_label.setText(self._t('label_combo_skills'))
        self.add_skill_btn.setText(self._t('button_add_skill_to_combo'))
        self.save_combo_btn.setText(self._t('button_save_combo'))
        self.combo_skills_edit.setPlaceholderText(self._t('placeholder_combo_skills'))
        suffix = self._t('suffix_seconds')
        self.combo_cooldown_spin.setSuffix(suffix)
        self.combo_delay_spin.setSuffix(suffix)
        close_btn = self.button_box.button(QtWidgets.QDialogButtonBox.Close)
        if close_btn:
            close_btn.setText(self._t('button_close'))

    def _resolve_language(self) -> str:
        parent = self.parent()
        while parent is not None and not hasattr(parent, 'current_language'):
            parent = parent.parent()
        return getattr(parent, 'current_language', 'en')

    def _t(self, key: str, **kwargs) -> str:
        return translate_text(getattr(self, '_language', 'en'), key, **kwargs)
    
    def _load_combo_details(self, row):
        """Load combo details when selected."""
        if row < 0 or row >= len(self.config.COMBO_SETS):
            return
        
        self.current_combo_index = row
        combo = self.config.COMBO_SETS[row]
        
        self.combo_name_edit.setText(combo['name'])
        self.combo_enabled_cb.setChecked(combo.get('enabled', True))
        self.combo_cooldown_spin.setValue(combo.get('cooldown', 60.0))
        self.combo_delay_spin.setValue(combo.get('delay_between_skills', 0.5))
        self.combo_skills_edit.setPlainText("\n".join(combo.get('skills', [])))
    
    def _new_combo(self):
        """Create a new combo set."""
        new_combo = {
            'name': self._t('default_combo_name', index=len(self.config.COMBO_SETS) + 1),
            'skills': [],
            'cooldown': 60.0,
            'delay_between_skills': 0.5,
            'enabled': True,
        }
        new_combos = list(self.config.COMBO_SETS) + [new_combo]
        try:
            self.config.update_config({'COMBO_SETS': new_combos})
        except Exception as e:
            logger.error(f"Failed to persist combo config to JSON: {e}")
            QtWidgets.QMessageBox.warning(
                self,
                self._t('msg_combo_save_warning_title'),
                self._t('msg_combo_save_warning_body', error=e)
            )
            return
        self._load_combo_list()
        self.combo_list.setCurrentRow(len(self.config.COMBO_SETS) - 1)
    
    def _delete_combo(self):
        """Delete selected combo set."""
        current_row = self.combo_list.currentRow()
        if current_row >= 0 and current_row < len(self.config.COMBO_SETS):
            combo_name = self.config.COMBO_SETS[current_row]['name']
            
            # Confirm deletion
            reply = QtWidgets.QMessageBox.question(
                self,
                self._t('msg_combo_delete_title'),
                self._t('msg_combo_delete_body', name=combo_name),
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            
            if reply == QtWidgets.QMessageBox.Yes:
                new_combos = list(self.config.COMBO_SETS)
                del new_combos[current_row]
                try:
                    self.config.update_config({'COMBO_SETS': new_combos})
                except Exception as e:
                    logger.error(f"Failed to persist combo config to JSON: {e}")
                    QtWidgets.QMessageBox.warning(
                        self,
                        self._t('msg_combo_save_warning_title'),
                        self._t('msg_combo_save_warning_body', error=e)
                    )
                    return
                self._load_combo_list()
                self.combo_name_edit.clear()
                self.combo_skills_edit.clear()
    
    def _add_skill_to_combo(self):
        """Add a skill to the combo using keybind capture."""
        capture_dialog = KeybindCaptureDialog(self)
        if capture_dialog.exec() and capture_dialog.captured_key:
            keybind = capture_dialog.captured_key
            
            # Add to the end of the skills list
            current_text = self.combo_skills_edit.toPlainText().strip()
            if current_text:
                self.combo_skills_edit.setPlainText(current_text + "\n" + keybind)
            else:
                self.combo_skills_edit.setPlainText(keybind)
    
    def _save_current_combo(self):
        """Save current combo details."""
        if self.current_combo_index < 0 or self.current_combo_index >= len(self.config.COMBO_SETS):
            return
        
        combo = dict(self.config.COMBO_SETS[self.current_combo_index])
        combo['name'] = self.combo_name_edit.text().strip() or self._t('default_combo_name', index=self.current_combo_index + 1)
        combo['enabled'] = self.combo_enabled_cb.isChecked()
        combo['cooldown'] = self.combo_cooldown_spin.value()
        combo['delay_between_skills'] = self.combo_delay_spin.value()

        skills_text = self.combo_skills_edit.toPlainText().strip()
        combo['skills'] = [s.strip() for s in skills_text.split("\n") if s.strip()]

        new_combos = list(self.config.COMBO_SETS)
        new_combos[self.current_combo_index] = combo
        try:
            self.config.update_config({'COMBO_SETS': new_combos})
        except Exception as e:
            logger.error(f"Failed to persist combo config to JSON: {e}")
            QtWidgets.QMessageBox.warning(
                self,
                self._t('msg_combo_save_warning_title'),
                self._t('msg_combo_save_warning_body', error=e)
            )
            return

        self._load_combo_list()
        self.combo_list.setCurrentRow(self.current_combo_index)

        QtWidgets.QMessageBox.information(
            self,
            self._t('msg_combo_save_info_title'),
            self._t('msg_combo_saved', name=combo['name'])
        )
    
    def _on_close(self):
        """Handle close action for embedded combo editor: navigate back to Dashboard."""
        try:
            parent = self.parent()
            if parent and hasattr(parent, 'change_page'):
                parent.change_page(0)
        except Exception:
            pass


    


def run_app():
    """Main application entry point."""
    app = QtWidgets.QApplication(sys.argv)
    # Apply a dark purple theme stylesheet for the whole app
    app.setStyleSheet("""
    QWidget { background-color: #1b1226; color: #EDE7F6; font-family: 'Segoe UI', Tahoma, Arial; }
    QGroupBox { background-color: #24132f; border: 1px solid #3a1f3b; border-radius: 8px; margin-top: 6px; }
    QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 4px 8px; color: #D1C4E9; }
    QPushButton { background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #5e35b1, stop:1 #7e57c2); color: white; border-radius: 6px; padding: 8px; }
    QPlainTextEdit, QTextEdit { background-color: #0f0815; border: 1px solid #2b1430; }
    QTableWidget { background-color: #120716; gridline-color: #2b1430; }
    QHeaderView::section { background-color: #2b1430; color: #EDE7F6; }
    QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit { background-color: #120716; color: #EDE7F6; border: 1px solid #2b1430; }
    QStackedWidget#pages { background: transparent; }
    """)

    # Interception is the required backend for input control
    logger.info("Interception backend enforced; ensure interception driver is installed")

    try:
        import skill_combo_config as _scc_lang
        app_language = getattr(_scc_lang, 'LANGUAGE', 'en') or 'en'
    except Exception:
        app_language = 'en'
        _scc_lang = None

    # Pre-start checklist dialog
    class PreStartDialog(QtWidgets.QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle(translate_text(app_language, 'prestart_title'))
            self.setModal(True)
            self.setMinimumSize(700, 520)

            layout = QtWidgets.QVBoxLayout(self)

            info = QtWidgets.QLabel(translate_text(app_language, 'prestart_info'))
            info.setWordWrap(True)
            layout.addWidget(info)

            self.remember_cb = QtWidgets.QCheckBox(translate_text(app_language, 'prestart_remember'))
            self.remember_cb.setChecked(True)
            layout.addWidget(self.remember_cb)

            # Spacer + button
            spacer = QtWidgets.QSpacerItem(20, 20, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
            layout.addItem(spacer)

            btn = QtWidgets.QPushButton(translate_text(app_language, 'prestart_button'))
            btn.setFixedHeight(44)
            btn.clicked.connect(self.accept)
            btn.setStyleSheet("QPushButton { font-weight: bold; font-size: 12pt; padding: 8px; }")
            h = QtWidgets.QHBoxLayout()
            h.addStretch()
            h.addWidget(btn)
            h.addStretch()
            layout.addLayout(h)

    def _check_and_install_interception(parent_window=None):
        """Check for driver sys files and attempt installation if missing.

        Returns True if drivers are present after this call (may require restart), False otherwise.
        """
        try:
            import subprocess
            from pathlib import Path
            sysroot = os.environ.get('SystemRoot', r'C:\Windows')
            drivers_dir = Path(sysroot) / 'System32' / 'drivers'
            required = [drivers_dir / 'mouse.sys', drivers_dir / 'keyboard.sys']
            missing = [p for p in required if not p.exists()]
            if not missing:
                return True

            # Attempt to run bundled installer (requires admin - run_app already ensures elevation)
            installer = Path(__file__).parent / 'Interception' / 'command line installer' / 'install-interception.exe'
            if installer.exists():
                try:
                    # Build a PowerShell command that opens an elevated PowerShell window,
                    # cds to the installer folder and runs the installer. We wait for the
                    # launched window to finish so we can notify the user afterwards.
                    installer_dir = str(installer.parent)
                    installer_name = installer.name

                    # Inner command executed inside the elevated PowerShell window
                    inner_cmd = (
                        f"Set-Location -LiteralPath '{installer_dir}';"
                        f" .\\{installer_name};"
                        " Read-Host -Prompt 'Press Enter to close';"
                        " exit"
                    )

                    # Outer PowerShell will Start-Process powershell -Verb runAs with -ArgumentList
                    # and -Wait so this call returns when the elevated window closes.
                    outer_cmd = (
                        "Start-Process powershell -Verb runAs -ArgumentList "
                        f"'-NoProfile -ExecutionPolicy Bypass -Command \"{inner_cmd}\"' -Wait"
                    )

                    # Execute the outer command using the system PowerShell and wait for completion
                    subprocess.run([
                        'powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                        '-Command', outer_cmd
                    ], check=False)
                except Exception as e:
                    logger.error(f"Failed to run interception installer via PowerShell: {e}")
            else:
                logger.warning("Interception installer not found in repository; please install manually")

            # Re-check files
            missing = [p for p in required if not p.exists()]
            if missing:
                # Inform user to restart after manual install or that automatic install failed
                QtWidgets.QMessageBox.warning(
                    parent_window,
                    translate_text(app_language, 'msg_interception_missing_title'),
                    translate_text(app_language, 'msg_interception_missing_body')
                )
                return False
            else:
                # Notify user to restart to finalize installation
                QtWidgets.QMessageBox.information(
                    parent_window,
                    translate_text(app_language, 'msg_interception_installed_title'),
                    translate_text(app_language, 'msg_interception_installed_body')
                )
                return True
        except Exception as e:
            logger.error(f"Error while checking/installing interception: {e}")
            return False

    # Remember confirmation only after acceptance, never when the dialog is cancelled.
    if not getattr(_scc_lang, 'SKIP_PRESTART_CHECKLIST', False):
        dlg = PreStartDialog()
        if dlg.exec() != QtWidgets.QDialog.Accepted:
            logger.info("User cancelled pre-start checklist; exiting")
            return
        if _scc_lang is not None:
            _scc_lang.update_config({'SKIP_PRESTART_CHECKLIST': dlg.remember_cb.isChecked()})

    # After user confirmation, check and attempt to install interception if necessary
    _check_and_install_interception()

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    logger.info("Starting AION automation (Interception backend)")
    # REQUIRE administrator privileges - do not run without admin
    try:
        if not is_admin():
            logger.info("Not running as administrator - attempting to relaunch elevated...")
            # run_as_admin will exit on success; if it fails we MUST NOT continue
            run_as_admin()
            # If we reach here, elevation failed or was cancelled - EXIT IMMEDIATELY
            logger.error("Administrator privileges are REQUIRED to run this program.")
            logger.error("Please right-click the script and select 'Run as administrator'")
            input("\nPress Enter to exit...")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Admin elevation failed: {e}")
        logger.error("Administrator privileges are REQUIRED to run this program.")
        input("\nPress Enter to exit...")
        sys.exit(1)

    # Only reach here if running as admin
    logger.success("✓ Running with administrator privileges")
    run_app()

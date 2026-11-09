"""Monitor de telas, envio de eventos para a interface e teclado Windows.

A interface fica em main.py; este módulo NÃO importa Tkinter.
O envio de teclas e os cliques são opcionais e dependem das permissões
/ restrições do aplicativo em primeiro plano.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import queue
import threading
import time
from pathlib import Path

import pyautogui

from detector import detect_all, screenshot_gray

# Nunca desligar o fail-safe do PyAutoGUI.
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.15

# --- Teclado por scan code (SendInput) -------------------------------------
# SendInput é uma API de entrada simulada do Windows; alguns jogos
# podem ignorar essas teclas. Não há mecanismo de contorno de proteção.
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
SCAN_W = 0x11


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUT_UNION)]


def _send_scan(scan, key_up=False):
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if key_up else 0)
    event = _INPUT(type=INPUT_KEYBOARD, u=_INPUT_UNION(ki=_KEYBDINPUT(0, scan, flags, 0, 0)))
    send_input = ctypes.windll.user32.SendInput
    # Evita truncar ponteiros em Python 64 bits.
    send_input.argtypes = (wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int)
    send_input.restype = wintypes.UINT
    return send_input(1, ctypes.byref(event), ctypes.sizeof(_INPUT))


def foreground_info():
    """Retorna título e executável da janela ativa no Windows.

    Declara assinaturas ctypes para não truncar handles em Windows 64 bits.
    """
    title, exe = "", ""
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
        user32.GetWindowTextLengthW.restype = ctypes.c_int
        user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
        user32.GetWindowTextW.restype = ctypes.c_int
        user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.QueryFullProcessImageNameW.argtypes = (
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return title, exe
        length = user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        handle = kernel32.OpenProcess(0x1000, False, pid.value)
        if handle:
            try:
                path = ctypes.create_unicode_buffer(1024)
                size = wintypes.DWORD(1024)
                if kernel32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)):
                    exe = Path(path.value).name
            finally:
                kernel32.CloseHandle(handle)
    except (AttributeError, OSError):
        pass
    return title, exe


def fortnite_in_foreground():
    title, exe = foreground_info()
    return "fortnite" in title.lower() or "fortnite" in exe.lower()


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


class KeyHolder:
    """Aperta e solta o W repetidamente numa thread própria.

    Todo 'down' é seguido por um 'up' na mesma thread, então o W nunca fica preso.
    """

    PRESS_TIME = 0.10  # tempo que cada toque dura

    def __init__(self, interval=0.5):
        self.interval = interval
        self.last_sent = None
        self._active = threading.Event()
        self._stop = threading.Event()
        self._thread = None

    @property
    def is_down(self):
        return self._active.is_set()

    def _run(self):
        while not self._stop.is_set():
            if self._active.is_set():
                self.last_sent = _send_scan(SCAN_W)
                time.sleep(self.PRESS_TIME)
                _send_scan(SCAN_W, key_up=True)
                self._stop.wait(self.interval)
            else:
                self._stop.wait(0.05)

    def hold(self):
        """Ativa os toques repetidos (nome mantido por compatibilidade)."""
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        self._active.set()
        return self.last_sent

    def release(self):
        self._active.clear()

    def close(self):
        self._active.clear()
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
            try:
                _send_scan(SCAN_W, key_up=True)
            except (AttributeError, OSError):
                pass




class MonitorRunner:
    """Executa o ciclo de monitoramento em uma thread externa.

    Emite pares (tipo, dado) na fila; a GUI atualiza seus widgets
    somente a partir da thread principal do Tkinter.
    """
    def __init__(self, messages: queue.Queue, stop_event: threading.Event):
        self.messages = messages
        self.stop_event = stop_event

    def run(self, templates, threshold, auto, hold_w=False, hold_always=False, w_interval=0.5):
        keys = KeyHolder(w_interval)
        warned_send = False
        warned_focus = False
        presumed = False
        unknown_streak = 0   # leituras seguidas sem reconhecer nenhuma tela
        played = False       # já saímos do lobby (JOGAR sumiu) desde a última partida
        in_match = False
        end_recorded = False
        previous_status = None
        last_action = {"jogar": 0.0, "voltar": 0.0}
        try:
            while not self.stop_event.is_set():
                screen = screenshot_gray(pyautogui.screenshot())
                found = detect_all(screen, templates, threshold)

                # A ordem importa: telas de resultado têm prioridade sobre o HUD.
                if found.get("voltar") or found.get("fim"):
                    state = "Partida encerrada / resultado"
                    if in_match and not end_recorded:
                        end_recorded = True
                        in_match = False
                        self.messages.put(("match", None))
                    if auto and found.get("voltar"):
                        self._try_click("voltar", found["voltar"], last_action, 20)
                elif found.get("partida"):
                    state = "Em partida"
                    in_match = True
                    end_recorded = False
                elif found.get("jogar"):
                    state = "No lobby"
                    # Registros são feitos ao detectar uma tela de resultado.
                    # Não conte simplesmente por voltar ao lobby.
                    in_match = False
                    end_recorded = False
                    if auto:
                        self._try_click("jogar", found["jogar"], last_action, 40)
                else:
                    state = "Carregando / tela não reconhecida"
                    unknown_streak += 1
                    # Fallback: se o HUD não é reconhecido mas JOGAR sumiu do lobby e
                    # nada mais aparece por ~6 s, assumimos que a partida começou
                    # (e continua assim até uma tela conhecida aparecer).
                    if hold_w and played and (presumed or unknown_streak >= 3):
                        presumed = True
                        state = "Em partida (presumido, HUD não reconhecido)"
                        in_match = True
                        end_recorded = False
                if not state.startswith(("Carregando", "Em partida (presumido")):
                    unknown_streak = 0
                    presumed = False
                if state == "No lobby":
                    played = True
                elif state.startswith("Partida encerrada"):
                    played = False

                if hold_w:
                    focused = fortnite_in_foreground()
                    if (hold_always or state.startswith("Em partida")) and focused:
                        if not keys.is_down:
                            self.messages.put(("log", "Apertando W repetidamente."))
                        sent = keys.hold()
                        if sent is not None and sent != 1 and not warned_send:
                            warned_send = True
                            self.messages.put(("log", "AVISO: o Windows recusou o envio do W (tente como administrador)."))
                    else:
                        if keys.is_down:
                            keys.release()
                            self.messages.put(("log", "W solto."))
                        if (hold_always or state.startswith("Em partida")) and not focused and not warned_focus:
                            warned_focus = True
                            title, exe = foreground_info()
                            self.messages.put(("log", f"Em partida, mas janela ativa não é o Fortnite: '{title}' ({exe}). W não enviado."))
                    if not state.startswith("Em partida"):
                        warned_focus = False

                if state != previous_status:
                    self.messages.put(("status", state))
                    previous_status = state
                if self.stop_event.wait(2.0):
                    break
        except pyautogui.FailSafeException:
            self.messages.put(("error", "Parada de emergência: mouse no canto superior esquerdo."))
        except Exception as exc:
            self.messages.put(("error", f"Erro durante a captura: {exc}"))
        finally:
            keys.close()  # encerra a thread; nenhum W fica preso
            self.messages.put(("stopped", None))

    def _try_click(self, key, detection, last_action, cooldown):
        now = time.monotonic()
        if now - last_action[key] < cooldown:
            return
        if not fortnite_in_foreground():
            return
        x, y, confidence = detection
        # Clique no centro da região capturada. Sem alterar jogo/anticheat.
        pyautogui.click(x=x, y=y)
        last_action[key] = now
        self.messages.put(("log", f"Clique em {key} ({confidence:.2f}) na posição {x},{y}."))


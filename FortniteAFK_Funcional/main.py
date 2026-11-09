"""Interface gráfica do Fortnite Vision Monitor.

Responsabilidade deste arquivo: interface, eventos Tkinter e captura guiada
pelas imagens. O processamento de imagens fica em detector.py; o ciclo
em segundo plano e o teclado ficam em monitor.py.
"""
from __future__ import annotations

import queue
import threading
import time
from datetime import datetime

import pyautogui
import tkinter as tk
from PIL import ImageTk
from tkinter import messagebox, ttk

from config import REFERENCES, TEMPLATES
from detector import best_match, load_templates, screenshot_gray
from historico import load_history, save_history
from monitor import KeyHolder, MonitorRunner, foreground_info, is_admin

class MonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Fortnite Vision Monitor | Python")
        self.root.geometry("640x640")
        self.root.minsize(600, 600)
        self.messages = queue.Queue()
        self.stop_event = threading.Event()
        self.worker = None
        self.history = load_history()
        self.matches_session = 0
        self.capture_busy = False
        self.auto_var = tk.BooleanVar(value=False)
        self.hold_w_var = tk.BooleanVar(value=False)
        self.hold_always_var = tk.BooleanVar(value=False)
        self.w_interval_var = tk.StringVar(value="0.5")
        self.status_var = tk.StringVar(value="Aguardando configuração")
        self.count_var = tk.StringVar(value=f"Partidas: {len(self.history)} no histórico | 0 nesta sessão")
        self.threshold_var = tk.StringVar(value="0.85")
        self.template_labels = {}
        self._make_ui()
        self._refresh_templates()
        self.root.after(250, self._drain_messages)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _make_ui(self):
        frame = ttk.Frame(self.root, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="FORTNITE VISION MONITOR", font=("Segoe UI", 19, "bold")).pack(anchor="w")
        ttk.Label(
            frame,
            text="Reconhece imagens da tela. Salva as partidas e pode executar cliques opcionais.",
            wraplength=590,
        ).pack(anchor="w", pady=(4, 15))

        refs = ttk.LabelFrame(frame, text="Imagens de referência — capture cada elemento", padding=12)
        refs.pack(fill="x")
        for key, (label, _) in REFERENCES.items():
            row = ttk.Frame(refs)
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=label).pack(side="left")
            ttk.Button(row, text="Capturar", command=lambda k=key: self._capture(k)).pack(side="right")
            indicator = ttk.Label(row, text="Falta", width=9)
            indicator.pack(side="right", padx=(4, 10))
            self.template_labels[key] = indicator

        ttk.Label(
            frame,
            text=("Ao clicar em Capturar: abra o Fortnite em até 4 segundos e "
                  "arraste o mouse ao redor do botão ou elemento visual."),
            wraplength=590,
            foreground="#555555",
        ).pack(anchor="w", pady=(8, 13))

        settings = ttk.Frame(frame)
        settings.pack(fill="x")
        ttk.Label(settings, text="Confiança (0,70–0,99):").pack(side="left")
        ttk.Entry(settings, width=7, textvariable=self.threshold_var).pack(side="left", padx=8)
        ttk.Label(settings, text="  Intervalo do W (s):").pack(side="left")
        ttk.Entry(settings, width=5, textvariable=self.w_interval_var).pack(side="left", padx=4)
        ttk.Button(settings, text="Testar reconhecimento", command=self._test_once).pack(side="right")
        ttk.Button(settings, text="Testar W", command=self._test_w).pack(side="right", padx=(0, 8))

        ttk.Checkbutton(
            frame,
            text="Automação opcional: clicar em Jogar / Voltar ao lobby quando detectados",
            variable=self.auto_var,
        ).pack(anchor="w", pady=(12, 4))
        ttk.Checkbutton(
            frame,
            text="Apertar a tecla W repetidamente durante a partida (só com o Fortnite em primeiro plano)",
            variable=self.hold_w_var,
        ).pack(anchor="w", pady=(0, 2))
        ttk.Checkbutton(
            frame,
            text="   W contínuo: apertar sempre, em qualquer tela, até clicar em Parar",
            variable=self.hold_always_var,
        ).pack(anchor="w", pady=(0, 4))
        ttk.Label(
            frame,
            text="A automação de partidas pode contrariar regras do jogo. Use por sua conta e risco.",
            foreground="#845000",
            wraplength=580,
        ).pack(anchor="w", pady=(0, 12))

        ttk.Separator(frame).pack(fill="x", pady=4)
        ttk.Label(frame, textvariable=self.status_var, font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(12, 6))
        ttk.Label(frame, textvariable=self.count_var).pack(anchor="w", pady=(0, 12))

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")
        self.start_button = ttk.Button(buttons, text="▶ Iniciar", command=self._start)
        self.start_button.pack(side="left", fill="x", expand=True, padx=(0, 7))
        self.stop_button = ttk.Button(buttons, text="■ Parar", command=self._stop, state="disabled")
        self.stop_button.pack(side="left", fill="x", expand=True)

        ttk.Label(frame, text="Registro de eventos", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(16, 4))
        self.log = tk.Text(frame, height=7, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True)
        self._log("Pronto. Capture as referências e pressione Iniciar.")

    def _log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log.configure(state="normal")
        self.log.insert("end", f"[{timestamp}] {message}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _refresh_templates(self):
        for key, (_, filename) in REFERENCES.items():
            self.template_labels[key].configure(
                text="OK" if (TEMPLATES / filename).exists() else "Falta"
            )

    def _capture(self, key):
        if self.capture_busy or (self.worker and self.worker.is_alive()):
            messagebox.showinfo("Aviso", "Pare o monitoramento antes de capturar novas imagens.")
            return
        self.capture_busy = True
        self.status_var.set("Abra o Fortnite; captura em 4 segundos...")
        self.root.withdraw()

        def task():
            try:
                time.sleep(4)
                screenshot = pyautogui.screenshot()
                self.messages.put(("select", (key, screenshot)))
            except Exception as exc:
                self.messages.put(("capture_error", str(exc)))

        threading.Thread(target=task, daemon=True).start()

    def _show_selector(self, key, screenshot):
        # Captura da tela sem alterar os arquivos do jogo.
        overlay = tk.Toplevel(self.root)
        overlay.overrideredirect(True)
        overlay.attributes("-topmost", True)
        w, h = screenshot.size
        overlay.geometry(f"{w}x{h}+0+0")
        canvas = tk.Canvas(overlay, width=w, height=h, borderwidth=0, highlightthickness=0, cursor="crosshair")
        canvas.pack()
        picture = ImageTk.PhotoImage(screenshot, master=overlay)
        canvas.create_image(0, 0, anchor="nw", image=picture)
        canvas.picture = picture
        canvas.create_rectangle(0, 0, 630, 35, fill="black", outline="")
        canvas.create_text(12, 18, anchor="w", fill="white",
                           text="Selecione com o mouse a área do elemento. ESC cancela.")
        start = [0, 0]
        rect = [None]

        def end_selection():
            overlay.destroy()
            self.root.deiconify()
            self.root.lift()
            self.capture_busy = False

        def press(event):
            start[:] = [event.x, event.y]
            if rect[0]:
                canvas.delete(rect[0])
            rect[0] = canvas.create_rectangle(event.x, event.y, event.x, event.y,
                                              outline="yellow", width=3)

        def motion(event):
            if rect[0]:
                canvas.coords(rect[0], start[0], start[1], event.x, event.y)

        def release(event):
            x1, x2 = sorted((max(0, start[0]), min(w, event.x)))
            y1, y2 = sorted((max(0, start[1]), min(h, event.y)))
            if x2 - x1 < 35 or y2 - y1 < 14:
                messagebox.showwarning("Área pequena", "Selecione uma área maior, como um botão inteiro.", parent=overlay)
                return
            _, filename = REFERENCES[key]
            screenshot.crop((x1, y1, x2, y2)).save(TEMPLATES / filename)
            end_selection()
            self._refresh_templates()
            self.status_var.set(f"Referência salva: {filename}")
            self._log(f"Capturada referência {filename} ({x2-x1}x{y2-y1}).")

        canvas.bind("<Button-1>", press)
        canvas.bind("<B1-Motion>", motion)
        canvas.bind("<ButtonRelease-1>", release)
        overlay.bind("<Escape>", lambda event: (end_selection(), self.status_var.set("Captura cancelada")))
        overlay.focus_force()

    def _get_threshold(self):
        try:
            value = float(self.threshold_var.get().replace(",", "."))
        except ValueError:
            return None
        return value if 0.7 <= value <= 0.99 else None

    def _load_templates(self):
        return load_templates()

    def _test_once(self):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Aviso", "Pare o monitoramento antes do teste.")
            return
        threshold = self._get_threshold()
        if threshold is None:
            messagebox.showerror("Confiança", "Use um valor entre 0,70 e 0,99.")
            return
        templates = self._load_templates()
        if not templates:
            messagebox.showwarning("Referências", "Capture pelo menos uma referência primeiro.")
            return
        self._log("Teste em 4 segundos. Coloque o Fortnite na frente.")
        self.root.iconify()

        def task():
            try:
                time.sleep(4)
                screen = screenshot_gray(pyautogui.screenshot())
                results = []
                for key, template in templates.items():
                    score = best_match(screen, template)
                    found = score is not None and score[2] >= threshold
                    results.append(
                        f"{key}: {'SIM' if found else 'não'} "
                        f"(confiança {score[2]:.2f})" if score else f"{key}: referência inválida"
                    )
                self.messages.put(("test_result", "; ".join(results)))
            except Exception as exc:
                self.messages.put(("error", str(exc)))

        threading.Thread(target=task, daemon=True).start()

    def _test_w(self):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Aviso", "Pare o monitoramento antes do teste.")
            return
        self._log("Teste do W em 4 segundos. Volte ao Fortnite (dentro da partida).")
        self.root.iconify()

        def task():
            keys = KeyHolder(0.4)
            try:
                time.sleep(4)
                title, exe = foreground_info()
                focused = "fortnite" in title.lower() or "fortnite" in exe.lower()
                keys.hold()
                time.sleep(3)
                keys.close()
                sent = keys.last_sent
                self.messages.put(("test_result",
                    f"Janela: '{title}' | processo: {exe or '?'} | reconhecida como Fortnite: "
                    f"{'SIM' if focused else 'NÃO'} | SendInput aceitou: {sent} | "
                    f"app como administrador: {'SIM' if is_admin() else 'NÃO'}. "
                    "O Windows aceitar a tecla não garante que o jogo responda."))
            except Exception as exc:
                keys.close()
                self.messages.put(("error", str(exc)))

        threading.Thread(target=task, daemon=True).start()

    def _start(self):
        if self.worker and self.worker.is_alive():
            return
        threshold = self._get_threshold()
        if threshold is None:
            messagebox.showerror("Confiança", "Use um valor entre 0,70 e 0,99.")
            return
        templates = self._load_templates()
        if "jogar" not in templates or "partida" not in templates or not ("fim" in templates or "voltar" in templates):
            messagebox.showwarning(
                "Faltam imagens",
                "Capture JOGAR, HUD da partida e pelo menos uma imagem de FIM ou VOLTAR AO LOBBY.",
            )
            return
        if self.auto_var.get() and "voltar" not in templates:
            messagebox.showwarning("Faltam imagens", "Para retorno automático, capture também VOLTAR AO LOBBY.")
            return
        self.stop_event.clear()
        auto = self.auto_var.get()
        hold_always = self.hold_always_var.get()
        try:
            w_interval = max(0.1, min(10.0, float(self.w_interval_var.get().replace(",", "."))))
        except ValueError:
            messagebox.showerror("Intervalo do W", "Use um número em segundos, ex.: 0,5.")
            return
        hold_w = self.hold_w_var.get() or hold_always
        self.matches_session = 0
        self.count_var.set(f"Partidas: {len(self.history)} no histórico | 0 nesta sessão")
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status_var.set("Monitor iniciando... Mude para o Fortnite.")
        self._log("Monitor iniciado" + (" (cliques automáticos ativados)." if auto else " (somente observação).")
                  + (" Apertando W durante a partida." if hold_w else ""))
        runner = MonitorRunner(self.messages, self.stop_event)
        self.worker = threading.Thread(
            target=runner.run,
            args=(templates, threshold, auto, hold_w, hold_always, w_interval),
            daemon=True,
        )
        self.worker.start()

    def _stop(self):
        self.stop_event.set()
        self.status_var.set("Parando monitoramento...")
        self._log("Parada solicitada.")

    def _drain_messages(self):
        while True:
            try:
                kind, value = self.messages.get_nowait()
            except queue.Empty:
                break
            if kind == "select":
                key, screenshot = value
                self._show_selector(key, screenshot)
            elif kind == "capture_error":
                self.root.deiconify()
                self.capture_busy = False
                messagebox.showerror("Falha na captura", value)
            elif kind == "status":
                self.status_var.set(value)
                self._log(value)
            elif kind == "match":
                self.matches_session += 1
                record = {"fim": datetime.now().isoformat(timespec="seconds")}
                self.history.append(record)
                try:
                    save_history(self.history)
                except OSError as exc:
                    self._log(f"Não foi possível salvar o histórico: {exc}")
                self.count_var.set(
                    f"Partidas: {len(self.history)} no histórico | {self.matches_session} nesta sessão"
                )
                self._log("Partida concluída e registrada.")
            elif kind == "log":
                self._log(value)
            elif kind == "test_result":
                self.root.deiconify()
                self._log(value)
                messagebox.showinfo("Teste de reconhecimento", value)
            elif kind == "error":
                self.root.deiconify()
                self._log(value)
                messagebox.showerror("Monitor", value)
            elif kind == "stopped":
                self.start_button.configure(state="normal")
                self.stop_button.configure(state="disabled")
                self.status_var.set("Monitoramento parado")
                self._log("Monitoramento encerrado.")
        self.root.after(250, self._drain_messages)

    def _on_close(self):
        self.stop_event.set()
        # A thread de monitoramento libera o teclado em seu finally.
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    try:
        ttk.Style(root).theme_use("clam")
    except tk.TclError:
        pass
    MonitorApp(root)
    root.mainloop()

"""Reconhecimento visual da tela com OpenCV.

Não interage com o teclado nem com o jogo: apenas recebe imagens
capturadas ou carrega referências e devolve correspondências.
"""
from pathlib import Path

import cv2
import numpy as np

from config import REFERENCES, TEMPLATES


def load_templates(folder: Path = TEMPLATES):
    """Carrega imagens de referência em tons de cinza.

    Usa imdecode para aceitar caminhos contendo acentos no Windows.
    """
    templates = {}
    for key, (_, filename) in REFERENCES.items():
        path = folder / filename
        if not path.exists():
            continue
        pixels = np.fromfile(str(path), dtype=np.uint8)
        image = cv2.imdecode(pixels, cv2.IMREAD_GRAYSCALE)
        if image is not None:
            templates[key] = image
    return templates


def screenshot_gray(screenshot):
    """Converte uma captura PIL RGB para escala de cinza."""
    rgb = np.asarray(screenshot.convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)


def best_match(screen_gray, template_gray):
    """Retorna (x_centro, y_centro, confiança) da melhor região ou None.

    A comparação é feita no tamanho exato da referência. Se a resolução
    do jogo mudar, capture outra referência na resolução atual.
    """
    sh, sw = screen_gray.shape[:2]
    h, w = template_gray.shape[:2]
    if h > sh or w > sw or min(h, w) < 8:
        return None
    if np.std(template_gray) < 1.0:
        return None  # imagem uniforme, pouco confiável
    heatmap = cv2.matchTemplate(screen_gray, template_gray, cv2.TM_CCOEFF_NORMED)
    _, confidence, _, top_left = cv2.minMaxLoc(heatmap)
    if not np.isfinite(confidence):
        return None
    return (top_left[0] + w // 2, top_left[1] + h // 2, float(confidence))


def detect(screen_gray, template_gray, threshold):
    """Retorna (x, y, confiança) se a confiança alcançar o limite."""
    found = best_match(screen_gray, template_gray)
    return found if found is not None and found[2] >= threshold else None


def detect_all(screen_gray, templates, threshold):
    return {key: detect(screen_gray, template, threshold)
            for key, template in templates.items()}

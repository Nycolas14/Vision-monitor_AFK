"""Caminhos e referências do projeto. Sem lógica de interface."""
from pathlib import Path

BASE = Path(__file__).resolve().parent
TEMPLATES = BASE / "templates"
HISTORY = BASE / "partidas.json"
TEMPLATES.mkdir(parents=True, exist_ok=True)

REFERENCES = {
    "jogar": ("1. Botão JOGAR (no lobby)", "jogar.png"),
    "partida": ("2. HUD da partida (ex.: barra de vida)", "partida.png"),
    "fim": ("3. Tela de eliminação/vitória (opcional)", "fim.png"),
    "voltar": ("4. Botão VOLTAR AO LOBBY", "voltar.png"),
}

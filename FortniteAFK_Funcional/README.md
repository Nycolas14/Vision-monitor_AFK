# Fortnite Vision Monitor — código modular em Python

Projeto de estudo que usa **OpenCV** para identificar elementos visuais em capturas de tela e **Tkinter** para exibir o estado do monitoramento. Há recursos **opcionais** de clique e envio simulado de `W`, que podem não funcionar em jogos e contrariar as regras da plataforma.

## Organização dos arquivos

```text
FortniteAFKMonitor_Organizado/
├── main.py             # Interface: botões, janelas e histórico na tela
├── detector.py         # Carrega referências e identifica imagens com OpenCV
├── monitor.py          # Monitoramento em thread, eventos e envio opcional de teclado
├── historico.py        # Leitura e gravação de partidas.json
├── config.py           # Caminhos e nomes de imagens
├── templates/          # Imagens de referência capturadas pelo usuário
├── tests/              # Testes unitários sem precisar abrir o Fortnite
├── requirements.txt    # Bibliotecas Python
├── INSTALAR.bat         # Instala no Windows
├── INICIAR.bat          # Inicia a interface
├── .gitignore           # Ignora arquivos temporários e histórico local
└── README.md            # Este documento
```

## Instalação (Windows)

1. Instale Python e marque a opção de adicioná-lo ao PATH, ou use o comando `py`.
2. Abra a pasta no Visual Studio Code.
3. No terminal, execute:
   ```powershell
   py -m pip install -r requirements.txt
   py main.py
   ```
   Alternativamente, dê duplo clique em `INSTALAR.bat` e depois em `INICIAR.bat`.

## Como testar o reconhecimento

1. Mantenha a resolução do jogo fixa e use **Janela em tela cheia**.
2. Em `main.py`, a interface oferece **Capturar** para cada referência. Volte ao jogo em até 4 segundos e selecione a região visual do botão/HUD.
3. Capture: `jogar.png`, `partida.png`, `fim.png` (opcional) e `voltar.png` na pasta `templates/`.
4. Clique em **Testar reconhecimento**. O log mostra **SIM / não** e também a confiança (0 a 1) de cada referência, mesmo que não seja encontrada.
5. Configure o limite de confiança; o padrão é `0.85`. Uma imagem com texto nítido e fundo estável normalmente funciona melhor.

O aplicativo acompanha partidas e registra o fim somente quando vê uma tela de partida **antes** da tela de resultado. Assim, o contador é uma estimativa, não uma leitura oficial do Fortnite.

## Testes automáticos

```powershell
py -m unittest discover -s tests -v
```

## Cuidados

- O reconhecimento depende da resolução, escala, idioma e interface atual do jogo.
- A API de teclado simulado do Windows pode não ser aceita pelo Fortnite. **Não existe garantia de funcionamento dentro do jogo**.
- Não lê memória, não modifica arquivos, não interfere com mecanismos de proteção ou anti-cheat.
- **Parar** interrompe o loop. Mover o mouse ao canto superior esquerdo ativa o mecanismo de emergência do PyAutoGUI.
- A automação de partidas pode violar regras do jogo. Teste o reconhecimento primeiro sem habilitar os cliques opcionais.
- Não compartilhe dados pessoais, tokens ou credenciais ao publicar no GitHub.

## Tecnologias

Python, Tkinter, OpenCV, NumPy, PyAutoGUI e Pillow.

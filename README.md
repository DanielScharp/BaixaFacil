<div align="center">

<img src="icon.ico" width="72" alt="Ícone do Baixa Fácil" />

# Baixa Fácil

**Um aplicativo de desktop para Windows que baixa vídeos e áudios do YouTube em poucos cliques, sem terminal, sem anúncios e sem login.**

[![Python](https://img.shields.io/badge/Python-3-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Tkinter](https://img.shields.io/badge/Interface-Tkinter-2B5B84?style=for-the-badge&logo=python&logoColor=white)](https://docs.python.org/3/library/tkinter.html)
[![yt-dlp](https://img.shields.io/badge/Motor-yt--dlp-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://github.com/yt-dlp/yt-dlp)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-007808?style=for-the-badge&logo=ffmpeg&logoColor=white)](https://ffmpeg.org/)
[![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)](#-como-rodar-localmente)

</div>

---

## 📌 Sobre o projeto

O [yt-dlp](https://github.com/yt-dlp/yt-dlp) é uma das ferramentas mais poderosas para baixar vídeos da internet, mas é usado pela linha de comando, com dezenas de opções. Para a maioria das pessoas, isso é uma barreira. As alternativas "fáceis" costumam ser sites cheios de anúncios, pop-ups e riscos de segurança.

O **Baixa Fácil** resolve esse problema com uma janela simples, em português, que guia o usuário em quatro passos: **colar o link, escolher o formato, escolher a qualidade e baixar**. Toda a complexidade (seleção de codecs, conversão, tentativas alternativas quando o YouTube recusa uma requisição, atualização do motor de download) acontece por trás, sem que o usuário precise saber que ela existe.

O projeto foi pensado para alguém que **não é da área de tecnologia**: as mensagens são claras, os erros explicam o que fazer em seguida e nada é instalado escondido no computador.

---

## ✨ Funcionalidades

| | Funcionalidade | O que faz |
|---|---|---|
| 📋 | **Colar link com um clique** | Lê o link direto da área de transferência e aceita os formatos mais comuns: `youtube.com/watch`, `youtu.be`, `shorts`, `live`, `embed`, `m.youtube.com` e YouTube Music. |
| 🎬 | **Quatro formatos de saída** | **MP4** compatível com qualquer player, **MKV** com a qualidade máxima disponível, **MP3** convertido e **áudio original**, sem conversão e sem perda. |
| 🔍 | **Consulta de qualidades reais** | O botão *Ver qualidades* pergunta ao YouTube quais resoluções aquele vídeo realmente tem e preenche a lista com elas. |
| 🎯 | **Sem rebaixamento silencioso** | Se o usuário escolheu 1080p, o app não entrega 480p fingindo que está tudo certo. |
| 🧾 | **Relatório do arquivo final** | Ao concluir, mostra a resolução e os codecs que *de fato* foram gravados, lidos do próprio arquivo. |
| 📊 | **Progresso em tempo real** | Barra de progresso, porcentagem, velocidade e título do vídeo, sem travar a janela. |
| ⏹️ | **Cancelar e continuar depois** | O download pode ser interrompido a qualquer momento; na próxima tentativa, ele continua de onde parou. |
| 🔁 | **Três rotas de download** | Se uma forma de acesso falhar, o app tenta automaticamente outras duas, todas públicas e sem cookies ou login. |
| 🔄 | **Atualização com um botão** | Quando o YouTube muda e os downloads param, o botão *Atualizar* baixa a versão mais recente do motor e reinicia o app. |
| 🩺 | **Diagnóstico antes de começar** | Verifica se o motor, o conversor de mídia e a permissão de gravação na pasta estão ok antes de iniciar o download. |
| 📝 | **Detalhes do erro** | Quando algo falha, o botão *Detalhes* mostra o que aconteceu, e um log local guarda o histórico para análise. |
| 📁 | **Pasta lembrada** | A pasta de destino escolhida fica salva para as próximas vezes, e o botão *Abrir pasta* leva direto ao arquivo. |

---

## 🧰 Tecnologias

**Aplicação**
- **[Python 3](https://www.python.org/)**: toda a lógica em um único arquivo, `app.py`, usando apenas a biblioteca padrão.
- **[Tkinter](https://docs.python.org/3/library/tkinter.html) / ttk** com tema personalizado (cores, fontes Segoe UI e botões estilizados) e suporte a telas de alta resolução (DPI).

**Download e mídia**
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)**: motor de download, usado como biblioteca Python.
- **[FFmpeg](https://ffmpeg.org/)**: junta vídeo e áudio, converte para MP3 e inspeciona o arquivo final.
- **[Node.js](https://nodejs.org/)**: usado pelo yt-dlp como ambiente JavaScript, necessário para lidar com as proteções atuais do YouTube.
- **bgutil-ytdlp-pot-provider** e **imageio-ffmpeg**: plugins complementares instalados junto com o motor.

**Integração com o Windows**
- **VBScript** (`Abrir.vbs`) para abrir o app sem a janela preta do terminal.
- `taskkill`, `os.startfile` e processos sem janela (`CREATE_NO_WINDOW`) para uma experiência de aplicativo nativo.

---

## 🧠 Decisões e diferenciais

**A janela nunca trava.**
Analisar e baixar um vídeo pode levar minutos. Por isso, essas tarefas rodam em **processos separados**: o próprio `app.py` é chamado novamente em modo `--worker`, `--analyze` ou `--update`, e se comunica com a interface enviando **eventos em JSON, uma linha por vez**. A interface lê esses eventos por uma fila e se atualiza a cada 150 ms. Isso mantém a janela responsiva e permite que o botão *Cancelar* encerre o download de verdade, junto com qualquer processo filho.

**Atualizar sem nunca quebrar o que funciona.**
O YouTube muda com frequência, e o yt-dlp precisa acompanhar. Em vez de sobrescrever a instalação atual, o botão *Atualizar* instala a nova versão em uma **pasta nova e datada**, testa se ela importa corretamente e só então troca o "ponteiro" (`runtime.json`) para ela. Essa troca é feita gravando um arquivo temporário e renomeando-o, uma operação atômica. Se qualquer etapa falhar, a versão anterior continua intacta e em uso. É o mesmo princípio de "deploy azul/verde", aplicado a um app de desktop.

**Resiliência a falhas do YouTube.**
Cada download percorre três perfis de acesso público (padrão, Safari e Android), já que cada um oferece formatos diferentes dependendo do vídeo e da rede. O usuário vê apenas "Tentando outra rota…", enquanto o motivo técnico de cada falha fica registrado para consulta.

**Honestidade com o usuário.**
O app não promete o que não pode entregar: não troca a resolução escolhida por outra sem avisar, mostra a qualidade real do arquivo salvo e explica que converter para MP3 não melhora o áudio original. Vídeos privados, removidos ou com restrição de idade ou região são tratados como limites do YouTube, não como erros escondidos.

**Validação de entrada pensada para leigos.**
O link colado é normalizado (adiciona `https://` se faltar), validado contra os domínios oficiais, recusado se tiver usuário e senha embutidos e convertido para o formato canônico do vídeo. Links de playlist baixam apenas o vídeo aberto, evitando downloads em massa por engano. Cada problema gera uma mensagem amigável, como *"Esse link não identifica um vídeo. Abra o vídeo e copie o link dele."*

**Logs que ajudam, sem poluir.**
Avisos esperados e inofensivos (como o de um serviço local opcional que não está rodando) são filtrados da tela, mas os erros reais são guardados em `logs/ultimo-download.log` com data e hora.

**Escolha consciente de formatos.**
O modo MP4 prioriza vídeo H.264 e áudio M4A, compatíveis com praticamente qualquer TV, celular ou editor. O modo MKV preserva AV1 ou VP9 quando eles são a melhor opção disponível, para quem quer a qualidade máxima.

---

## 🗂️ Estrutura do projeto

```text
BaixaFacil/
├── app.py            # Aplicação completa: interface, download, análise e atualização
├── Abrir.vbs         # Atalho que abre o app sem janela de terminal
├── icon.ico          # Ícone da janela
├── LEIA-ME.txt       # Guia rápido para o usuário final
├── bin/
│   └── ffmpeg.exe    # Conversor de mídia usado pelo app
│
│   # Gerados durante o uso (fora do Git):
├── runtime-*/        # Versões do motor instaladas pelo botão "Atualizar"
├── runtime.json      # Indica qual versão do motor está ativa
├── settings.json     # Última pasta de destino escolhida
└── logs/             # Diagnóstico dos downloads
```

Dentro do `app.py`, as responsabilidades estão divididas em funções bem definidas:

| Função | Papel |
|---|---|
| `normalize_url` | Valida e padroniza o link do YouTube |
| `download_options` | Monta a configuração do yt-dlp para cada formato e qualidade |
| `analyze` | Lista as resoluções disponíveis antes do download |
| `worker` | Executa o download, tentando as três rotas públicas |
| `media_details` | Lê o arquivo final para informar a qualidade real |
| `healthcheck` | Confere motor, FFmpeg, Node.js e permissão de escrita |
| `update_runtime` / `activate_runtime` | Atualização segura do motor de download |
| `main` | Interface gráfica e orquestração dos eventos |

---

## 🚀 Como rodar localmente

**Pré-requisitos:** Windows, [Python 3](https://www.python.org/downloads/) (o projeto foi desenvolvido com Python 3.14) e [Node.js](https://nodejs.org/).

```bash
# 1. Clone o repositório
git clone https://github.com/DanielScharp/BaixaFacil.git
cd BaixaFacil

# 2. Abra o aplicativo
python app.py
```

Na primeira execução, clique em **Atualizar**: o app instala o motor de download na própria pasta do projeto e reinicia sozinho. Depois disso, é só colar um link e baixar.

Se preferir instalar o motor manualmente:

```bash
python -m pip install --target runtime "yt-dlp[default]" imageio-ffmpeg bgutil-ytdlp-pot-provider
```

### Abrindo sem o terminal

O arquivo `Abrir.vbs` abre o app com `pythonw.exe`, sem a janela preta do terminal, e pode ser usado como atalho na área de trabalho. Ele aponta para `C:\Python314\pythonw.exe`; se o seu Python estiver em outro lugar, ajuste esse caminho no arquivo.

### Como usar

1. Copie o link de um vídeo do YouTube e clique em **Colar link**.
2. Escolha o formato: **MP4**, **Máxima (MKV)**, **MP3** ou **Original**.
3. Clique em **Ver qualidades** e escolha a resolução desejada.
4. Clique em **Baixar agora**. Ao terminar, use **Abrir pasta**.

---

## ⚖️ Uso responsável

O Baixa Fácil acessa apenas conteúdo público, sem login ou cookies. Use-o para vídeos que você tem direito de baixar, como os seus próprios, conteúdo livre ou material autorizado pelo autor, respeitando os termos do YouTube e os direitos autorais.

O motor de download é o [yt-dlp](https://github.com/yt-dlp/yt-dlp) e a conversão de mídia é feita pelo [FFmpeg](https://ffmpeg.org/), cada um com sua própria licença.

---

## 🛣️ Próximos passos

- [ ] Gerar um instalador ou executável único, sem exigir Python instalado
- [ ] Fila com vários downloads
- [ ] Suporte opcional a playlists
- [ ] Versões para macOS e Linux

---

## 📫 Contato

<div align="center">

Gostou do projeto ou quer conversar sobre uma oportunidade? Vou adorar ouvir você.

[![LinkedIn](https://img.shields.io/badge/LinkedIn-daniel--scharp-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/daniel-scharp/)
[![E-mail](https://img.shields.io/badge/E--mail-contato@danielscharp.com.br-EA4335?style=for-the-badge&logo=gmail&logoColor=white)](mailto:contato@danielscharp.com.br)
[![GitHub](https://img.shields.io/badge/GitHub-DanielScharp-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/DanielScharp)

Feito com dedicação por **Daniel Scharp**

</div>

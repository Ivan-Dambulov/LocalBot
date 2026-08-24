# ui/main_window.py
import threading
from pathlib import Path
import customtkinter as ctk
from tkinter import messagebox

from ui.settings import load_preferences, save_preferences
from ui.widgets.chat_view import ChatView


ctk.set_appearance_mode("System")          # "System", "Dark", "Light"
ctk.set_default_color_theme("blue")


class MainWindow(ctk.CTk):
    def __init__(
        self,
        engine,
        model_path: str = "",
        gpu_layers: int = 0,
        context_size: int = 8192,
        models_dir: str = "models",
    ):
        super().__init__()

        self.engine = engine
        self.model_path = model_path
        self.gpu_layers = gpu_layers
        self.context_size = context_size
        self.models_dir = models_dir

        self.title("Local AI Assistant")
        self.geometry("1150x720")
        self.minsize(900, 600)

        try:
            self.attributes("-alpha", 0.98)
        except Exception:
            pass

        self._build_ui()
        self._refresh_conversations()
        self._update_status()

    def _build_ui(self):
        # ========== Top bar ==========
        top = ctk.CTkFrame(self, height=52, corner_radius=0, fg_color=("gray95", "gray15"))
        top.pack(fill="x")
        top.pack_propagate(False)

        ctk.CTkButton(
            top, text="New Chat", width=100, height=32,
            corner_radius=10, command=self._new_chat
        ).pack(side="left", padx=(16, 8), pady=10)

        ctk.CTkButton(
            top, text="Clear", width=80, height=32,
            corner_radius=10, command=self._clear_menu
        ).pack(side="left", padx=4, pady=10)

        ctk.CTkButton(
            top, text="Model Manager", width=130, height=32,
            corner_radius=10, command=self._open_model_manager
        ).pack(side="left", padx=8, pady=10)

        # Appearance switch
        self.appearance_switch = ctk.CTkSwitch(
            top, text="Dark", command=self._toggle_appearance, width=60
        )
        self.appearance_switch.pack(side="right", padx=20)

        self.status_label = ctk.CTkLabel(top, text="Ready", font=ctk.CTkFont(size=13))
        self.status_label.pack(side="right", padx=12)

        # ========== Main content ==========
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        # Left sidebar – conversations
        sidebar = ctk.CTkFrame(main, width=240, corner_radius=16)
        sidebar.pack(side="left", fill="y", padx=(0, 12))
        sidebar.pack_propagate(False)

        ctk.CTkLabel(
            sidebar, text="Conversations",
            font=ctk.CTkFont(size=15, weight="bold")
        ).pack(anchor="w", padx=16, pady=(16, 8))

        self.conv_list = ctk.CTkScrollableFrame(sidebar, fg_color="transparent")
        self.conv_list.pack(fill="both", expand=True, padx=8, pady=(0, 12))

        # Right – chat area
        chat_frame = ctk.CTkFrame(main, corner_radius=16)
        chat_frame.pack(side="left", fill="both", expand=True)

        self.chat_view = ChatView(chat_frame, corner_radius=12)
        self.chat_view.pack(fill="both", expand=True, padx=12, pady=(12, 8))

        # Input area
        input_frame = ctk.CTkFrame(chat_frame, fg_color="transparent")
        input_frame.pack(fill="x", padx=12, pady=(0, 12))

        self.input = ctk.CTkTextbox(
            input_frame, height=70, font=ctk.CTkFont(size=14), corner_radius=12
        )
        self.input.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.input.bind("<Control-Return>", lambda e: self._send())

        ctk.CTkButton(
            input_frame, text="Send", width=90, height=40,
            corner_radius=12, font=ctk.CTkFont(size=14, weight="bold"),
            command=self._send
        ).pack(side="right")

    def _toggle_appearance(self):
        current = ctk.get_appearance_mode()
        new_mode = "Light" if current == "Dark" else "Dark"
        ctk.set_appearance_mode(new_mode)
        self.appearance_switch.configure(text=new_mode)

    def _update_status(self):
        name = Path(self.model_path).name if self.model_path else "No model"
        self.status_label.configure(
            text=f"{name}  •  GPU: {self.gpu_layers}  •  ctx {self.context_size}"
        )

    def _append(self, role: str, text: str):
        text = text.strip()
        if role == "user":
            self.chat_view.add_user_message(text)
        elif role == "assistant":
            self.chat_view.add_assistant_message(text)
        else:
            self.chat_view.add_system_message(text)

    def _new_chat(self):
        self.engine.new_conversation()
        self.chat_view.clear()
        self._refresh_conversations()

    def _refresh_conversations(self):
        for widget in self.conv_list.winfo_children():
            widget.destroy()

        self._conv_ids = []
        for conv in self.engine.get_conversations():
            btn = ctk.CTkButton(
                self.conv_list,
                text=conv["title"][:40],
                anchor="w",
                height=36,
                corner_radius=10,
                fg_color="transparent",
                hover_color=("gray85", "gray25"),
                command=lambda c=conv: self._load_conversation(c["id"]),
            )
            btn.pack(fill="x", pady=2)
            self._conv_ids.append(conv["id"])

    def _load_conversation(self, cid: int):
        messages = self.engine.load_conversation(cid)
        self.chat_view.clear()
        for m in messages:
            self._append(m["role"], m["content"])

    def _send(self):
        text = self.input.get("1.0", "end").strip()
        if not text:
            return
        self.input.delete("1.0", "end")
        self._append("user", text)

        self._stream_buffer = ""
        self.chat_view.show_typing_indicator()

        def worker():
            try:
                for token in self.engine.send(text):
                    self.after(0, lambda t=token: self._stream_token(t))
                self.after(0, self._finish_stream)
                self.after(0, self._refresh_conversations)
            except Exception as e:
                self.after(0, lambda: self._stream_error(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _stream_token(self, token: str):
        # First token: the typing indicator morphs into the live bubble.
        self._stream_buffer += token
        self.chat_view.update_streaming_message(self._stream_buffer)

    def _finish_stream(self):
        self.chat_view.finalize_streaming_message()
        self._stream_buffer = ""

    def _stream_error(self, message: str):
        self.chat_view.hide_typing_indicator()
        self._append("system", f"Error: {message}")
        self._stream_buffer = ""

    def _open_model_manager(self):
        from ui.model_manager import ModelManager
        ModelManager(
            self,
            current_model_path=self.model_path,
            models_dir=self.models_dir,
            on_apply=self._on_model_applied,
        )

    def _on_model_applied(self, new_path: str):
        try:
            from llm.llama_runtime import LlamaRuntime
            llm = LlamaRuntime(
                model_path=new_path,
                context_size=self.context_size,
                gpu_layers=self.gpu_layers,
            )
            self.engine.set_llm(llm)
            self.model_path = new_path
            self._update_status()
            messagebox.showinfo("Model loaded", f"Now using:\n{Path(new_path).name}")
        except Exception as e:
            messagebox.showerror("Failed to load model", str(e))

    def _clear_menu(self):
        if messagebox.askyesno("Clear", "Delete all conversations?"):
            self.engine.clear_conversations("all")
            self._new_chat()
            self._refresh_conversations()
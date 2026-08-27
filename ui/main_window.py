# ui/main_window.py
import threading
from pathlib import Path
import customtkinter as ctk
from tkinter import messagebox

from ui.settings import load_preferences, save_preferences
from ui.widgets.chat_view import ChatView


ctk.set_appearance_mode("Light")
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
        self._current_conv_id = None
        self._all_conversations = []
        self._stream_buffer = ""

        self.title("LocalBot")
        self.geometry("1200x800")
        self.minsize(960, 640)
        self.configure(fg_color="#FAFAFA")

        try:
            self.attributes("-alpha", 0.99)
        except Exception:
            pass

        self._build_ui()
        self._refresh_conversations()
        self._update_status()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True)

        # ==================== LEFT SIDEBAR ====================
        sidebar = ctk.CTkFrame(
            main, width=270, corner_radius=0, fg_color="#F5F5F7"
        )
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        ctk.CTkLabel(
            sidebar,
            text="Chats",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#1C1C1E",
        ).pack(anchor="w", padx=18, pady=(22, 10))

        self.search_entry = ctk.CTkEntry(
            sidebar,
            placeholder_text="Search conversations…",
            height=34,
            corner_radius=10,
            fg_color="#FFFFFF",
            border_width=1,
            border_color="#E5E5EA",
            text_color="#1C1C1E",
            placeholder_text_color="#AEAEB2",
            font=ctk.CTkFont(size=13),
        )
        self.search_entry.pack(fill="x", padx=14, pady=(0, 10))
        self.search_entry.bind("<KeyRelease>", lambda e: self._filter_conversations())

        self.conv_list = ctk.CTkScrollableFrame(
            sidebar, fg_color="transparent", corner_radius=0
        )
        self.conv_list.pack(fill="both", expand=True, padx=8, pady=(0, 12))

        # ==================== RIGHT SIDE ====================
        right = ctk.CTkFrame(main, fg_color="#FAFAFA", corner_radius=0)
        right.pack(side="left", fill="both", expand=True)

        # --- Header ---
        header = ctk.CTkFrame(
            right, height=60, corner_radius=0, fg_color="#FFFFFF"
        )
        header.pack(fill="x")
        header.pack_propagate(False)

        left_header = ctk.CTkFrame(header, fg_color="transparent")
        left_header.pack(side="left", padx=20, pady=10)

        ctk.CTkLabel(
            left_header,
            text="LocalBot",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color="#1C1C1E",
        ).pack(anchor="w")

        status_row = ctk.CTkFrame(left_header, fg_color="transparent")
        status_row.pack(anchor="w")

        ctk.CTkLabel(
            status_row,
            text="●",
            text_color="#34C759",
            font=ctk.CTkFont(size=11),
        ).pack(side="left", padx=(0, 4))

        self.connection_label = ctk.CTkLabel(
            status_row,
            text="Local Server Connected",
            font=ctk.CTkFont(size=11),
            text_color="#8E8E93",
        )
        self.connection_label.pack(side="left")

        right_header = ctk.CTkFrame(header, fg_color="transparent")
        right_header.pack(side="right", padx=16, pady=12)

        model_name = Path(self.model_path).name if self.model_path else "No model"
        if len(model_name) > 22:
            model_name = model_name[:19] + "…"
        self.model_var = ctk.StringVar(value=model_name)

        self.model_menu = ctk.CTkOptionMenu(
            right_header,
            variable=self.model_var,
            values=[model_name],
            width=150,
            height=30,
            corner_radius=9,
            fg_color="#F2F2F7",
            button_color="#E5E5EA",
            button_hover_color="#D1D1D6",
            text_color="#1C1C1E",
            dropdown_fg_color="#FFFFFF",
            dropdown_text_color="#1C1C1E",
            font=ctk.CTkFont(size=12),
        )
        self.model_menu.pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            right_header,
            text="⚙  Settings",
            width=96,
            height=30,
            corner_radius=9,
            fg_color="#FFFFFF",
            border_width=1,
            border_color="#E5E5EA",
            text_color="#1C1C1E",
            hover_color="#F2F2F7",
            font=ctk.CTkFont(size=12),
            command=self._open_model_manager,
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            right_header,
            text="🗑  Clear All",
            width=96,
            height=30,
            corner_radius=9,
            fg_color="#FFFFFF",
            border_width=1,
            border_color="#E5E5EA",
            text_color="#1C1C1E",
            hover_color="#F2F2F7",
            font=ctk.CTkFont(size=12),
            command=self._clear_menu,
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            right_header,
            text="+ New Chat",
            width=104,
            height=30,
            corner_radius=9,
            fg_color="#0A84FF",
            hover_color="#0071E3",
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._new_chat,
        ).pack(side="left", padx=(6, 0))

        # Separator under header
        ctk.CTkFrame(right, height=1, fg_color="#E5E5EA").pack(fill="x")

        # --- Chat view ---
        self.chat_view = ChatView(right, corner_radius=0)
        self.chat_view.pack(fill="both", expand=True, padx=28, pady=(14, 0))

        # --- Input bar ---
        input_bar = ctk.CTkFrame(right, fg_color="transparent", height=70)
        input_bar.pack(fill="x", padx=28, pady=(10, 18))

        input_inner = ctk.CTkFrame(
            input_bar,
            height=48,
            corner_radius=24,
            fg_color="#FFFFFF",
            border_width=1,
            border_color="#E5E5EA",
        )
        input_inner.pack(fill="x")
        input_inner.pack_propagate(False)

        ctk.CTkButton(
            input_inner,
            text="📎",
            width=34,
            height=34,
            corner_radius=17,
            fg_color="transparent",
            hover_color="#F2F2F7",
            text_color="#8E8E93",
            command=lambda: None,
        ).pack(side="left", padx=(6, 0))

        self.input = ctk.CTkEntry(
            input_inner,
            placeholder_text="Type a message…",
            height=40,
            border_width=0,
            fg_color="transparent",
            text_color="#1C1C1E",
            placeholder_text_color="#AEAEB2",
            font=ctk.CTkFont(size=14),
        )
        self.input.pack(side="left", fill="x", expand=True, padx=4)
        self.input.bind("<Return>", lambda e: self._send())

        ctk.CTkButton(
            input_inner,
            text="↑",
            width=36,
            height=36,
            corner_radius=18,
            fg_color="#0A84FF",
            hover_color="#0071E3",
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=16, weight="bold"),
            command=self._send,
        ).pack(side="right", padx=6)

    # ------------------------------------------------------------------ Status
    def _update_status(self):
        name = Path(self.model_path).name if self.model_path else "No model"
        if len(name) > 22:
            name = name[:19] + "…"
        self.model_var.set(name)
        try:
            self.model_menu.configure(values=[name])
        except Exception:
            pass

        if self.model_path:
            self.connection_label.configure(
                text="Local Server Connected", text_color="#8E8E93"
            )
        else:
            self.connection_label.configure(
                text="No model loaded", text_color="#FF9500"
            )

    # ------------------------------------------------------------------ Conversations
    def _refresh_conversations(self):
        self._all_conversations = list(self.engine.get_conversations())
        self._render_conversation_list(self._all_conversations)

    def _filter_conversations(self):
        query = self.search_entry.get().strip().lower()
        if not query:
            self._render_conversation_list(self._all_conversations)
            return
        filtered = [
            c for c in self._all_conversations
            if query in (c.get("title") or "").lower()
        ]
        self._render_conversation_list(filtered)

    def _render_conversation_list(self, conversations):
        for widget in self.conv_list.winfo_children():
            widget.destroy()

        self._conv_ids = []
        for conv in conversations:
            is_active = conv["id"] == self._current_conv_id

            card = ctk.CTkFrame(
                self.conv_list,
                height=56,
                corner_radius=12,
                fg_color="#0A84FF" if is_active else "transparent",
            )
            card.pack(fill="x", pady=2, padx=4)
            card.pack_propagate(False)

            title_color = "#FFFFFF" if is_active else "#1C1C1E"
            sub_color = "#E0E0E0" if is_active else "#8E8E93"

            title = (conv.get("title") or "New Chat")[:28]
            ctk.CTkLabel(
                card,
                text=title,
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=title_color,
                anchor="w",
                height=18,
            ).place(x=12, y=8)

            preview = (conv.get("title") or "")[:38]
            ctk.CTkLabel(
                card,
                text=preview,
                font=ctk.CTkFont(size=11),
                text_color=sub_color,
                anchor="w",
                height=16,
            ).place(x=12, y=30)

            def _on_click(event, cid=conv["id"]):
                self._load_conversation(cid)

            card.bind("<Button-1>", _on_click)
            for child in card.winfo_children():
                child.bind("<Button-1>", _on_click)

            self._conv_ids.append(conv["id"])

    def _load_conversation(self, cid: int):
        self._current_conv_id = cid
        messages = self.engine.load_conversation(cid)
        self.chat_view.clear()
        for m in messages:
            self._append(m["role"], m["content"])
        self._refresh_conversations()

    def _new_chat(self):
        self.engine.new_conversation()
        self._current_conv_id = None
        self.chat_view.clear()
        self._refresh_conversations()

    # ------------------------------------------------------------------ Messaging
    def _append(self, role: str, text: str):
        text = text.strip()
        if not text:
            return
        if role == "user":
            self.chat_view.add_user_message(text)
        elif role == "assistant":
            self.chat_view.add_assistant_message(text)
        else:
            self.chat_view.add_system_message(text)

    def _send(self):
        text = self.input.get().strip()
        if not text:
            return
        self.input.delete(0, "end")
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
        self._stream_buffer += token
        self.chat_view.update_streaming_message(self._stream_buffer)

    def _finish_stream(self):
        self.chat_view.finalize_streaming_message()
        self._stream_buffer = ""

    def _stream_error(self, message: str):
        self.chat_view.hide_typing_indicator()
        self._append("system", f"Error: {message}")
        self._stream_buffer = ""

    # ------------------------------------------------------------------ Model Manager
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
            messagebox.showinfo(
                "Model loaded", f"Now using:\n{Path(new_path).name}"
            )
        except Exception as e:
            messagebox.showerror("Failed to load model", str(e))

    def _clear_menu(self):
        if messagebox.askyesno("Clear", "Delete all conversations?"):
            self.engine.clear_conversations("all")
            self._new_chat()
            self._refresh_conversations()
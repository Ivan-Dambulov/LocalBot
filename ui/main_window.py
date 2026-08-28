# ui/main_window.py
import threading
from pathlib import Path

import customtkinter as ctk
from tkinter import messagebox, filedialog

from ui.settings import load_preferences, save_preferences
from ui.theme import colors, paint_scrollable
from ui.widgets.chat_view import ChatView


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
        self._generating = False

        self.preferences = load_preferences()
        self.web_search_enabled = bool(
            self.preferences.get("web_search_enabled", False)
        )
        self.engine.set_web_search_enabled(self.web_search_enabled)

        # Strict Light / Dark only (no System mixing with hard-coded colors)
        appearance = self.preferences.get("appearance_mode", "Dark")
        if appearance not in ("Light", "Dark"):
            appearance = "Dark"
        ctk.set_appearance_mode(appearance)
        ctk.set_default_color_theme("blue")

        self.title("LocalBot")
        self.geometry("1200x800")
        self.minsize(960, 640)

        self._build_ui()
        self._apply_theme()
        self._refresh_conversations()
        self._update_status()
        self._set_generating(False)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        self.main = ctk.CTkFrame(self, fg_color="transparent")
        self.main.pack(fill="both", expand=True)

        # ==================== LEFT SIDEBAR ====================
        self.sidebar = ctk.CTkFrame(self.main, width=280, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        self.sidebar_title = ctk.CTkLabel(
            self.sidebar,
            text="Chats",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self.sidebar_title.pack(anchor="w", padx=18, pady=(22, 10))

        self.search_entry = ctk.CTkEntry(
            self.sidebar,
            placeholder_text="Search conversations…",
            height=34,
            corner_radius=10,
            border_width=1,
            font=ctk.CTkFont(size=13),
        )
        self.search_entry.pack(fill="x", padx=14, pady=(0, 10))
        self.search_entry.bind(
            "<KeyRelease>",
            lambda e: self._filter_conversations(),
        )

        self.conv_list = ctk.CTkScrollableFrame(
            self.sidebar,
            fg_color="transparent",
            corner_radius=0,
        )
        self.conv_list.pack(fill="both", expand=True, padx=8, pady=(0, 12))

        # ==================== RIGHT SIDE ====================
        self.right = ctk.CTkFrame(self.main, corner_radius=0)
        self.right.pack(side="left", fill="both", expand=True)

        self.header = ctk.CTkFrame(self.right, height=60, corner_radius=0)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)

        left_header = ctk.CTkFrame(self.header, fg_color="transparent")
        left_header.pack(side="left", padx=20, pady=10)

        self.app_title = ctk.CTkLabel(
            left_header,
            text="LocalBot",
            font=ctk.CTkFont(size=17, weight="bold"),
        )
        self.app_title.pack(anchor="w")

        status_row = ctk.CTkFrame(left_header, fg_color="transparent")
        status_row.pack(anchor="w")

        self.status_dot = ctk.CTkLabel(
            status_row,
            text="●",
            font=ctk.CTkFont(size=11),
        )
        self.status_dot.pack(side="left", padx=(0, 4))

        self.connection_label = ctk.CTkLabel(
            status_row,
            text="Local Server Connected",
            font=ctk.CTkFont(size=11),
        )
        self.connection_label.pack(side="left")

        right_header = ctk.CTkFrame(self.header, fg_color="transparent")
        right_header.pack(side="right", padx=16, pady=12)

        model_name = (
            Path(self.model_path).name if self.model_path else "No model"
        )
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
            font=ctk.CTkFont(size=12),
        )
        self.model_menu.pack(side="left", padx=(0, 6))

        self.theme_btn = ctk.CTkButton(
            right_header,
            text="Dark",
            width=72,
            height=30,
            corner_radius=9,
            border_width=1,
            font=ctk.CTkFont(size=12),
            command=self._toggle_theme,
        )
        self.theme_btn.pack(side="left", padx=3)

        self.settings_btn = ctk.CTkButton(
            right_header,
            text="⚙  Settings",
            width=96,
            height=30,
            corner_radius=9,
            border_width=1,
            font=ctk.CTkFont(size=12),
            command=self._open_model_manager,
        )
        self.settings_btn.pack(side="left", padx=3)

        self.clear_btn = ctk.CTkButton(
            right_header,
            text="🗑  Clear",
            width=80,
            height=30,
            corner_radius=9,
            border_width=1,
            font=ctk.CTkFont(size=12),
            command=self._clear_menu,
        )
        self.clear_btn.pack(side="left", padx=3)

        self.new_chat_btn = ctk.CTkButton(
            right_header,
            text="+ New Chat",
            width=104,
            height=30,
            corner_radius=9,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._new_chat,
        )
        self.new_chat_btn.pack(side="left", padx=(6, 0))

        self.header_sep = ctk.CTkFrame(self.right, height=1)
        self.header_sep.pack(fill="x")

        self.chat_view = ChatView(self.right, corner_radius=0)
        self.chat_view.pack(fill="both", expand=True, padx=28, pady=(14, 0))

        self.attachment_frame = ctk.CTkFrame(self.right, fg_color="transparent")
        self.attachment_frame.pack(fill="x", padx=28, pady=(4, 0))

        input_bar = ctk.CTkFrame(self.right, fg_color="transparent", height=70)
        input_bar.pack(fill="x", padx=28, pady=(10, 18))

        self.input_inner = ctk.CTkFrame(
            input_bar,
            height=48,
            corner_radius=24,
            border_width=1,
        )
        self.input_inner.pack(fill="x")
        self.input_inner.pack_propagate(False)

        self.attach_btn = ctk.CTkButton(
            self.input_inner,
            text="📎",
            width=34,
            height=34,
            corner_radius=17,
            font=ctk.CTkFont(size=15),
            command=self._attach_files,
        )
        self.attach_btn.pack(side="left", padx=(6, 4))

        self.web_search_button = ctk.CTkButton(
            self.input_inner,
            text="🌐",
            width=34,
            height=34,
            corner_radius=17,
            font=ctk.CTkFont(size=15),
            command=self._toggle_web_search,
        )
        self.web_search_button.pack(side="left", padx=(0, 0))

        self.input = ctk.CTkEntry(
            self.input_inner,
            placeholder_text="Type a message…",
            height=40,
            border_width=0,
            font=ctk.CTkFont(size=14),
        )

        self.input.pack(side="left", fill="x", expand=True, padx=4)
        self.input.bind("<Return>", lambda e: self._send())

        self.send_btn = ctk.CTkButton(
            self.input_inner,
            text="↑",
            width=36,
            height=36,
            corner_radius=18,
            font=ctk.CTkFont(size=16, weight="bold"),
            command=self._send,
        )
        self.send_btn.pack(side="right", padx=6)

        self.stop_btn = ctk.CTkButton(
            self.input_inner,
            text="■",
            width=36,
            height=36,
            corner_radius=18,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._stop_generation,
        )
        # stop_btn is packed only while generating

    # ------------------------------------------------------------------ Theme
    def _apply_theme(self):
        """Paint every major region the same mode — no mixed light/dark."""
        c = colors()

        self.configure(fg_color=c["bg"])
        self.main.configure(fg_color=c["bg"])
        self.sidebar.configure(fg_color=c["sidebar"])
        self.right.configure(fg_color=c["bg"])
        self.header.configure(fg_color=c["header"])
        self.header_sep.configure(fg_color=c["border"])

        # Sidebar list + internal canvas must match sidebar
        paint_scrollable(self.conv_list, c["sidebar"])

        self.sidebar_title.configure(text_color=c["text"])
        self.search_entry.configure(
            fg_color=c["surface"],
            border_color=c["border"],
            text_color=c["text"],
            placeholder_text_color=c["text_secondary"],
        )

        self.app_title.configure(text_color=c["text"])
        self.connection_label.configure(text_color=c["text_secondary"])

        self.chat_view.apply_theme()
        self.attachment_frame.configure(fg_color=c["bg"])

        for btn in (self.theme_btn, self.settings_btn, self.clear_btn):
            btn.configure(
                fg_color=c["surface_alt"],
                border_width=1,
                border_color=c["border"],
                text_color=c["text"],
                hover_color=c["surface"],
            )

        self.new_chat_btn.configure(
            fg_color=c["accent"],
            hover_color=c["accent_hover"],
            text_color="#FFFFFF",
            border_width=0,
        )
        self.model_menu.configure(
            fg_color=c["surface_alt"],
            button_color=c["border"],
            button_hover_color=c["surface"],
            text_color=c["text"],
            dropdown_fg_color=c["surface"],
            dropdown_text_color=c["text"],
            dropdown_hover_color=c["surface_alt"],
        )

        self.input_inner.configure(
            fg_color=c["input_bg"],
            border_color=c["border"],
        )
        self.input.configure(
            text_color=c["text"],
            placeholder_text_color=c["text_secondary"],
            fg_color=c["input_bg"],
        )
        self.attach_btn.configure(
            fg_color=c["surface_alt"],
            hover_color=c["border"],
            text_color=c["text"],
        )

        self._update_web_search_button()
        self._update_theme_button_label()
        self._set_generating(self._generating)
        self._refresh_conversations()
        self._update_status()
        self._refresh_attachment_view()
        self._reload_visible_chat()


    def _reload_visible_chat(self):
        """Rebuild on-screen messages so bubbles match the current theme."""
        if self._generating:
            return

        self.chat_view.clear()

        conv_id = self._current_conv_id or getattr(
            self.engine, "conversation_id", None
        )
        if not conv_id:
            return

        try:
            messages = self.engine.store.load_messages(conv_id)
        except Exception:
            return

        for m in messages:
            self._append(m["role"], m["content"])

    def _update_theme_button_label(self):
        # Show the mode you are currently in
        if ctk.get_appearance_mode() == "Dark":
            self.theme_btn.configure(text="Dark")
        else:
            self.theme_btn.configure(text="Light")

    def _toggle_theme(self):
        if ctk.get_appearance_mode() == "Dark":
            new_mode = "Light"
        else:
            new_mode = "Dark"

        ctk.set_appearance_mode(new_mode)
        self.preferences["appearance_mode"] = new_mode
        save_preferences(self.preferences)

        # Apply shell colors, then rebuild bubbles after CTk updates mode
        self.after(20, self._apply_theme)

    def _reload_visible_chat(self):
        """
        Recreate every on-screen bubble from the DB so Light/Dark
        always matches the current theme (including old conversations).
        """
        if self._generating:
            return

        conv_id = self._current_conv_id
        if conv_id is None:
            conv_id = getattr(self.engine, "conversation_id", None)

        if not conv_id:
            self.chat_view.clear()
            self.chat_view.apply_theme()
            return

        try:
            messages = self.engine.store.load_messages(conv_id)
        except Exception:
            self.chat_view.clear()
            self.chat_view.apply_theme()
            return

        self.chat_view.rebuild_messages(messages)

    # ------------------------------------------------------------------ Web search / attach
    def _toggle_web_search(self):
        self.web_search_enabled = not self.web_search_enabled
        self.engine.set_web_search_enabled(self.web_search_enabled)
        self.preferences["web_search_enabled"] = self.web_search_enabled
        save_preferences(self.preferences)
        self._update_web_search_button()

    def _attach_files(self):
        if self._generating:
            return
        files = filedialog.askopenfilenames(
            title="Select files",
            filetypes=[
                ("Supported files", "*.txt *.md *.pdf *.docx *.xlsx *.xls"),
                ("All files", "*.*"),
            ],
        )
        if not files:
            return
        self.engine.add_attachments(files)
        self._refresh_attachment_view()

    def _update_web_search_button(self):
        c = colors()
        if self.web_search_enabled:
            self.web_search_button.configure(
                fg_color=c["accent"],
                hover_color=c["accent_hover"],
                text_color="#FFFFFF",
            )
        else:
            self.web_search_button.configure(
                fg_color=c["surface_alt"],
                hover_color=c["border"],
                text_color=c["text"],
            )

    # ------------------------------------------------------------------ Status / generating
    def _set_generating(self, active: bool):
        self._generating = active
        c = colors()
        if active:
            self.send_btn.pack_forget()
            self.stop_btn.configure(
                fg_color=c["danger"],
                hover_color=c["danger_hover"],
                text_color="#FFFFFF",
            )
            self.stop_btn.pack(side="right", padx=6)
            self.input.configure(state="disabled")
        else:
            self.stop_btn.pack_forget()
            self.send_btn.configure(
                fg_color=c["accent"],
                hover_color=c["accent_hover"],
                text_color="#FFFFFF",
            )
            self.send_btn.pack(side="right", padx=6)
            self.input.configure(state="normal")

    def _update_status(self):
        c = colors()
        name = Path(self.model_path).name if self.model_path else "No model"
        if len(name) > 22:
            name = name[:19] + "…"
        self.model_var.set(name)
        try:
            self.model_menu.configure(values=[name])
        except Exception:
            pass
        if self.model_path:
            self.status_dot.configure(text_color=c["success"])
            self.connection_label.configure(
                text="Local Server Connected",
                text_color=c["text_secondary"],
            )
        else:
            self.status_dot.configure(text_color=c["warning"])
            self.connection_label.configure(
                text="No model loaded",
                text_color=c["warning"],
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
            item
            for item in self._all_conversations
            if query in (item.get("title") or "").lower()
        ]
        self._render_conversation_list(filtered)

    def _render_conversation_list(self, conversations):
        c = colors()
        for widget in self.conv_list.winfo_children():
            widget.destroy()
        self._conv_ids = []

        # Keep list background in sync with sidebar
        paint_scrollable(self.conv_list, c["sidebar"])

        for conv in conversations:
            is_active = conv["id"] == self._current_conv_id
            card = ctk.CTkFrame(
                self.conv_list,
                height=56,
                corner_radius=12,
                # Solid colors only — never "transparent" (causes mixed strips)
                fg_color=c["accent"] if is_active else c["surface_alt"],
            )
            card.pack(fill="x", pady=2, padx=4)
            card.pack_propagate(False)

            title_color = "#FFFFFF" if is_active else c["text"]
            sub_color = "#E0E0E0" if is_active else c["text_secondary"]
            title = (conv.get("title") or "New Chat")[:28]

            ctk.CTkLabel(
                card,
                text=title,
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=title_color,
                anchor="w",
                height=18,
            ).place(x=12, y=8)
            ctk.CTkLabel(
                card,
                text=(conv.get("title") or "")[:38],
                font=ctk.CTkFont(size=11),
                text_color=sub_color,
                anchor="w",
                height=16,
            ).place(x=12, y=30)

            def _on_click(event, cid=conv["id"]):
                if not self._generating:
                    self._load_conversation(cid)

            card.bind("<Button-1>", _on_click)
            for child in card.winfo_children():
                child.bind("<Button-1>", _on_click)
            self._conv_ids.append(conv["id"])

    def _load_conversation(self, cid: int):
        if self._generating:
            return
        self._current_conv_id = cid
        try:
            messages = self.engine.load_conversation(cid)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return
        self.chat_view.rebuild_messages(messages)
        self._refresh_conversations()

    def _new_chat(self):
        if self._generating:
            return
        self.engine.new_conversation()
        self._current_conv_id = None
        self.chat_view.clear()
        self._refresh_conversations()
        self._refresh_attachment_view()

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
        if self._generating:
            return
        text = self.input.get().strip()
        if not text:
            return
        self.input.delete(0, "end")
        self._append("user", text)
        self._stream_buffer = ""
        self.chat_view.show_typing_indicator()
        self._set_generating(True)

        def worker():
            try:
                for token in self.engine.send(
                    text,
                    web_search=self.web_search_enabled,
                ):
                    self.after(0, self._stream_token, token)
                self.after(0, self._finish_stream)
            except Exception as exc:
                self.after(0, self._stream_error, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _stop_generation(self):
        if not self._generating:
            return
        self.engine.request_stop()

    def _stream_token(self, token: str):
        self._stream_buffer += token
        self.chat_view.update_streaming_message(self._stream_buffer)

    def _finish_stream(self):
        self.chat_view.finalize_streaming_message()
        self._stream_buffer = ""
        self._current_conv_id = self.engine.conversation_id
        self._set_generating(False)
        self._refresh_conversations()
        self._refresh_attachment_view()

    def _stream_error(self, message: str):
        self.chat_view.hide_typing_indicator()
        self._append("system", f"Error: {message}")
        self._stream_buffer = ""
        self._set_generating(False)
        self._refresh_attachment_view()

    # ------------------------------------------------------------------ Model manager
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
                "Model loaded",
                f"Now using:\n{Path(new_path).name}",
            )
        except Exception as e:
            messagebox.showerror("Failed to load model", str(e))

    def _clear_menu(self):
        if self._generating:
            return
        if messagebox.askyesno("Clear", "Delete all conversations?"):
            self.engine.clear_conversations("all")
            self._new_chat()
            self._refresh_conversations()

    def _refresh_attachment_view(self):
        c = colors()
        for widget in self.attachment_frame.winfo_children():
            widget.destroy()
        for filename in self.engine.get_attachment_names():
            chip = ctk.CTkLabel(
                self.attachment_frame,
                text=f"📄 {filename}",
                fg_color=c["chip"],
                text_color=c["text"],
                corner_radius=8,
                padx=8,
                pady=4,
            )
            chip.pack(side="left", padx=4, pady=4)
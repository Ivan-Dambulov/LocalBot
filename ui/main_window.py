from PySide6.QtCore import (
    Qt,
    QThread,
    Signal,
)
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QMessageBox,
    QFrame,
    QSizePolicy,
    QMenu,
)

from assistant.engine import AssistantEngine
from ui.settings_dialog import SettingsDialog
from ui.styles import apply_macos_theme


class ChatWorker(QThread):

    token_received = Signal(str)
    response_finished = Signal()
    error_occurred = Signal(str)

    def __init__(
        self,
        engine: AssistantEngine,
        message: str
    ):
        super().__init__()
        self.engine = engine
        self.message = message

    def run(self):
        try:
            for token in self.engine.send(self.message):
                self.token_received.emit(token)
            self.response_finished.emit()
        except Exception as exc:
            self.error_occurred.emit(str(exc))


class MainWindow(QWidget):

    def __init__(
        self,
        engine: AssistantEngine,
        model_path: str = "",
        gpu_layers: int = 0,
        context_size: int = 8192,
        models_dir: str = "models",
    ):
        super().__init__()

        self.engine = engine
        self.worker = None
        self.current_assistant_response = ""

        # Runtime settings (for Settings dialog)
        self.model_path = model_path
        self.gpu_layers = gpu_layers
        self.context_size = context_size
        self.models_dir = models_dir
        self._dark_mode = False

        self.setWindowTitle("Assistant")
        self.resize(1100, 750)

        self._load_theme_pref()
        self._build_ui()
        apply_macos_theme(self, dark=self._dark_mode)
        self._update_theme_button()
        self.load_conversations()
        self._select_current_conversation()
        self._update_status_bar_info()


    def _build_ui(self):
        self.setObjectName("MainWindow")

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ----- Sidebar (macOS-style) -----
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(260)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 14, 12, 12)
        sidebar_layout.setSpacing(8)

        self.new_chat_button = QPushButton("＋  New Chat")
        self.new_chat_button.setObjectName("PrimaryButton")
        self.new_chat_button.setMinimumHeight(36)
        self.new_chat_button.setCursor(Qt.PointingHandCursor)
        self.new_chat_button.clicked.connect(self.new_conversation)
        sidebar_layout.addWidget(self.new_chat_button)

        self.clear_button = QPushButton("Clear…")
        self.clear_button.setObjectName("SecondaryButton")
        self.clear_button.setMinimumHeight(30)
        self.clear_button.setCursor(Qt.PointingHandCursor)
        clear_menu = QMenu(self)
        clear_menu.addAction("Today", lambda: self.clear_conversations("today"))
        clear_menu.addAction("Last 7 days", lambda: self.clear_conversations("last_week"))
        clear_menu.addSeparator()
        clear_menu.addAction("All conversations…", lambda: self.clear_conversations("all"))
        self.clear_button.setMenu(clear_menu)
        sidebar_layout.addWidget(self.clear_button)

        conversation_label = QLabel("CONVERSATIONS")
        conversation_label.setObjectName("SidebarTitle")
        sidebar_layout.addWidget(conversation_label)

        self.conversation_list = QListWidget()
        self.conversation_list.setObjectName("ConversationList")
        self.conversation_list.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )
        self.conversation_list.setSpacing(2)
        self.conversation_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.conversation_list.itemClicked.connect(
            self.on_conversation_selected
        )
        sidebar_layout.addWidget(self.conversation_list, 1)

        self.settings_button = QPushButton("⚙  Model Manager")
        self.settings_button.setObjectName("SidebarFooterButton")
        self.settings_button.setMinimumHeight(34)
        self.settings_button.setCursor(Qt.PointingHandCursor)
        self.settings_button.clicked.connect(self.open_settings)
        sidebar_layout.addWidget(self.settings_button)

        # ----- Chat panel -----
        chat_panel = QWidget()
        chat_panel.setObjectName("ChatPanel")
        chat_layout = QVBoxLayout(chat_panel)
        chat_layout.setContentsMargins(20, 12, 20, 16)
        chat_layout.setSpacing(12)

        # Top bar: spacer + appearance toggle (Apple-style)
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 4)
        top_bar.addStretch()
        self.theme_button = QPushButton("􀆭  Dark")
        self.theme_button.setObjectName("ThemeToggle")
        self.theme_button.setCursor(Qt.PointingHandCursor)
        self.theme_button.setToolTip("Switch appearance")
        self.theme_button.clicked.connect(self.toggle_theme)
        top_bar.addWidget(self.theme_button)
        chat_layout.addLayout(top_bar)

        self.chat_area = QTextEdit()
        self.chat_area.setObjectName("ChatArea")
        self.chat_area.setReadOnly(True)
        self.chat_area.setPlaceholderText("Start a conversation…")
        self.chat_area.setFrameShape(QFrame.NoFrame)
        chat_layout.addWidget(self.chat_area, 1)

        # Composer bar (rounded capsule)
        composer = QFrame()
        composer.setObjectName("ComposerBar")
        composer_layout = QHBoxLayout(composer)
        composer_layout.setContentsMargins(4, 2, 4, 2)
        composer_layout.setSpacing(0)

        self.input_box = QLineEdit()
        self.input_box.setObjectName("MessageInput")
        self.input_box.setPlaceholderText("Message")
        self.input_box.setMinimumHeight(40)
        self.input_box.returnPressed.connect(self.send_message)
        composer_layout.addWidget(self.input_box, 1)

        self.send_button = QPushButton("Send")
        self.send_button.setObjectName("SendButton")
        self.send_button.setMinimumWidth(72)
        self.send_button.setMinimumHeight(32)
        self.send_button.setCursor(Qt.PointingHandCursor)
        self.send_button.clicked.connect(self.send_message)
        composer_layout.addWidget(self.send_button)

        chat_layout.addWidget(composer)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setAlignment(Qt.AlignRight)
        chat_layout.addWidget(self.status_label)

        main_layout.addWidget(sidebar)
        main_layout.addWidget(chat_panel, 1)
        self.setLayout(main_layout)


    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------



    def toggle_theme(self):
        self._dark_mode = not self._dark_mode
        apply_macos_theme(self, dark=self._dark_mode)
        self._update_theme_button()
        self._save_theme_pref()

    def _update_theme_button(self):
        if not hasattr(self, "theme_button"):
            return
        if self._dark_mode:
            self.theme_button.setText("☀  Light")
            self.theme_button.setToolTip("Switch to Light Mode")
        else:
            self.theme_button.setText("☾  Dark")
            self.theme_button.setToolTip("Switch to Dark Mode")

    def _save_theme_pref(self):
        try:
            from pathlib import Path
            cfg = Path("data")
            cfg.mkdir(parents=True, exist_ok=True)
            path = cfg / "settings.ini"
            lines = []
            if path.is_file():
                for line in path.read_text(encoding="utf-8").splitlines():
                    if line.strip().startswith("dark_mode="):
                        continue
                    lines.append(line)
            lines.append(f"dark_mode={1 if self._dark_mode else 0}")
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError:
            pass

    def _load_theme_pref(self):
        try:
            from pathlib import Path
            path = Path("data/settings.ini")
            if not path.is_file():
                return
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("dark_mode="):
                    self._dark_mode = line.split("=", 1)[1].strip() in ("1", "true", "True")
                    break
        except OSError:
            pass

    def clear_conversations(self, scope: str):
        """
        scope: 'today' | 'last_week' | 'all'
        """
        if self.worker is not None:
            QMessageBox.warning(
                self,
                "Assistant is busy",
                "Please wait for the current response to finish.",
            )
            return

        labels = {
            "today": "conversations from today",
            "last_week": "conversations from the last 7 days",
            "all": "ALL conversations",
        }
        label = labels.get(scope, scope)

        confirm = QMessageBox.question(
            self,
            "Clear conversations",
            (
                f"Delete {label}?\n\n"
                "This cannot be undone."
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        try:
            deleted = self.engine.clear_conversations(scope)
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        self.chat_area.clear()
        self.load_conversations()
        self._select_current_conversation()
        self.status_label.setText(
            f"Cleared {deleted} conversation(s)"
            if deleted
            else "Nothing to clear"
        )
        self.input_box.setFocus()

    def open_settings(self):
        if self.worker is not None:
            QMessageBox.warning(
                self,
                "Assistant is busy",
                "Please wait for the current response to finish.",
            )
            return

        dialog = SettingsDialog(
            parent=self,
            models_dir=self.models_dir,
            current_model=self.model_path,
            current_gpu_layers=self.gpu_layers,
            current_context=self.context_size,
        )

        if dialog.exec():
            if dialog.selected_model_path:
                self.model_path = dialog.selected_model_path
            self.gpu_layers = dialog.gpu_layers
            self.context_size = dialog.context_size
            self.models_dir = dialog.models_dir
            self._update_status_bar_info()

            QMessageBox.information(
                self,
                "Restart required",
                (
                    "Settings were saved to data/settings.ini.\n\n"
                    "Restart the application for the new model / "
                    "GPU layers / context size to take effect."
                ),
            )

    def _update_status_bar_info(self):
        name = (
            self.model_path.split("/")[-1]
            if self.model_path
            else "—"
        )
        self.status_label.setText(
            f"Ready  ·  {name}  ·  gpu_layers={self.gpu_layers}  ·  ctx={self.context_size}"
        )

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    def load_conversations(self):
        self.conversation_list.blockSignals(True)
        self.conversation_list.clear()

        conversations = self.engine.get_conversations()

        for conversation in conversations:
            item = QListWidgetItem(conversation["title"])
            item.setData(Qt.UserRole, conversation["id"])
            self.conversation_list.addItem(item)

        self.conversation_list.blockSignals(False)

    def _select_current_conversation(self):
        current_id = self.engine.conversation_id
        if current_id is None:
            self.conversation_list.clearSelection()
            return

        for index in range(self.conversation_list.count()):
            item = self.conversation_list.item(index)
            conversation_id = item.data(Qt.UserRole)
            if conversation_id == current_id:
                self.conversation_list.setCurrentItem(item)
                return

    def on_conversation_selected(self, item: QListWidgetItem):
        if self.worker is not None:
            return

        conversation_id = item.data(Qt.UserRole)

        try:
            messages = self.engine.load_conversation(conversation_id)
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        self.chat_area.clear()

        for message in messages:
            role = message["role"]
            content = message["content"]
            if role == "user":
                self.append_user_message(content)
            elif role == "assistant":
                self.append_assistant_message(content)

        self._update_status_bar_info()
        self.input_box.setFocus()

    def new_conversation(self):
        if self.worker is not None:
            return

        self.engine.new_conversation()
        self.chat_area.clear()
        self.load_conversations()
        self._select_current_conversation()
        self.status_label.setText("New chat")
        self.input_box.clear()
        self.input_box.setFocus()

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------

    def send_message(self):
        text = self.input_box.text().strip()
        if not text:
            return
        if self.worker is not None:
            return

        self.append_user_message(text)
        self.input_box.clear()

        self.send_button.setEnabled(False)
        self.new_chat_button.setEnabled(False)
        self.settings_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.conversation_list.setEnabled(False)
        self.input_box.setEnabled(False)
        self.status_label.setText("Assistant is thinking...")

        self.chat_area.append(
            "<p style='margin:10px 0 2px 0;'>"
            "<span style='color:#007AFF;font-size:11px;font-weight:600;'>Assistant</span><br>"
            "<span style='font-size:14px;line-height:1.45;'>"
        )
        cursor = self.chat_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.chat_area.setTextCursor(cursor)

        self.current_assistant_response = ""

        self.worker = ChatWorker(self.engine, text)
        self.worker.token_received.connect(self.on_token)
        self.worker.response_finished.connect(self.on_response_finished)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.finished.connect(self._worker_finished)
        self.worker.start()

    def on_token(self, token: str):
        self.current_assistant_response += token
        cursor = self.chat_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(token)
        self.chat_area.setTextCursor(cursor)
        self.chat_area.ensureCursorVisible()

    def on_response_finished(self):
        # Close the open <span>/<p> from the streaming header
        cursor = self.chat_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml("</span></p>")
        self.chat_area.setTextCursor(cursor)
        self.send_button.setEnabled(True)
        self.new_chat_button.setEnabled(True)
        self.settings_button.setEnabled(True)
        self.clear_button.setEnabled(True)
        self.conversation_list.setEnabled(True)
        self.input_box.setEnabled(True)
        self._update_status_bar_info()
        self.load_conversations()
        self._select_current_conversation()
        self.input_box.setFocus()

    def on_error(self, error: str):
        self.chat_area.append(f"\n[Error: {error}]")
        self.status_label.setText("Error")

    def _worker_finished(self):
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None

        self.send_button.setEnabled(True)
        self.new_chat_button.setEnabled(True)
        self.settings_button.setEnabled(True)
        self.clear_button.setEnabled(True)
        self.conversation_list.setEnabled(True)
        self.input_box.setEnabled(True)
        self.input_box.setFocus()

    def append_user_message(self, text: str):
        self.chat_area.append(
            "<p style='margin:10px 0 2px 0;'>"
            "<span style='color:#8E8E93;font-size:11px;font-weight:600;'>You</span><br>"
            f"<span style='font-size:14px;line-height:1.45;'>{self._escape_html(text)}</span>"
            "</p>"
        )

    def append_assistant_message(self, text: str):
        self.chat_area.append(
            "<p style='margin:10px 0 2px 0;'>"
            "<span style='color:#007AFF;font-size:11px;font-weight:600;'>Assistant</span><br>"
            f"<span style='font-size:14px;line-height:1.45;'>{self._escape_html(text)}</span>"
            "</p>"
        )

    @staticmethod
    def _escape_html(text: str) -> str:
        return (
            text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#039;")
        )

    def closeEvent(self, event):
        if self.worker is not None:
            QMessageBox.warning(
                self,
                "Assistant is busy",
                "Please wait for the current response to finish.",
            )
            event.ignore()
            return
        event.accept()

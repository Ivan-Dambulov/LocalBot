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
)

from assistant.engine import AssistantEngine



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

            for token in self.engine.send(
                self.message
            ):

                self.token_received.emit(
                    token
                )

            self.response_finished.emit()

        except Exception as exc:

            self.error_occurred.emit(
                str(exc)
            )



class MainWindow(QWidget):

    def __init__(
        self,
        engine: AssistantEngine
    ):

        super().__init__()

        self.engine = engine

        self.worker = None

        self.current_assistant_response = ""

        self.setWindowTitle(
            "My Assistant"
        )

        self.resize(
            1100,
            750
        )

        self._build_ui()

        self.load_conversations()

        self._select_current_conversation()


    def _build_ui(self):

        main_layout = QHBoxLayout()

        main_layout.setContentsMargins(
            0,
            0,
            0,
            0
        )

        main_layout.setSpacing(0)


        sidebar = QFrame()

        sidebar.setFrameShape(
            QFrame.StyledPanel
        )

        sidebar.setMinimumWidth(
            240
        )

        sidebar.setMaximumWidth(
            320
        )

        sidebar_layout = QVBoxLayout(
            sidebar
        )

        sidebar_layout.setContentsMargins(
            10,
            10,
            10,
            10
        )

        self.new_chat_button = QPushButton(
            "+ New Conversation"
        )

        self.new_chat_button.setMinimumHeight(
            40
        )

        self.new_chat_button.clicked.connect(
            self.new_conversation
        )

        sidebar_layout.addWidget(
            self.new_chat_button
        )

        conversation_label = QLabel(
            "Conversations"
        )

        sidebar_layout.addWidget(
            conversation_label
        )

        self.conversation_list = QListWidget()

        self.conversation_list.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )

        self.conversation_list.itemClicked.connect(
            self.on_conversation_selected
        )

        sidebar_layout.addWidget(
            self.conversation_list
        )


        chat_panel = QWidget()

        chat_layout = QVBoxLayout(
            chat_panel
        )

        chat_layout.setContentsMargins(
            15,
            15,
            15,
            15
        )

        # Chat area
        self.chat_area = QTextEdit()

        self.chat_area.setReadOnly(
            True
        )

        self.chat_area.setPlaceholderText(
            "Start a conversation..."
        )

        chat_layout.addWidget(
            self.chat_area
        )


        input_layout = QHBoxLayout()

        self.input_box = QLineEdit()

        self.input_box.setPlaceholderText(
            "Type your message..."
        )

        self.input_box.setMinimumHeight(
            40
        )

        self.input_box.returnPressed.connect(
            self.send_message
        )

        input_layout.addWidget(
            self.input_box
        )

        self.send_button = QPushButton(
            "Send"
        )

        self.send_button.setMinimumWidth(
            80
        )

        self.send_button.setMinimumHeight(
            40
        )

        self.send_button.clicked.connect(
            self.send_message
        )

        input_layout.addWidget(
            self.send_button
        )

        chat_layout.addLayout(
            input_layout
        )


        self.status_label = QLabel(
            "Ready"
        )

        self.status_label.setAlignment(
            Qt.AlignRight
        )

        chat_layout.addWidget(
            self.status_label
        )


        main_layout.addWidget(
            sidebar
        )

        main_layout.addWidget(
            chat_panel,
            1
        )

        self.setLayout(
            main_layout
        )


    def load_conversations(self):

        self.conversation_list.blockSignals(
            True
        )

        self.conversation_list.clear()

        conversations = (
            self.engine.get_conversations()
        )

        for conversation in conversations:

            item = QListWidgetItem(
                conversation["title"]
            )

            item.setData(
                Qt.UserRole,
                conversation["id"]
            )

            self.conversation_list.addItem(
                item
            )

        self.conversation_list.blockSignals(
            False
        )

    def _select_current_conversation(self):

        current_id = (
            self.engine.conversation_id
        )

        for index in range(
            self.conversation_list.count()
        ):

            item = (
                self.conversation_list.item(
                    index
                )
            )

            conversation_id = item.data(
                Qt.UserRole
            )

            if conversation_id == current_id:

                self.conversation_list.setCurrentItem(
                    item
                )

                return


    def on_conversation_selected(
        self,
        item: QListWidgetItem
    ):

        if self.worker is not None:
            return

        conversation_id = item.data(
            Qt.UserRole
        )

        try:

            messages = (
                self.engine.load_conversation(
                    conversation_id
                )
            )

        except Exception as exc:

            QMessageBox.critical(
                self,
                "Error",
                str(exc)
            )

            return

        self.chat_area.clear()

        for message in messages:

            role = message["role"]

            content = message["content"]

            if role == "user":

                self.append_user_message(
                    content
                )

            elif role == "assistant":

                self.append_assistant_message(
                    content
                )

        self.status_label.setText(
            "Ready"
        )

        self.input_box.setFocus()



    def new_conversation(self):

        if self.worker is not None:
            return

        self.engine.new_conversation()

        self.chat_area.clear()

        self.load_conversations()

        self._select_current_conversation()

        self.status_label.setText(
            "New conversation"
        )

        self.input_box.clear()

        self.input_box.setFocus()



    def send_message(self):

        text = (
            self.input_box
            .text()
            .strip()
        )

        if not text:
            return

        if self.worker is not None:
            return

        # Display user message
        self.append_user_message(
            text
        )

        self.input_box.clear()

        # Disable controls
        self.send_button.setEnabled(
            False
        )

        self.new_chat_button.setEnabled(
            False
        )

        self.conversation_list.setEnabled(
            False
        )

        self.input_box.setEnabled(
            False
        )

        self.status_label.setText(
            "Assistant is thinking..."
        )

        # Prepare assistant message
        self.chat_area.append(
            "<b>Assistant:</b>"
        )

        cursor = (
            self.chat_area.textCursor()
        )

        cursor.movePosition(
            QTextCursor.End
        )

        self.chat_area.setTextCursor(
            cursor
        )

        self.current_assistant_response = ""

        # Create worker
        self.worker = ChatWorker(
            self.engine,
            text
        )

        self.worker.token_received.connect(
            self.on_token_received
        )

        self.worker.response_finished.connect(
            self.on_response_finished
        )

        self.worker.error_occurred.connect(
            self.on_error
        )

        self.worker.finished.connect(
            self._worker_finished
        )

        self.worker.start()



    def on_token_received(
        self,
        token: str
    ):

        self.current_assistant_response += (
            token
        )

        cursor = (
            self.chat_area.textCursor()
        )

        cursor.movePosition(
            QTextCursor.End
        )

        cursor.insertText(
            token
        )

        self.chat_area.setTextCursor(
            cursor
        )

        self.chat_area.ensureCursorVisible()



    def on_response_finished(self):

        self.chat_area.append("")

        self.send_button.setEnabled(
            True
        )

        self.new_chat_button.setEnabled(
            True
        )

        self.conversation_list.setEnabled(
            True
        )

        self.input_box.setEnabled(
            True
        )

        self.status_label.setText(
            "Ready"
        )

        # Reload sidebar because:
        # - title may have changed
        # - updated_at changed
        self.load_conversations()

        self._select_current_conversation()

        self.input_box.setFocus()



    def on_error(
        self,
        error: str
    ):

        self.chat_area.append(
            f"\n[Error: {error}]"
        )

        self.status_label.setText(
            "Error"
        )



    def _worker_finished(self):

        if self.worker is not None:

            self.worker.deleteLater()

            self.worker = None

        self.send_button.setEnabled(
            True
        )

        self.new_chat_button.setEnabled(
            True
        )

        self.conversation_list.setEnabled(
            True
        )

        self.input_box.setEnabled(
            True
        )

        self.input_box.setFocus()



    def append_user_message(
        self,
        text: str
    ):

        self.chat_area.append(
            f"<b>You:</b> "
            f"{self._escape_html(text)}"
        )

        self.chat_area.append("")

    def append_assistant_message(
        self,
        text: str
    ):

        self.chat_area.append(
            f"<b>Assistant:</b> "
            f"{self._escape_html(text)}"
        )

        self.chat_area.append("")



    @staticmethod
    def _escape_html(
        text: str
    ) -> str:

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
                (
                    "Please wait for the current "
                    "response to finish."
                )
            )

            event.ignore()

            return

        event.accept()
"""
macOS-inspired stylesheet for Local AI Assistant.
Works cross-platform; uses system fonts where available.
"""

# Light appearance (default). Soft gray sidebar, white content, SF-like blue accents.
MACOS_LIGHT = """
* {
    font-family: -apple-system, "SF Pro Text", "Segoe UI", "Helvetica Neue",
                 "Helvetica", "Arial", sans-serif;
    font-size: 13px;
}

QWidget#MainWindow {
    background-color: #FFFFFF;
}

/* ---- Sidebar ---- */
QFrame#Sidebar {
    background-color: #F5F5F7;
    border: none;
    border-right: 1px solid #E5E5EA;
}

QLabel#SidebarTitle {
    color: #8E8E93;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.4px;
    padding: 8px 4px 4px 4px;
    text-transform: uppercase;
}

QPushButton#PrimaryButton {
    background-color: #007AFF;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton#PrimaryButton:hover {
    background-color: #0066D6;
}
QPushButton#PrimaryButton:pressed {
    background-color: #0055B3;
}
QPushButton#PrimaryButton:disabled {
    background-color: #B0B0B5;
    color: #F2F2F7;
}

QPushButton#SecondaryButton {
    background-color: transparent;
    color: #3A3A3C;
    border: 1px solid #D1D1D6;
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 12px;
}
QPushButton#SecondaryButton:hover {
    background-color: #EBEBED;
}
QPushButton#SecondaryButton:pressed {
    background-color: #E0E0E5;
}
QPushButton#SecondaryButton:disabled {
    color: #AEAEB2;
    border-color: #E5E5EA;
}

QPushButton#SidebarFooterButton {
    background-color: transparent;
    color: #007AFF;
    border: none;
    border-radius: 8px;
    padding: 8px 10px;
    text-align: left;
    font-size: 13px;
}
QPushButton#SidebarFooterButton:hover {
    background-color: rgba(0, 122, 255, 0.10);
}

/* Conversation list */
QListWidget#ConversationList {
    background-color: transparent;
    border: none;
    outline: none;
    padding: 2px;
}
QListWidget#ConversationList::item {
    background-color: transparent;
    color: #1C1C1E;
    border-radius: 8px;
    padding: 10px 12px;
    margin: 1px 4px;
}
QListWidget#ConversationList::item:hover {
    background-color: rgba(0, 0, 0, 0.05);
}
QListWidget#ConversationList::item:selected {
    background-color: #007AFF;
    color: #FFFFFF;
}

/* ---- Chat area ---- */
QWidget#ChatPanel {
    background-color: #FFFFFF;
}

QTextEdit#ChatArea {
    background-color: #FFFFFF;
    border: none;
    border-radius: 0;
    padding: 8px 4px;
    color: #1C1C1E;
    selection-background-color: #007AFF;
    selection-color: #FFFFFF;
}

/* Composer */
QFrame#ComposerBar {
    background-color: #F9F9FB;
    border: 1px solid #E5E5EA;
    border-radius: 12px;
}

QLineEdit#MessageInput {
    background-color: transparent;
    border: none;
    padding: 10px 12px;
    color: #1C1C1E;
    font-size: 14px;
    selection-background-color: #007AFF;
}
QLineEdit#MessageInput:focus {
    outline: none;
}

QPushButton#SendButton {
    background-color: #007AFF;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
    margin: 6px;
}
QPushButton#SendButton:hover {
    background-color: #0066D6;
}
QPushButton#SendButton:disabled {
    background-color: #C7C7CC;
}

QLabel#StatusLabel {
    color: #8E8E93;
    font-size: 11px;
    padding: 4px 2px;
}


QPushButton#ThemeToggle {
    background-color: transparent;
    color: #3A3A3C;
    border: 1px solid #D1D1D6;
    border-radius: 14px;
    padding: 4px 12px;
    font-size: 12px;
    min-height: 24px;
}
QPushButton#ThemeToggle:hover {
    background-color: #EBEBED;
}

/* Menus */
QMenu {
    background-color: #F5F5F7;
    border: 1px solid #D1D1D6;
    border-radius: 8px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #007AFF;
    color: #FFFFFF;
}
QMenu::separator {
    height: 1px;
    background: #E5E5EA;
    margin: 4px 8px;
}

/* Scrollbars — thin, macOS-like */
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: rgba(0, 0, 0, 0.25);
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(0, 0, 0, 0.40);
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: transparent;
    height: 10px;
}
QScrollBar::handle:horizontal {
    background: rgba(0, 0, 0, 0.25);
    border-radius: 5px;
    min-width: 30px;
}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0;
}
"""

# Optional dark variant if you later toggle appearance
MACOS_DARK = """
* {
    font-family: -apple-system, "SF Pro Text", "Segoe UI", "Helvetica Neue",
                 "Helvetica", "Arial", sans-serif;
    font-size: 13px;
    color: #F5F5F7;
}

QWidget#MainWindow {
    background-color: #1C1C1E;
}

QFrame#Sidebar {
    background-color: #2C2C2E;
    border: none;
    border-right: 1px solid #3A3A3C;
}

QLabel#SidebarTitle {
    color: #8E8E93;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.4px;
    padding: 8px 4px 4px 4px;
}

QPushButton#PrimaryButton {
    background-color: #0A84FF;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: 600;
}
QPushButton#PrimaryButton:hover { background-color: #409CFF; }
QPushButton#PrimaryButton:disabled { background-color: #3A3A3C; color: #8E8E93; }

QPushButton#SecondaryButton {
    background-color: transparent;
    color: #F5F5F7;
    border: 1px solid #48484A;
    border-radius: 8px;
    padding: 6px 12px;
}
QPushButton#SecondaryButton:hover { background-color: #3A3A3C; }

QPushButton#SidebarFooterButton {
    background-color: transparent;
    color: #0A84FF;
    border: none;
    border-radius: 8px;
    padding: 8px 10px;
    text-align: left;
}
QPushButton#SidebarFooterButton:hover {
    background-color: rgba(10, 132, 255, 0.15);
}

QListWidget#ConversationList {
    background-color: transparent;
    border: none;
    outline: none;
}
QListWidget#ConversationList::item {
    background-color: transparent;
    color: #F5F5F7;
    border-radius: 8px;
    padding: 10px 12px;
    margin: 1px 4px;
}
QListWidget#ConversationList::item:hover {
    background-color: rgba(255, 255, 255, 0.08);
}
QListWidget#ConversationList::item:selected {
    background-color: #0A84FF;
    color: #FFFFFF;
}

QWidget#ChatPanel { background-color: #1C1C1E; }

QTextEdit#ChatArea {
    background-color: #1C1C1E;
    border: none;
    color: #F5F5F7;
    selection-background-color: #0A84FF;
}

QFrame#ComposerBar {
    background-color: #2C2C2E;
    border: 1px solid #3A3A3C;
    border-radius: 12px;
}

QLineEdit#MessageInput {
    background-color: transparent;
    border: none;
    padding: 10px 12px;
    color: #F5F5F7;
    font-size: 14px;
}

QPushButton#SendButton {
    background-color: #0A84FF;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
    margin: 6px;
}
QPushButton#SendButton:hover { background-color: #409CFF; }
QPushButton#SendButton:disabled { background-color: #3A3A3C; }

QLabel#StatusLabel {
    color: #8E8E93;
    font-size: 11px;
    padding: 4px 2px;
}


QPushButton#ThemeToggle {
    background-color: transparent;
    color: #F5F5F7;
    border: 1px solid #48484A;
    border-radius: 14px;
    padding: 4px 12px;
    font-size: 12px;
    min-height: 24px;
}
QPushButton#ThemeToggle:hover {
    background-color: #3A3A3C;
}

QMenu {
    background-color: #2C2C2E;
    border: 1px solid #48484A;
    border-radius: 8px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #0A84FF;
    color: #FFFFFF;
}
QMenu::separator {
    height: 1px;
    background: #48484A;
    margin: 4px 8px;
}

QScrollBar:vertical {
    background: transparent;
    width: 10px;
}
QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.25);
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


def apply_macos_theme(widget, dark: bool = False) -> None:
    """Apply theme stylesheet to a top-level window/widget."""
    widget.setStyleSheet(MACOS_DARK if dark else MACOS_LIGHT)

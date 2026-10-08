from PySide6.QtWidgets import QListWidget

class DeselectableListWidget(QListWidget):
    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        if not item:
            self.clearSelection()
            self.setCurrentItem(None)
        super().mousePressEvent(event)
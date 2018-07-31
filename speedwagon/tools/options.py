import abc
import os
import typing
import warnings

from PyQt5 import QtWidgets, QtCore


class WidgetMeta(abc.ABCMeta, type(QtCore.QObject)):  # type: ignore
    pass


class ToolOption:

    def __init__(self, name) -> None:
        self.name = name
        self._data = ""


class ToolOptionDataType(ToolOption):
    def __init__(self, name, data_type=str) -> None:
        warnings.warn("To be removed", DeprecationWarning)
        super().__init__(name)
        self.data_type = data_type
        self._data = ""

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, value):
        if not isinstance(value, self.data_type):
            raise TypeError("Invalid type")
        self._data = value


class UserOption(metaclass=abc.ABCMeta):
    def __init__(self, label_text):
        warnings.warn("Use UserOption2 instead", DeprecationWarning)
        self.label_text = label_text
        self.data = None

    @abc.abstractmethod
    def is_valid(self) -> bool:
        pass

    def browse(self):
        pass


class UserOption2(metaclass=abc.ABCMeta):
    def __init__(self, label_text):
        self.label_text = label_text
        self.data = None

    @abc.abstractmethod
    def is_valid(self) -> bool:
        pass

    def edit_widget(self) -> QtWidgets.QWidget:
        pass


class UserOptionPythonDataType2(UserOption2):
    def __init__(self, label_text, data_type=str) -> None:
        super().__init__(label_text)
        self.data_type = data_type
        self.data = None

    def is_valid(self) -> bool:
        return isinstance(self.data, self.data_type)


class AbsCustomData(metaclass=abc.ABCMeta):
    @classmethod
    @abc.abstractmethod
    def is_valid(cls, value) -> bool:
        pass

    @classmethod
    def browse(cls):
        pass


class AbsCustomData2(metaclass=abc.ABCMeta):
    @classmethod
    @abc.abstractmethod
    def is_valid(cls, value) -> bool:
        pass

    @classmethod
    @abc.abstractmethod
    def edit_widget(cls) -> QtWidgets.QWidget:
        pass


class UserOptionCustomDataTypeWidgets(UserOption2):
    def __init__(
            self,
            label_text,
            data_type: typing.Type[AbsCustomData2]
    ) -> None:

        super().__init__(label_text)
        self.data_type = data_type
        self.data = None


class UserOptionCustomDataType(UserOption2):
    def __init__(
            self,
            label_text,
            data_type: typing.Type[AbsCustomData2]
    ) -> None:

        super().__init__(label_text)
        self.data_type = data_type
        self.data = None

    def is_valid(self) -> bool:
        return self.data_type.is_valid(self.data)
        # return self.data_type.is_valid(self.data)

    def edit_widget(self) -> QtWidgets.QWidget:
        return self.data_type.edit_widget()

    # def browse(self):
    #     return self.data_type.browse()


class FileData(AbsCustomData, metaclass=abc.ABCMeta):

    def __init__(self) -> None:
        warnings.warn("Removing soon", DeprecationWarning)
        super().__init__()

    @classmethod
    def is_valid(cls, value) -> bool:
        if not os.path.isfile(value):
            return False
        if os.path.basename(value) != cls.filename():
            return False
        return True

    @classmethod
    def browse(cls) -> QtWidgets.QWidget:
        browser = QtWidgets.QFileDialog()
        browser.setModal(True)
        browser.setFileMode(QtWidgets.QFileDialog.AnyFile)
        browser.setNameFilter(cls.filter())
        return browser

    @staticmethod
    @abc.abstractmethod
    def filename() -> str:
        pass

    @staticmethod
    @abc.abstractmethod
    def filter() -> str:
        pass


#

class CustomItemWidget(QtWidgets.QWidget):
    editingFinished = QtCore.pyqtSignal()

    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self._data = ""
        self.inner_layout = QtWidgets.QHBoxLayout(parent)
        self.inner_layout.setSpacing(3)
        self.inner_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.inner_layout)
        self.setAutoFillBackground(True)

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, value):
        self._data = value
        self.editingFinished.emit()


class AbsBrowseableWidget(CustomItemWidget, metaclass=WidgetMeta):
    # class AbsBrowseableWidget(metaclass=WidgetMeta):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__()
        self.text_line = QtWidgets.QLineEdit(self)
        size_p = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                                       QtWidgets.QSizePolicy.MinimumExpanding)
        self.text_line.setSizePolicy(size_p)
        self.browse_button = QtWidgets.QPushButton("Browse", parent=self)
        # self.browse_button.setSizePolicy(size_p)
        self.inner_layout.addWidget(self.text_line)
        self.inner_layout.addWidget(self.browse_button)
        self.text_line.textEdited.connect(self._change_data)
        self.text_line.editingFinished.connect(self.editingFinished)
        # self.text_line.focus
        # self.text_line.
        self.browse_button.clicked.connect(self.browse_clicked)
        # self.browse_button.clicked.connect(self.editingFinished)

        # self.setFocusPolicy(QtCore.Qt.StrongFocus)
        # self.text_line.setFocusPolicy(QtCore.Qt.StrongFocus)

    @abc.abstractmethod
    def browse_clicked(self):
        pass

    @property
    def data(self):
        return super().data

    @data.setter
    def data(self, value):
        self._data = value
        self.text_line.setText(value)

    def _change_data(self, value):
        self.data = value


class FolderBrowseWidget(AbsBrowseableWidget):

    def browse_clicked(self):
        selection = QtWidgets.QFileDialog.getExistingDirectory()
        if selection:
            self.data = selection
            self.editingFinished.emit()


class FolderData(AbsCustomData2, metaclass=abc.ABCMeta):

    @classmethod
    def is_valid(cls, value) -> bool:
        if not os.path.isdir(value):
            return False
        return True

    @classmethod
    def edit_widget(cls) -> QtWidgets.QWidget:
        return FolderBrowseWidget()

    # @classmethod
    # def browse(cls):
    #     return QtWidgets.QLineEdit()


class ListSelectionWidget(CustomItemWidget, metaclass=WidgetMeta):

    def __init__(self, selections, *args, **kwargs):
        super().__init__()
        # super().__init__(parent, *args, **kwargs)
        self._combobox = QtWidgets.QComboBox()
        self._selections = selections

        self._model = QtCore.QStringListModel()
        self._model.setStringList(self._selections)
        self._combobox.setModel(self._model)
        self._combobox.currentIndexChanged.connect(self._update)
        self.inner_layout.addWidget(self._combobox,
                                    alignment=QtCore.Qt.AlignBaseline)

    def _update(self):
        self.data = self._combobox.currentText()


class ListSelection(UserOption2):

    def __init__(self, label_text):
        super().__init__(label_text)
        self._selections = []

    def is_valid(self) -> bool:
        return True

    def edit_widget(self) -> QtWidgets.QWidget:
        return ListSelectionWidget(self._selections)

    def add_selection(self, text):
        self._selections.append(text)
        self.data = self._selections[0]
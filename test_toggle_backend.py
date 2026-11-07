from PySide6 import QtWidgets
import main, input_controller, importlib
import skill_combo_config as scc

app = QtWidgets.QApplication([])
win = main.MainWindow()
# Toggle to win32 and DRY_RUN on
win._on_backend_changed('win32')
win._on_dry_run_toggled(True)
# reload skill config to confirm saved values
importlib.reload(scc)
print('ic backend:', input_controller.INPUT_BACKEND, 'ic dry:', input_controller.INPUT_DRY_RUN)
print('scc backend:', scc.INPUT_BACKEND, 'scc dry:', scc.INPUT_DRY_RUN)
app.quit()
